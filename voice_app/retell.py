from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx

from voice_app import config


def verify_retell_signature(raw_body: bytes | str, signature: str | None) -> bool:
    if not signature or not config.RETELL_API_KEY:
        return False
    payload = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body
    digest = hmac.new(
        config.RETELL_API_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, signature)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.RETELL_API_KEY}",
        "Content-Type": "application/json",
    }


def list_voice_agents() -> list[dict[str, str]]:
    if not config.RETELL_API_KEY:
        return []
    try:
        response = httpx.post(
            "https://api.retellai.com/v2/list-agents?limit=50",
            headers=_headers(),
            json={"filter_criteria": {"channel": {"type": "string", "op": "eq", "value": "voice"}}},
            timeout=20.0,
        )
        if response.status_code >= 400:
            return []
        items = response.json().get("items") or []
        out: list[dict[str, str]] = []
        for item in items:
            if isinstance(item, dict) and item.get("agent_id"):
                out.append(
                    {
                        "agent_id": str(item["agent_id"]),
                        "agent_name": str(item.get("agent_name") or item["agent_id"]),
                    }
                )
        return out
    except Exception:
        return []


END_CALL_DESCRIPTION = (
    "End the call ONLY if the user clearly says goodbye, stop, hang up, 拜拜, or 收线. "
    "This is a live PowerPoint session. Never call end_call after changing slides. "
    "Never call end_call in the same turn as a question. Stay on the line until they dismiss you."
)


def get_agent() -> dict[str, Any]:
    if not config.RETELL_API_KEY or not config.RETELL_AGENT_ID:
        raise RuntimeError("RETELL_API_KEY or RETELL_AGENT_ID is missing.")
    response = httpx.get(
        f"https://api.retellai.com/get-agent/{config.RETELL_AGENT_ID}",
        headers=_headers(),
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"get-agent failed ({response.status_code}): {response.text[:500]}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("get-agent returned an unexpected body.")
    return data


def get_llm(llm_id: str, version: int | None = None) -> dict[str, Any]:
    params = {"version": version} if version is not None else None
    response = httpx.get(
        f"https://api.retellai.com/get-retell-llm/{llm_id}",
        headers=_headers(),
        params=params,
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"get-retell-llm failed ({response.status_code}): {response.text[:500]}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("get-retell-llm returned an unexpected body.")
    return data


def get_call(call_id: str) -> dict[str, Any]:
    response = httpx.get(
        f"https://api.retellai.com/v2/get-call/{call_id}",
        headers=_headers(),
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"get-call failed ({response.status_code}): {response.text[:500]}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("get-call returned an unexpected body.")
    return data


def summarize_call(call: dict[str, Any]) -> dict[str, Any]:
    turns = call.get("transcript_with_tool_calls") or []
    tool_invocations: list[dict[str, Any]] = []
    if isinstance(turns, list):
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            role = str(turn.get("role") or "")
            if "tool" in role or turn.get("name"):
                if role in {"tool_call_invocation", "tool_call_result"} or turn.get("type"):
                    tool_invocations.append(
                        {
                            "role": role,
                            "name": turn.get("name") or turn.get("tool_name"),
                            "arguments": turn.get("arguments"),
                            "content": (turn.get("content") or "")[:400],
                            "type": turn.get("type"),
                        }
                    )
    return {
        "call_id": call.get("call_id"),
        "call_status": call.get("call_status"),
        "disconnection_reason": call.get("disconnection_reason"),
        "duration_ms": call.get("duration_ms"),
        "transcript": call.get("transcript") or "",
        "tool_invocations": tool_invocations,
        "called_end_call": any(item.get("name") == "end_call" for item in tool_invocations),
        "called_presenter_tool": any(
            item.get("name") not in {None, "end_call"} and item.get("role") == "tool_call_invocation"
            for item in tool_invocations
        ),
        "call_analysis": call.get("call_analysis"),
    }


def inspect_agent_tools() -> dict[str, Any]:
    agent = get_agent()
    engine = agent.get("response_engine") or {}
    llm_id = engine.get("llm_id")
    version = engine.get("version")
    llm = get_llm(str(llm_id), version if isinstance(version, int) else None)
    mcps = llm.get("mcps") or []
    tools = llm.get("general_tools") or []
    mcp_url = mcps[0].get("url") if mcps and isinstance(mcps[0], dict) else None
    tool_names = [str(t.get("name")) for t in tools if isinstance(t, dict) and t.get("name")]
    return {
        "agent_id": agent.get("agent_id"),
        "agent_name": agent.get("agent_name"),
        "language": agent.get("language"),
        "llm_id": llm_id,
        "llm_version": version,
        "model": llm.get("model"),
        "begin_message": llm.get("begin_message"),
        "reminder_trigger_ms": agent.get("reminder_trigger_ms"),
        "reminder_max_count": agent.get("reminder_max_count"),
        "mcp_url": mcp_url,
        "mcp_count": len(mcps) if isinstance(mcps, list) else 0,
        "tool_names": tool_names,
        "has_end_call": "end_call" in tool_names,
        "presenter_tool_count": sum(1 for t in tools if isinstance(t, dict) and t.get("type") == "mcp"),
    }


def _looks_like_presenter_prompt(text: str) -> bool:
    lowered = text.lower()
    return "deliver_next" in lowered and "spoken_text" in lowered


def sync_presenter_behavior() -> dict[str, Any]:
    """Keep Reminder trigger short and the Retell prompt from inviting the audience."""
    from voice_app.presenter_prompt import (
        DELIVER_NEXT_DESCRIPTION,
        GENERAL_PROMPT,
        HANDLE_QUESTION_DESCRIPTION,
        PROMPT_MARKER,
    )

    notes: list[str] = []
    agent = get_agent()
    agent_id = str(agent.get("agent_id") or config.RETELL_AGENT_ID)
    agent_patch: dict[str, Any] = {}
    if int(agent.get("reminder_trigger_ms") or 0) != config.RETELL_REMINDER_TRIGGER_MS:
        agent_patch["reminder_trigger_ms"] = config.RETELL_REMINDER_TRIGGER_MS
    if int(agent.get("reminder_max_count") or 0) != config.RETELL_REMINDER_MAX_COUNT:
        agent_patch["reminder_max_count"] = config.RETELL_REMINDER_MAX_COUNT
    if agent.get("enable_backchannel"):
        agent_patch["enable_backchannel"] = False
    if agent_patch:
        response = httpx.patch(
            f"https://api.retellai.com/update-agent/{agent_id}",
            headers=_headers(),
            json=agent_patch,
            timeout=20.0,
        )
        if response.status_code >= 400:
            notes.append(
                f"Could not patch agent reminder ({response.status_code}): {response.text[:240]}"
            )
        else:
            notes.append(
                f"Agent reminder {config.RETELL_REMINDER_TRIGGER_MS}ms × {config.RETELL_REMINDER_MAX_COUNT}; backchannel off."
            )

    engine = agent.get("response_engine") or {}
    llm_id = engine.get("llm_id")
    version = engine.get("version")
    if not llm_id:
        return {"ok": True, "changed": bool(notes), "notes": notes or ["No Retell LLM to patch."]}

    llm = get_llm(str(llm_id), version if isinstance(version, int) else None)
    llm_patch: dict[str, Any] = {}
    current = str(llm.get("general_prompt") or "")
    if PROMPT_MARKER not in current:
        if _looks_like_presenter_prompt(current) or not current.strip():
            llm_patch["general_prompt"] = GENERAL_PROMPT
            notes.append("Updating Retell prompt so the agent reads spoken_text only (no 對嗎 / invite-questions).")
        else:
            notes.append(
                "Retell prompt looks custom. Paste the prompt in docs/RETELL_SETUP.md to stop improvised audience questions."
            )
    elif current.strip() != GENERAL_PROMPT.strip():
        llm_patch["general_prompt"] = GENERAL_PROMPT
        notes.append("Refreshing Retell presenter prompt.")

    desc_map = {
        "deliver_next": DELIVER_NEXT_DESCRIPTION,
        "handle_audience_question": HANDLE_QUESTION_DESCRIPTION,
    }
    tools = llm.get("general_tools") or []
    new_tools: list[dict[str, Any]] = []
    tools_changed = False
    if isinstance(tools, list):
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            item = dict(tool)
            name = str(item.get("name") or "")
            wanted = desc_map.get(name)
            if wanted and str(item.get("description") or "").strip() != wanted.strip():
                item["description"] = wanted
                tools_changed = True
                notes.append(f"Updated {name} description.")
            new_tools.append(item)
    if tools_changed:
        llm_patch["general_tools"] = new_tools

    if llm_patch:
        params = {"version": version} if isinstance(version, int) else None
        response = httpx.patch(
            f"https://api.retellai.com/update-retell-llm/{llm_id}",
            headers=_headers(),
            params=params,
            json=llm_patch,
            timeout=30.0,
        )
        if response.status_code >= 400 and "general_tools" in llm_patch:
            llm_patch.pop("general_tools")
            if llm_patch:
                response = httpx.patch(
                    f"https://api.retellai.com/update-retell-llm/{llm_id}",
                    headers=_headers(),
                    params=params,
                    json=llm_patch,
                    timeout=30.0,
                )
        if response.status_code >= 400:
            notes.append(
                f"Could not patch Retell LLM ({response.status_code}): {response.text[:240]}"
            )
            return {"ok": False, "changed": False, "notes": notes, "error": notes[-1]}

    return {
        "ok": True,
        "changed": bool(notes),
        "notes": notes or ["Presenter voice settings already match."],
    }


def sync_director_function_endpoints(base_url: str) -> dict[str, Any]:
    """Point Retell's scripted presenter functions at the Python director."""
    base = (base_url or "").rstrip("/")
    if not base:
        return {"ok": False, "changed": False, "error": "DIRECTOR_PUBLIC_URL is empty."}
    if not config.DIRECTOR_WEBHOOK_TOKEN:
        return {"ok": False, "changed": False, "error": "DIRECTOR_WEBHOOK_TOKEN is empty."}

    agent = get_agent()
    engine = agent.get("response_engine") or {}
    llm_id = engine.get("llm_id")
    version = engine.get("version")
    if not llm_id:
        return {"ok": False, "changed": False, "error": "The Retell agent has no LLM to update."}
    llm = get_llm(str(llm_id), version if isinstance(version, int) else None)
    tools = llm.get("general_tools") or []
    if not isinstance(tools, list):
        return {"ok": False, "changed": False, "error": "Retell returned no general_tools list."}

    targets = {
        "deliver_next": f"{base}/webhook/presenter/deliver-next",
        "handle_audience_question": f"{base}/webhook/presenter/handle-question",
    }
    auth = f"Bearer {config.DIRECTOR_WEBHOOK_TOKEN}"
    found: set[str] = set()
    changed = False
    notes: list[str] = []
    new_tools: list[dict[str, Any]] = []

    for tool in tools:
        if not isinstance(tool, dict):
            continue
        item = dict(tool)
        name = str(item.get("name") or "")
        wanted_url = targets.get(name)
        if wanted_url:
            found.add(name)
            if str(item.get("url") or "").rstrip("/") != wanted_url:
                item["url"] = wanted_url
                changed = True
                notes.append(f"Updated {name} URL to the Python director.")
            headers = dict(item.get("headers") or {})
            if headers.get("Authorization") != auth:
                headers["Authorization"] = auth
                item["headers"] = headers
                changed = True
                notes.append(f"Updated {name} webhook authorization.")
            desired = {
                "method": "POST",
                "timeout_ms": 30000,
                "speak_after_execution": True,
                "speak_during_execution": False,
                "max_retry": 0,
            }
            for key, value in desired.items():
                if item.get(key) != value:
                    item[key] = value
                    changed = True
        new_tools.append(item)

    missing = sorted(set(targets) - found)
    if missing:
        return {
            "ok": False,
            "changed": False,
            "error": f"Retell is missing custom function(s): {', '.join(missing)}.",
        }
    if not changed:
        return {
            "ok": True,
            "changed": False,
            "notes": ["Retell director function URLs and authorization already match."],
            "urls": targets,
        }

    params = {"version": version} if isinstance(version, int) else None
    response = httpx.patch(
        f"https://api.retellai.com/update-retell-llm/{llm_id}",
        headers=_headers(),
        params=params,
        json={"general_tools": new_tools},
        timeout=30.0,
    )
    if response.status_code >= 400:
        return {
            "ok": False,
            "changed": False,
            "error": f"Could not update Retell director functions ({response.status_code}): {response.text[:400]}",
        }
    return {"ok": True, "changed": True, "notes": notes, "urls": targets}


# Backward-compatible import for older callers during migration.
sync_n8n_function_endpoints = sync_director_function_endpoints


def sync_mcp_endpoint(mcp_url: str) -> dict[str, Any]:
    """Point the agent's saved MCP server at this process's current public URL."""
    info = inspect_agent_tools()
    llm_id = info["llm_id"]
    version = info["llm_version"]
    llm = get_llm(str(llm_id), version if isinstance(version, int) else None)
    mcps = llm.get("mcps") or []
    if not isinstance(mcps, list) or not mcps:
        return {
            "ok": False,
            "error": "This agent has no MCP server. In Retell, add the MCP URL from the local UI, then Add Tools.",
            **info,
        }
    notes: list[str] = []
    new_mcps: list[dict[str, Any]] = []
    for mcp in mcps:
        if not isinstance(mcp, dict):
            continue
        old_url = str(mcp.get("url") or "")
        item: dict[str, Any] = {
            "name": mcp.get("name") or "PowerPoint Presenter",
            "url": mcp_url,
            "headers": mcp.get("headers") or {},
            "query_params": mcp.get("query_params") or {},
            "timeout_ms": int(mcp.get("timeout_ms") or 20000),
        }
        if mcp.get("id"):
            item["id"] = mcp["id"]
        if old_url.rstrip("/") != mcp_url.rstrip("/"):
            notes.append(f"MCP URL {old_url} → {mcp_url}")
        new_mcps.append(item)
    tools = llm.get("general_tools") or []
    new_tools: list[dict[str, Any]] = []
    if isinstance(tools, list):
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            item = dict(tool)
            if item.get("type") == "end_call" or item.get("name") == "end_call":
                if "ONLY if the user clearly" not in str(item.get("description") or ""):
                    item["description"] = END_CALL_DESCRIPTION
                    notes.append("Tightened end_call so it should not hang up after a slide change.")
            new_tools.append(item)
    if not notes:
        return {"ok": True, "changed": False, "notes": ["Retell MCP URL already matches this tunnel."], **info}
    params = {"version": version} if isinstance(version, int) else None
    body: dict[str, Any] = {"mcps": new_mcps}
    if new_tools:
        body["general_tools"] = new_tools
    response = httpx.patch(
        f"https://api.retellai.com/update-retell-llm/{llm_id}",
        headers=_headers(),
        params=params,
        json=body,
        timeout=30.0,
    )
    if response.status_code >= 400:
        slim = []
        for mcp in new_mcps:
            slim.append({"name": mcp["name"], "url": mcp["url"], "headers": mcp.get("headers") or {}})
        response = httpx.patch(
            f"https://api.retellai.com/update-retell-llm/{llm_id}",
            headers=_headers(),
            params=params,
            json={"mcps": slim},
            timeout=30.0,
        )
    if response.status_code >= 400:
        return {
            "ok": False,
            "error": f"Could not update Retell MCP URL ({response.status_code}): {response.text[:400]}",
            **info,
        }
    info["mcp_url"] = mcp_url
    return {"ok": True, "changed": True, "notes": notes, **info}


def create_web_call(dynamic_variables: dict[str, str], metadata: dict[str, Any]) -> dict[str, Any]:
    if not config.RETELL_API_KEY:
        raise RuntimeError("RETELL_API_KEY is missing. Add it to your .env file.")
    if not config.RETELL_AGENT_ID:
        raise RuntimeError("RETELL_AGENT_ID is missing. Add it to your .env file.")
    body: dict[str, Any] = {
        "agent_id": config.RETELL_AGENT_ID,
        "retell_llm_dynamic_variables": dynamic_variables,
        "metadata": metadata,
        "agent_override": {
            "agent": {
                "reminder_trigger_ms": config.RETELL_REMINDER_TRIGGER_MS,
                "reminder_max_count": config.RETELL_REMINDER_MAX_COUNT,
                "responsiveness": 1,
                "interruption_sensitivity": 0.35,
                "enable_backchannel": False,
            },
            "retell_llm": {
                "tool_call_strict_mode": True,
            },
        },
    }
    used_reminder = True
    response = httpx.post(
        "https://api.retellai.com/v2/create-web-call",
        headers=_headers(),
        json=body,
        timeout=30.0,
    )
    if response.status_code >= 400 and "agent_override" in body:
        print(
            f"create-web-call override failed ({response.status_code}); retrying with reminder only.",
            flush=True,
        )
        body["agent_override"] = {
            "agent": {
                "reminder_trigger_ms": config.RETELL_REMINDER_TRIGGER_MS,
                "reminder_max_count": config.RETELL_REMINDER_MAX_COUNT,
                "responsiveness": 1,
                "interruption_sensitivity": 0.35,
                "enable_backchannel": False,
            }
        }
        response = httpx.post(
            "https://api.retellai.com/v2/create-web-call",
            headers=_headers(),
            json=body,
            timeout=30.0,
        )
    if response.status_code >= 400 and "agent_override" in body:
        print(f"create-web-call with reminder override failed ({response.status_code}); retrying without override.", flush=True)
        body.pop("agent_override")
        used_reminder = False
        response = httpx.post(
            "https://api.retellai.com/v2/create-web-call",
            headers=_headers(),
            json=body,
            timeout=30.0,
        )
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = json.dumps(response.json())
        except Exception:
            pass
        if response.status_code == 404:
            names = ", ".join(f"{a['agent_name']} ({a['agent_id']})" for a in list_voice_agents()[:8])
            raise RuntimeError(
                f"Retell agent {config.RETELL_AGENT_ID} was not found on this API key. "
                "Use the Agent ID from the same Retell account as RETELL_API_KEY in this project's .env "
                "(a Windows environment variable can silently override it). "
                f"Voice agents on this key: {names or '(none)'}."
            )
        raise RuntimeError(f"Retell create-web-call failed ({response.status_code}): {detail}")
    if used_reminder:
        print(
            f"Web call reminder: {config.RETELL_REMINDER_TRIGGER_MS}ms × {config.RETELL_REMINDER_MAX_COUNT} "
            "(next beat on silence; no extra recap).",
            flush=True,
        )
    return response.json()
