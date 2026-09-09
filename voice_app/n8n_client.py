"""Tell n8n Cloud that a live session started so it can store the tunnel URL."""

from __future__ import annotations

from typing import Any

import httpx

from voice_app import config


def _webhook_headers() -> dict[str, str]:
    if not config.N8N_WEBHOOK_TOKEN:
        return {}
    return {"Authorization": f"Bearer {config.N8N_WEBHOOK_TOKEN}"}


def notify_session(payload: dict[str, Any]) -> dict[str, Any]:
    url = config.N8N_SESSION_WEBHOOK_URL
    if not url:
        return {"ok": False, "skipped": True, "reason": "N8N_SESSION_WEBHOOK_URL is empty."}
    try:
        response = httpx.post(url, headers=_webhook_headers(), json=payload, timeout=8.0)
        text = response.text[:400]
        if response.status_code >= 400:
            return {"ok": False, "status": response.status_code, "body": text}
        return {"ok": True, "status": response.status_code, "body": text}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def call_deliver_next(bridge_url: str = "", dry: bool = False) -> dict[str, Any]:
    url = config.n8n_deliver_next_url()
    if not url:
        return {
            "ok": False,
            "error": "Set N8N_SESSION_WEBHOOK_URL (…/presenter/session) or N8N_DELIVER_NEXT_WEBHOOK_URL.",
        }
    try:
        response = httpx.post(
            url,
            headers=_webhook_headers(),
            json={
                "bridge_url": bridge_url,
                "dry": dry,
                "source": "console",
                "bridge_token": config.PRESENTER_TOOL_TOKEN,
                "slide_pause_ms": config.SLIDE_PAUSE_MS,
            },
            timeout=20.0,
        )
        text = response.text[:1500]
        try:
            body: Any = response.json()
        except Exception:
            body = text
        empty = body in ("", None, {}, [])
        hint = ""
        if response.is_success and empty:
            hint = (
                "n8n returned HTTP 200 with an empty body. The Webhook node is almost certainly "
                "set to Respond Immediately (the n8n default). Open Webhook deliver-next → "
                "Respond → Using Last Node Output → First Entry JSON. Publish again. "
                "Also confirm Executions actually ran 'Next beat' and 'POST slide bridge'."
            )
        return {
            "ok": response.is_success and not empty,
            "status": response.status_code,
            "url": url,
            "body": body,
            "empty_body": empty,
            "hint": hint,
        }
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def notify_speech_done() -> dict[str, Any]:
    """Tell n8n the agent finished speaking so the next deliver_next may flip."""
    url = config.n8n_deliver_next_url()
    if not url:
        return {"ok": False, "skipped": True, "reason": "No deliver-next webhook URL."}
    try:
        response = httpx.post(
            url,
            headers=_webhook_headers(),
            json={"event": "speech_done", "source": "speech"},
            timeout=8.0,
        )
        return {
            "ok": response.is_success,
            "status": response.status_code,
            "body": response.text[:240],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
