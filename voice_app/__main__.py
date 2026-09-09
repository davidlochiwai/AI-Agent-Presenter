from __future__ import annotations

import argparse
import threading
import time

import httpx
import uvicorn

from voice_app import config
from voice_app.window_layout import arrange_app_window, launch_presenter_app, presenter_layout


def _open_presenter_window() -> None:
    url = f"http://127.0.0.1:{config.APP_PORT}/"
    for _ in range(80):
        try:
            if httpx.get(f"http://127.0.0.1:{config.APP_PORT}/health", timeout=1.0).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.25)
    else:
        print("Presenter window was not opened because the local app did not become ready.", flush=True)
        return
    try:
        bounds = presenter_layout(config.PRESENTER_SLIDE_RATIO).app
        result = launch_presenter_app(url, bounds)
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    if result.get("ok"):
        arranged: dict[str, object] = {"ok": False}
        for _ in range(20):
            time.sleep(0.25)
            arranged = arrange_app_window(bounds)
            if arranged.get("ok"):
                break
        if arranged.get("ok"):
            print("Opened AIRA Presenter on the right side of the primary monitor.", flush=True)
        else:
            print(
                "Opened AIRA Presenter, but Windows did not confirm its final position.",
                flush=True,
            )
    else:
        print(
            f"Could not open the presenter window automatically: {result.get('error')}. "
            f"Open {url} manually.",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AIRA presenter web application.")
    parser.add_argument(
        "--presenter-window",
        action="store_true",
        help="Open a dedicated Edge app window on the right side of the primary monitor.",
    )
    args = parser.parse_args()
    print(f"Open the UI at http://127.0.0.1:{config.APP_PORT}")
    if args.presenter_window and config.PRESENTER_SPLIT_LAYOUT:
        threading.Thread(
            target=_open_presenter_window,
            daemon=True,
            name="presenter-window-launcher",
        ).start()
    uvicorn.run(
        "voice_app.app:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
