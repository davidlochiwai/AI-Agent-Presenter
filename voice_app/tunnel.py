from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

EPHEMERAL_HOST_SUFFIXES = (
    ".trycloudflare.com",
    ".ngrok-free.app",
    ".ngrok.io",
    ".ngrok.app",
)

CLOUDFLARED_QUICK_TUNNEL_PATTERN = (
    r"https://[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com"
)


@dataclass
class TunnelInfo:
    public_url: str
    provider: str
    process: subprocess.Popen[str] | None = None

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()


def is_ephemeral_public_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host.endswith(suffix) for suffix in EPHEMERAL_HOST_SUFFIXES)


def probe_public_origin(base_url: str, timeout: float = 8.0) -> bool:
    """True when this process is reachable at base_url/health (not a dead tunnel hostname)."""
    url = base_url.rstrip("/") + "/health"
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        if response.status_code != 200:
            return False
        data = response.json()
        return data.get("ok") is True and data.get("service") == "ai-agent-presenter"
    except Exception:
        return False


def wait_until_public(base_url: str, attempts: int = 8, delay_s: float = 1.0) -> bool:
    for _ in range(attempts):
        if probe_public_origin(base_url):
            return True
        time.sleep(delay_s)
    return False


def start_tunnel(local_port: int) -> TunnelInfo | None:
    if shutil.which("cloudflared"):
        return _cloudflared(local_port)
    if shutil.which("ngrok"):
        return _ngrok(local_port)
    return None


def _cloudflared(local_port: int) -> TunnelInfo:
    proc = subprocess.Popen(
        [
            "cloudflared",
            "tunnel",
            "--url",
            f"http://127.0.0.1:{local_port}",
            "--no-autoupdate",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    # cloudflared also logs links such as https://api.trycloudflare.com.
    # A quick-tunnel hostname contains multiple generated words separated by
    # hyphens; accepting the API hostname points Retell at a dead endpoint.
    url = _wait_for_url(proc, CLOUDFLARED_QUICK_TUNNEL_PATTERN)
    return TunnelInfo(public_url=url, provider="cloudflared", process=proc)


def _ngrok(local_port: int) -> TunnelInfo:
    proc = subprocess.Popen(
        ["ngrok", "http", str(local_port), "--log", "stdout", "--log-format", "logfmt"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    url = _wait_for_url(
        proc,
        r"https://[a-z0-9-]+\.ngrok-free\.app|https://[a-z0-9-]+\.ngrok\.io",
    )
    return TunnelInfo(public_url=url, provider="ngrok", process=proc)


def _wait_for_url(proc: subprocess.Popen[str], pattern: str, timeout_s: float = 25.0) -> str:
    matched: list[str] = []
    done = threading.Event()

    def _read() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            found = re.search(pattern, line)
            if found:
                matched.append(found.group(0))
                done.set()

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    if not done.wait(timeout_s):
        proc.terminate()
        raise RuntimeError(
            "Could not read a public tunnel URL. Set PUBLIC_BASE_URL in .env "
            "or install cloudflared and retry."
        )
    return matched[0]
