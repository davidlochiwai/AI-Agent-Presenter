from __future__ import annotations

import hmac
import json
import queue
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.types import ASGIApp, Receive, Scope, Send

from voice_app import config
from voice_app.config import persist_generated_token
from voice_app.director import PresentationDirector
from voice_app.events import EventBus
from voice_app.mcp_http import CORS_HEADERS, discovery_payload, handle_jsonrpc, handle_mcp, json_mcp, options_mcp
from voice_app.retell import (
    create_web_call,
    get_call,
    summarize_call,
    sync_director_function_endpoints,
    sync_mcp_endpoint,
    sync_presenter_behavior,
    verify_retell_signature,
)
from voice_app.bridge import catalog as bridge_catalog
from voice_app.bridge import dispatch as bridge_dispatch
from voice_app.bridge import run_actions as bridge_run
from voice_app.bridge import snapshot_for_bridge
from voice_app.qa_rag import QARagService
from voice_app.runtime import PresenterRuntime
from voice_app.tools import TOOL_SPECS, dispatch_tool
from voice_app.tunnel import (
    TunnelInfo,
    is_ephemeral_public_url,
    start_tunnel,
    wait_until_public,
)
from voice_app.window_layout import arrange_app_window, presenter_layout

STATIC_DIR = Path(__file__).resolve().parent / "static"

events = EventBus()
runtime = PresenterRuntime(events)
qa_service = QARagService()
director = PresentationDirector(runtime, qa_service)

tunnel_info: TunnelInfo | None = None
public_base = ""
tunnel_live = False
last_call_id: str | None = None
mcp_hits: deque[dict[str, Any]] = deque(maxlen=40)
bridge_hits: deque[dict[str, Any]] = deque(maxlen=40)
retell_tool_info: dict[str, Any] = {}
retell_director_info: dict[str, Any] = {}
retell_director_sync_lock = threading.Lock()


def _arrange_presenter_windows() -> dict[str, Any]:
    if not config.PRESENTER_SPLIT_LAYOUT:
        return {"ok": False, "error": "Split presenter layout is disabled."}
    try:
        layout = presenter_layout(config.PRESENTER_SLIDE_RATIO)
        powerpoint = runtime.arrange_show()
        browser = arrange_app_window(layout.app)
        errors = [
            result.get("error")
            for result in (powerpoint, browser)
            if not result.get("ok") and result.get("error")
        ]
        return {
            "ok": bool(powerpoint.get("ok") and browser.get("ok")),
            "layout": layout.to_dict(),
            "powerpoint": powerpoint,
            "app": browser,
            "error": "; ".join(errors),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _print_retell_urls(base: str) -> None:
    token = config.DIRECTOR_WEBHOOK_TOKEN
    print("", flush=True)
    print("=" * 72, flush=True)
    print("Retell should call the Python director endpoints.", flush=True)
    print(f"Deliver next:          POST {base}/webhook/presenter/deliver-next", flush=True)
    print(f"Handle question:       POST {base}/webhook/presenter/handle-question", flush=True)
    print(f"Auth header:           Authorization: Bearer {token}", flush=True)
    print("Local MCP remains only as a fallback.", flush=True)
    print(f"Fallback MCP URL:      {base}/mcp", flush=True)
    print("=" * 72, flush=True)
    print("", flush=True)


def _resolve_public_base() -> tuple[str, TunnelInfo | None]:
    configured = (config.DIRECTOR_PUBLIC_URL or "").rstrip("/")
    if configured and not is_ephemeral_public_url(configured):
        print(f"Using the configured director public URL: {configured}", flush=True)
        return configured, None
    if configured and is_ephemeral_public_url(configured):
        print(
            f"Ignoring stale tunnel URL in .env ({configured}). "
            "trycloudflare hostnames die when the app stops; starting a fresh tunnel.",
            flush=True,
        )
    if not config.DIRECTOR_AUTO_TUNNEL:
        return configured, None
    try:
        info = start_tunnel(config.APP_PORT)
    except Exception as exc:
        print(
            f"No public tunnel ({exc}). Set DIRECTOR_PUBLIC_URL or install cloudflared.",
            flush=True,
        )
        return "", None
    if not info:
        print("No public tunnel. Install cloudflared or set DIRECTOR_PUBLIC_URL.", flush=True)
        return "", None
    print(f"Public tunnel ({info.provider}): {info.public_url}", flush=True)
    return info.public_url.rstrip("/"), info


def _capture_mcp(event: dict[str, Any]) -> None:
    if event.get("type") != "mcp":
        return
    mcp_hits.appendleft(
        {
            "method": event.get("method"),
            "detail": event.get("detail") or "",
            "t": time.strftime("%H:%M:%S"),
        }
    )


events.subscribe(_capture_mcp)


def _sync_retell_mcp(base: str) -> None:
    global retell_tool_info
    mcp_url = f"{base.rstrip('/')}/mcp"
    try:
        result = sync_mcp_endpoint(mcp_url)
        retell_tool_info = result
        if result.get("ok") and result.get("changed"):
            for note in result.get("notes") or []:
                print(f"Retell sync: {note}", flush=True)
        elif result.get("ok"):
            print("Retell MCP URL already matches this tunnel.", flush=True)
        else:
            print(f"Retell MCP sync skipped: {result.get('error')}", flush=True)
    except Exception as exc:
        retell_tool_info = {"ok": False, "error": str(exc)}
        print(f"Retell MCP sync failed: {exc}", flush=True)


def _sync_retell_presenter(director_base: str = "") -> None:
    def run() -> None:
        try:
            result = sync_presenter_behavior()
            for note in result.get("notes") or []:
                print(f"Retell presenter: {note}", flush=True)
            if director_base:
                _sync_retell_director_now(director_base)
        except Exception as exc:
            global retell_director_info
            retell_director_info = {"ok": False, "error": str(exc)}
            print(f"Retell presenter sync failed: {exc}", flush=True)

    threading.Thread(target=run, daemon=True, name="retell-presenter-sync").start()


def _sync_retell_director_now(base: str) -> dict[str, Any]:
    global retell_director_info
    with retell_director_sync_lock:
        try:
            result = sync_director_function_endpoints(base)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        retell_director_info = result
    for note in result.get("notes") or []:
        print(f"Retell director: {note}", flush=True)
    if not result.get("ok"):
        print(f"Retell director sync failed: {result.get('error')}", flush=True)
    return result


def _verify_tunnel_later(base: str) -> None:
    def run() -> None:
        global tunnel_live
        time.sleep(1.5)
        tunnel_live = wait_until_public(base)
        if tunnel_live:
            print("Tunnel health check: OK — Retell can reach this PC.", flush=True)
            _sync_retell_director_now(base)
        else:
            print(
                "Tunnel health check: not confirmed yet. "
                "Voice Start will remain disabled for this dead URL.",
                flush=True,
            )
        _sync_retell_mcp(base)

    threading.Thread(target=run, daemon=True, name="tunnel-health").start()


def _ensure_voice_ingress_ready(timeout_s: float = 12.0) -> None:
    """Refuse to start a voice call until Retell can reach this process."""
    if not public_base:
        raise RuntimeError("No public director URL is available.")
    deadline = time.time() + timeout_s
    while not tunnel_live and time.time() < deadline:
        time.sleep(0.2)
    if not tunnel_live:
        raise RuntimeError(
            "The public tunnel did not pass its health check. Restart the app "
            "to obtain a new Cloudflare URL, then try Voice Start again."
        )

    expected = {
        "deliver_next": f"{public_base}/webhook/presenter/deliver-next",
        "handle_audience_question": f"{public_base}/webhook/presenter/handle-question",
    }
    current_urls = retell_director_info.get("urls")
    if retell_director_info.get("ok") is True and current_urls == expected:
        return
    result = _sync_retell_director_now(public_base)
    if result.get("ok") is not True:
        raise RuntimeError(
            "Retell function URLs could not be updated: "
            f"{result.get('error') or 'unknown synchronization error'}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tunnel_info, public_base, tunnel_live
    persist_generated_token()
    if config.USED_PROJECT_ENV_OVER_PROCESS:
        print(
            "Using RETELL_API_KEY from this project's .env. "
            "A different RETELL_API_KEY was already set in Windows and would have called the wrong Retell account.",
            flush=True,
        )
    public_base, tunnel_info = _resolve_public_base()
    tunnel_live = False
    if public_base:
        _print_retell_urls(public_base)
        _verify_tunnel_later(public_base)
        # Update the prompt immediately, but never publish an unverified tunnel
        # to Retell. The health-check thread updates the function URLs.
        _sync_retell_presenter()
    else:
        print("No public HTTPS URL. Retell cannot reach the Python director.", flush=True)
        _sync_retell_presenter()
    yield
    if tunnel_info:
        tunnel_info.stop()


def _host_from_scope(scope: Scope) -> str:
    for key, value in scope.get("headers") or []:
        if key.lower() == b"host":
            return value.decode("latin-1").split(":")[0].lower()
    return ""


def _query_token(scope: Scope) -> str:
    raw = scope.get("query_string") or b""
    query = raw.decode("latin-1")
    for part in query.split("&"):
        if part.startswith("token="):
            return part.split("=", 1)[1]
    return ""


def _bearer_from_scope(scope: Scope) -> str:
    for key, value in scope.get("headers") or []:
        if key.lower() == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                return text.split(" ", 1)[1].strip()
            return text.strip()
    return _query_token(scope)


def _token_ok(given: str) -> bool:
    expected = config.PRESENTER_TOOL_TOKEN
    return bool(expected) and bool(given) and hmac.compare_digest(given, expected)


def _director_token_ok(given: str) -> bool:
    expected = config.DIRECTOR_WEBHOOK_TOKEN
    return bool(expected) and bool(given) and hmac.compare_digest(given, expected)


class AccessGuardMiddleware:
    """Pure ASGI middleware so MCP/SSE responses are not buffered."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        method = scope.get("method") or ""
        client_host = (scope.get("client") or ("?", 0))[0]
        query = (scope.get("query_string") or b"").decode("latin-1")
        if path.startswith("/mcp") or path.startswith("/api/retell") or path.startswith("/api/bridge") or path == "/health":
            suffix = f"?{query}" if query else ""
            print(f"{client_host} {method} {path}{suffix}", flush=True)
            if path.startswith("/api/bridge"):
                bridge_hits.appendleft(
                    {
                        "method": method,
                        "path": path,
                        "t": time.strftime("%H:%M:%S"),
                        "client": client_host,
                    }
                )
        if path.startswith("/api/bridge") and method != "OPTIONS":
            if not _token_ok(_bearer_from_scope(scope)):
                await JSONResponse(
                    {"error": "Unauthorized. Send Authorization: Bearer <PRESENTER_TOOL_TOKEN>."},
                    status_code=401,
                    headers=CORS_HEADERS,
                )(scope, receive, send)
                return
        elif path.startswith("/api/retell") and method not in {"GET", "HEAD", "OPTIONS"}:
            if not _token_ok(_bearer_from_scope(scope)):
                await JSONResponse(
                    {"error": "Unauthorized. Send Authorization: Bearer <PRESENTER_TOOL_TOKEN>."},
                    status_code=401,
                    headers=CORS_HEADERS,
                )(scope, receive, send)
                return
        elif path.startswith("/mcp") or path == "/health":
            pass
        elif path.startswith("/api/") or path == "/" or path.startswith("/static"):
            if _host_from_scope(scope) not in {"127.0.0.1", "localhost", "::1"}:
                await JSONResponse(
                    {"error": "Open this app at http://127.0.0.1, not the public tunnel URL."},
                    status_code=403,
                )(scope, receive, send)
                return
        await self.app(scope, receive, send)


app = FastAPI(title="AI Agent Presenter", lifespan=lifespan, redirect_slashes=False)
app.add_middleware(AccessGuardMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoadBody(BaseModel):
    path: str = Field(min_length=1)


class StartCallBody(BaseModel):
    presenter_view: bool = False
    voice: bool = False


class BridgeRunBody(BaseModel):
    actions: str | list[str] | None = None
    action: str | None = None
    slide_number: int | None = None
    presenter_view: bool = False
    interrupt: bool = False
    spoken_text: str = ""


class SpeechBody(BaseModel):
    speaking: bool


class QABody(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    current_slide: int | None = None
    call_id: str | None = None


def _tool_error(exc: Exception) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)


def _token_ok_request(request: Request) -> bool:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        given = auth.split(" ", 1)[1].strip()
    else:
        given = auth.strip() or (request.query_params.get("token") or "")
    return _token_ok(given)


@app.api_route("/mcp", methods=["GET", "POST", "DELETE", "HEAD", "OPTIONS"])
@app.api_route("/mcp/", methods=["GET", "POST", "DELETE", "HEAD", "OPTIONS"])
async def mcp_endpoint(request: Request) -> Response:
    return await handle_mcp(request, runtime, allow_call=_token_ok_request(request))


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "ai-agent-presenter"}


async def _director_payload(request: Request) -> dict[str, Any]:
    auth = request.headers.get("authorization") or ""
    given = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else auth.strip()
    if not _director_token_ok(given):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized. Send the configured director Bearer token.",
        )
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required.")
    return payload


@app.post("/webhook/presenter/session")
async def director_session(request: Request) -> dict[str, Any]:
    return director.reset(await _director_payload(request))


@app.post("/webhook/presenter/deliver-next")
async def director_deliver_next(request: Request) -> dict[str, Any]:
    return director.deliver_next(await _director_payload(request))


@app.post("/webhook/presenter/handle-question")
async def director_handle_question(request: Request) -> dict[str, Any]:
    return director.handle_question(await _director_payload(request))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    base = public_base
    saved = retell_tool_info.get("mcp_url")
    local_mcp = f"{base}/mcp" if base else None
    director_base = base.rstrip("/") if base else ""
    return {
        "agent_configured": bool(config.RETELL_API_KEY and config.RETELL_AGENT_ID),
        "agent_id": config.RETELL_AGENT_ID,
        "agent_name": retell_tool_info.get("agent_name"),
        "public_base_url": base,
        "tunnel_live": tunnel_live,
        "mcp_url": local_mcp,
        "mcp_url_with_token": f"{base}/mcp?token={config.PRESENTER_TOOL_TOKEN}" if base else None,
        "retell_mcp_url": saved,
        "mcp_url_match": bool(local_mcp and saved and local_mcp.rstrip("/") == str(saved).rstrip("/")),
        "has_end_call": bool(retell_tool_info.get("has_end_call")),
        "presenter_tool_count": retell_tool_info.get("presenter_tool_count") or 0,
        "retell_sync_error": retell_tool_info.get("error"),
        "function_url": f"{base}/api/retell/function" if base else None,
        "auth_header": f"Bearer {config.DIRECTOR_WEBHOOK_TOKEN}",
        "mcp_auth_header": f"Bearer {config.PRESENTER_TOOL_TOKEN}",
        "tools": [spec["name"] for spec in TOOL_SPECS],
        "app_port": config.APP_PORT,
        "last_call_id": last_call_id,
        "mcp_hits": list(mcp_hits)[:12],
        "director_public_url": director_base or None,
        "director_auto_tunnel": config.DIRECTOR_AUTO_TUNNEL,
        "director_tunnel_live": tunnel_live,
        "director_webhook_auth_configured": bool(config.DIRECTOR_WEBHOOK_TOKEN),
        "retell_director_sync_ok": retell_director_info.get("ok"),
        "retell_director_sync_error": retell_director_info.get("error"),
        "director_session_url": (
            f"{director_base}/webhook/presenter/session" if director_base else None
        ),
        "director_deliver_next_url": (
            f"{director_base}/webhook/presenter/deliver-next" if director_base else None
        ),
        "director_handle_question_url": (
            f"{director_base}/webhook/presenter/handle-question" if director_base else None
        ),
        "director": director.snapshot(),
        "bridge_hits": list(bridge_hits)[:8],
        "sample_deck_path": str(config.SAMPLE_DECK_PATH) if config.SAMPLE_DECK_PATH.exists() else None,
        "sample_script_path": str(config.SAMPLE_SCRIPT_PATH) if config.SAMPLE_SCRIPT_PATH.exists() else None,
        "sample_knowledge_path": str(config.SAMPLE_KNOWLEDGE_PATH) if config.SAMPLE_KNOWLEDGE_PATH.exists() else None,
        "script_beats_total": len(director.beats),
        "script_source": director.script_source,
        "slide_pause_ms": config.SLIDE_PAUSE_MS,
        "reminder_trigger_ms": config.RETELL_REMINDER_TRIGGER_MS,
        "presenter_split_layout": config.PRESENTER_SPLIT_LAYOUT,
        "presenter_slide_ratio": config.PRESENTER_SLIDE_RATIO,
        "qa": qa_service.status(),
    }


@app.get("/api/session")
def api_session() -> dict[str, Any]:
    return runtime.snapshot()


@app.post("/api/layout/arrange")
def api_layout_arrange() -> dict[str, Any]:
    return _arrange_presenter_windows()


@app.post("/api/session/load")
def api_load(body: LoadBody) -> dict[str, Any]:
    try:
        loaded = runtime.load(body.path)
        loaded["script"] = director.reload_beats()
        if config.QA_AUTO_INDEX:
            loaded["qa_index"] = qa_service.start_index(body.path)
        return loaded
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/session/start-call")
def api_start_call(body: StartCallBody) -> dict[str, Any]:
    global last_call_id
    last_call_id = None
    snap = runtime.snapshot()
    if not snap.get("loaded"):
        raise HTTPException(status_code=400, detail="Load a .pptx path first.")
    runtime.reset_talk_state()
    director.reload_beats()
    try:
        runtime.start_show(presenter_view=body.presenter_view)
        snap = runtime.snapshot()
        status = snap["status"]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    layout = (
        _arrange_presenter_windows()
        if not body.presenter_view
        else {"ok": False, "error": "Presenter View uses PowerPoint fullscreen mode."}
    )
    access_token = None
    want_voice = bool(body.voice)
    if want_voice:
        if not (config.RETELL_API_KEY and config.RETELL_AGENT_ID):
            raise HTTPException(
                status_code=400,
                detail="Voice is checked, but RETELL_API_KEY / RETELL_AGENT_ID are missing in .env.",
            )
        try:
            _ensure_voice_ingress_ready()
        except Exception as exc:
            runtime.end_show()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        try:
            call = create_web_call(
                {
                    "deck_name": str(snap.get("name") or ""),
                    "slide_count": str(status.get("slide_count") or 0),
                    "current_slide": str(status.get("slide") or 1),
                    "current_title": str(status.get("title") or ""),
                    "current_notes": str(status.get("notes") or "")[:800],
                },
                {"deck_path": snap.get("path"), "app": "ai-agent-presenter"},
            )
        except Exception as exc:
            runtime.end_show()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        access_token = call.get("access_token") or call.get("accessToken")
        if not access_token:
            raise HTTPException(status_code=502, detail=f"Retell did not return an access token: {call}")
        last_call_id = str(call.get("call_id") or "") or None
        print(f"Created web call {last_call_id}", flush=True)
    director_reset = director.reset(
        {
            "event": "session_started",
            "call_id": last_call_id,
            "deck_name": str(snap.get("name") or ""),
            "deck_path": snap.get("path"),
            "slides": snap.get("slides") or [],
            "status": status,
            "slide_pause_ms": config.SLIDE_PAUSE_MS,
        }
    )
    print("Python director session reset.", flush=True)
    return {
        "access_token": access_token,
        "call_id": last_call_id if access_token else None,
        "voice": bool(access_token),
        "status": status,
        "director": director_reset,
        "layout": layout,
    }


class DeliverNextBody(BaseModel):
    dry: bool = False


@app.post("/api/session/run")
def api_session_run(body: BridgeRunBody) -> dict[str, Any]:
    """Local-only COM test. Does not advance the scripted director."""
    try:
        if body.actions:
            return bridge_run(runtime, body.actions)
        if body.action:
            args: dict[str, Any] = {}
            if body.slide_number is not None:
                args["slide_number"] = body.slide_number
            return bridge_dispatch(runtime, body.action, args)
        return bridge_dispatch(runtime, "next")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/debug/director-deliver-next")
def api_debug_director_deliver_next(body: DeliverNextBody | None = None) -> dict[str, Any]:
    dry = bool(body.dry) if body else False
    result = director.deliver_next({"dry": dry, "source": "console"})
    print(f"Python director deliver-next: {result}", flush=True)
    return result


@app.get("/api/debug/call")
def api_debug_call(call_id: str | None = None) -> dict[str, Any]:
    target = call_id or last_call_id
    if not target:
        raise HTTPException(status_code=404, detail="No call yet. Press Start first.")
    try:
        summary = summarize_call(get_call(target))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    local_tool_names = [hit["method"] for hit in mcp_hits if hit.get("method") == "tools/call"]
    summary["local_mcp_hits"] = list(mcp_hits)[:20]
    summary["local_tools_called"] = local_tool_names
    summary["hint"] = _debug_hint(summary)
    return summary


def _debug_hint(summary: dict[str, Any]) -> str:
    if summary.get("called_end_call") and not summary.get("called_presenter_tool"):
        return (
            "The agent hung up with end_call and never invoked a PowerPoint MCP tool. "
            "Remove or restrict the prebuilt end_call tool in Retell. "
            "If this console showed no tools/call line, Retell did not reach this PC (stale MCP URL)."
        )
    if summary.get("disconnection_reason") == "agent_hangup":
        return "disconnection_reason=agent_hangup means the model called end_call. Delete that prebuilt tool for a live presenter."
    if not summary.get("called_presenter_tool"):
        return "No PowerPoint tool ran. Watch this console for method='tools/call'. Silence means the MCP URL on the agent is wrong."
    return "A presenter tool ran. If PowerPoint did not move, check the Presenter tools log for an error."


@app.post("/api/session/end-show")
def api_end_show() -> dict[str, Any]:
    return runtime.end_show()


@app.api_route("/api/bridge", methods=["GET", "HEAD", "OPTIONS"])
@app.api_route("/api/bridge/", methods=["GET", "HEAD", "OPTIONS"])
def api_bridge_root(request: Request) -> Any:
    if request.method == "OPTIONS":
        return options_mcp()
    payload = bridge_catalog()
    payload.update(snapshot_for_bridge(runtime))
    return json_mcp(payload)


@app.post("/api/bridge/wait-idle")
def api_bridge_wait_idle() -> Any:
    ready = runtime.wait_until_line_finished(90.0)
    print(
        f"wait-idle: speaking={ready.get('speaking')} idle={ready.get('idle')} "
        f"timed_out={ready.get('timed_out', False)}",
        flush=True,
    )
    return json_mcp(ready)


@app.get("/api/bridge/ready")
def api_bridge_ready() -> Any:
    return json_mcp(runtime.speech_ready())


@app.get("/api/bridge/status")
def api_bridge_status() -> Any:
    return json_mcp({"ok": True, **snapshot_for_bridge(runtime)})


@app.get("/api/bridge/slides")
def api_bridge_slides() -> Any:
    return json_mcp(bridge_dispatch(runtime, "slides"))


@app.post("/api/bridge/qa")
def api_bridge_qa(body: QABody) -> Any:
    current_slide = body.current_slide
    if current_slide is None:
        try:
            current_slide = int((runtime.snapshot().get("status") or {}).get("slide") or 0) or None
        except (TypeError, ValueError):
            current_slide = None
    result = qa_service.answer(body.question, current_slide=current_slide)
    result["call_id"] = body.call_id
    print(
        f"Q&A {result.get('mode')}: answerable={result.get('answerable')} "
        f"slide={result.get('slide')} sources={result.get('source_ids')}",
        flush=True,
    )
    return json_mcp(result)


@app.get("/api/qa/status")
def api_qa_status() -> dict[str, Any]:
    return qa_service.status()


@app.post("/api/qa/reindex")
def api_qa_reindex() -> dict[str, Any]:
    snap = runtime.snapshot()
    path = snap.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Load a PowerPoint deck first.")
    return qa_service.start_index(path, force=True)


@app.post("/api/session/speech")
def api_session_speech(body: SpeechBody) -> dict[str, Any]:
    runtime.set_agent_speaking(body.speaking)
    return {"ok": True, "speaking": body.speaking, **runtime.speech_ready()}


@app.post("/api/bridge/run")
def api_bridge_run(body: BridgeRunBody) -> Any:
    try:
        if body.actions:
            return json_mcp(bridge_run(runtime, body.actions, interrupt=body.interrupt, spoken_text=body.spoken_text or ""))
        if body.action:
            args: dict[str, Any] = {}
            if body.slide_number is not None:
                args["slide_number"] = body.slide_number
            if body.action in {"start", "start_show"}:
                args["presenter_view"] = body.presenter_view
            if body.action in {"goto_slide", "next", "previous", "next_slide", "previous_slide", "first", "last"} and not body.interrupt:
                runtime.enqueue_nav([(body.action, args)])
                snap = runtime.snapshot()
                return json_mcp({"ok": True, "queued": True, "status": snap.get("status")})
            return json_mcp(bridge_dispatch(runtime, body.action, args))
        raise HTTPException(status_code=400, detail='Send {"actions": "goto_slide:3"} or {"action": "next"}.')
    except HTTPException:
        raise
    except Exception as exc:
        return json_mcp({"ok": False, "error": str(exc)})


@app.get("/api/events")
def api_events() -> StreamingResponse:
    incoming: queue.Queue[dict[str, Any]] = queue.Queue()
    unsubscribe = events.subscribe(incoming.put)

    def generate():
        try:
            yield f"data: {json.dumps({'type': 'hello'})}\n\n"
            while True:
                try:
                    item = incoming.get(timeout=15)
                    yield f"data: {json.dumps(item, default=str)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            unsubscribe()

    return StreamingResponse(generate(), media_type="text/event-stream")


def _extract_tool_call(payload: dict[str, Any], fallback_name: str | None) -> tuple[str, dict[str, Any]]:
    name = (
        payload.get("name")
        or payload.get("function")
        or payload.get("function_name")
        or fallback_name
    )
    args = payload.get("args")
    if not isinstance(args, dict):
        maybe_arguments = payload.get("arguments")
        if isinstance(maybe_arguments, dict):
            args = maybe_arguments
        elif isinstance(maybe_arguments, str):
            try:
                parsed = json.loads(maybe_arguments)
                args = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                args = {}
        else:
            args = {key: value for key, value in payload.items() if key not in {"name", "call", "args", "function", "function_name", "arguments"}}
    if not name:
        raise HTTPException(status_code=400, detail="Function name is missing.")
    return str(name), args


@app.api_route("/api/retell/function", methods=["GET", "POST", "HEAD", "OPTIONS"])
async def retell_function(request: Request) -> Any:
    if request.method == "OPTIONS":
        return options_mcp()
    if request.method in {"GET", "HEAD"}:
        print("Retell/MCP discovery on /api/retell/function", flush=True)
        return json_mcp(discovery_payload())
    raw = await request.body()
    if config.VERIFY_RETELL_SIGNATURE and config.RETELL_API_KEY:
        signature = request.headers.get("x-retell-signature")
        if signature and not verify_retell_signature(raw, signature):
            raise HTTPException(status_code=401, detail="Invalid Retell signature.")
    try:
        payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
    if payload == {} or payload is None:
        print("Retell probed /api/retell/function with an empty body → tool catalog.", flush=True)
        return json_mcp(discovery_payload())
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required.")
    if payload.get("jsonrpc") or payload.get("method"):
        print(
            "Retell sent MCP JSON-RPC to /api/retell/function. Serving tools anyway. "
            "Prefer the MCP URL ending in /mcp.",
            flush=True,
        )
        reply = handle_jsonrpc(payload, runtime, allow_call=_token_ok_request(request))
        if reply is None:
            return Response(status_code=204, headers=CORS_HEADERS)
        return json_mcp(reply)
    print("Retell custom function keys:", sorted(payload.keys()), flush=True)
    name, args = _extract_tool_call(payload, None)
    try:
        return dispatch_tool(runtime, name, args)
    except Exception as exc:
        return _tool_error(exc)


@app.post("/api/retell/function/{name}")
async def retell_named_function(name: str, request: Request) -> Any:
    raw = await request.body()
    if config.VERIFY_RETELL_SIGNATURE and config.RETELL_API_KEY:
        signature = request.headers.get("x-retell-signature")
        if signature and not verify_retell_signature(raw, signature):
            raise HTTPException(status_code=401, detail="Invalid Retell signature.")
    try:
        payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    _, args = _extract_tool_call(payload, name)
    try:
        return dispatch_tool(runtime, name, args)
    except Exception as exc:
        return _tool_error(exc)
