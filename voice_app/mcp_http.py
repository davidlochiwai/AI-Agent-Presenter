"""JSON MCP endpoint for Retell (no streaming).

Retell's Add Tools UI hangs on Streamable HTTP / SSE servers. It expects a
quick JSON body with capabilities + tools (and JSON-RPC for initialize /
tools/list / tools/call).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from voice_app.runtime import PresenterRuntime
from voice_app.tools import TOOL_SPECS, dispatch_tool

PROTOCOL_VERSION = "2024-11-05"
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
}


def catalog() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        schema = spec.get("parameters") or {"type": "object", "properties": {}}
        tools.append(
            {
                "name": spec["name"],
                "description": spec["description"],
                "inputSchema": schema,
                "input_schema": schema,
            }
        )
    return tools


def discovery_payload() -> dict[str, Any]:
    return {
        "capabilities": {"tools": True},
        "tools": catalog(),
        "serverInfo": {"name": "PowerPoint Presenter", "version": "0.1.0"},
    }


def json_mcp(payload: dict[str, Any] | list[Any], status: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status, headers=CORS_HEADERS)


def options_mcp() -> Response:
    return Response(status_code=204, headers=CORS_HEADERS)


def _rpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_jsonrpc(
    message: dict[str, Any],
    runtime: PresenterRuntime,
    allow_call: bool,
) -> dict[str, Any] | None:
    method = str(message.get("method") or "")
    req_id = message.get("id")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    print(f"MCP JSON-RPC method={method!r} id={req_id!r}", flush=True)
    runtime.events.publish({"type": "mcp", "method": method, "detail": str(req_id or "")})

    if method in {"notifications/initialized", "notifications/cancelled"} or (
        method.startswith("notifications/") and req_id is None
    ):
        return None

    if method == "initialize":
        requested = params.get("protocolVersion") or PROTOCOL_VERSION
        return _rpc_result(
            req_id,
            {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "PowerPoint Presenter", "version": "0.1.0"},
            },
        )

    if method in {"tools/list", "list_tools"}:
        return _rpc_result(req_id, {"tools": catalog()})

    if method == "ping":
        return _rpc_result(req_id, {})

    if method in {"tools/call", "call_tool"}:
        if not allow_call:
            return _rpc_error(req_id, -32001, "Unauthorized. Send the Bearer token from the local UI.")
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if not name:
            return _rpc_error(req_id, -32602, "Tool name is required.")
        try:
            result = dispatch_tool(runtime, name, arguments)
            text = json.dumps(result, ensure_ascii=False)
            return _rpc_result(
                req_id,
                {"content": [{"type": "text", "text": text}], "isError": False, "structuredContent": result},
            )
        except Exception as exc:
            return _rpc_result(
                req_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )

    return _rpc_error(req_id, -32601, f"Unknown method: {method}")


async def handle_mcp(request: Request, runtime: PresenterRuntime, allow_call: bool = False) -> Response:
    client = request.client.host if request.client else "?"
    accept = request.headers.get("accept") or ""
    print(
        f"MCP {request.method} {request.url.path} from {client} accept={accept!r}",
        flush=True,
    )
    if request.method == "OPTIONS":
        return options_mcp()
    if request.method in {"GET", "HEAD", "DELETE"}:
        print(f"MCP {request.method} discovery", flush=True)
        if request.method == "DELETE":
            return Response(status_code=204, headers=CORS_HEADERS)
        return json_mcp(discovery_payload())

    raw = await request.body()
    if not raw:
        print("MCP POST empty body → discovery", flush=True)
        return json_mcp(discovery_payload())
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return json_mcp({"error": "Invalid JSON"}, status=400)

    if isinstance(payload, list):
        replies = []
        for item in payload:
            if isinstance(item, dict):
                reply = handle_jsonrpc(item, runtime, allow_call)
                if reply is not None:
                    replies.append(reply)
        return json_mcp(replies)

    if not isinstance(payload, dict):
        return json_mcp(discovery_payload())

    if "jsonrpc" in payload or "method" in payload:
        reply = handle_jsonrpc(payload, runtime, allow_call)
        if reply is None:
            return Response(status_code=204, headers=CORS_HEADERS)
        return json_mcp(reply)

    print("MCP POST keys:", sorted(payload.keys()), flush=True)
    return json_mcp(discovery_payload())
