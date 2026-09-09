from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class EventBus:
    """Fan-out live events to SSE subscribers (UI tool-call log)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            listeners = list(self._subscribers)
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                continue
