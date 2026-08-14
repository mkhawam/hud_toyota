"""Async pub/sub event bus.

Providers publish values to dot-separated topics (``vehicle.speed_kph``,
``alert.raised``); consumers subscribe by exact topic, prefix wildcard
(``vehicle.*``), or ``*``. The bus keeps a last-value cache so late
subscribers (a WebSocket client connecting mid-drive) can be primed with
current state.

Slow consumers never block publishers: each subscription has a bounded
queue and the oldest message is dropped on overflow — for telemetry the
latest value always wins.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass(frozen=True)
class Message:
    topic: str
    value: Any
    ts: float  # unix seconds, stamped at publish


def topic_matches(pattern: str, topic: str) -> bool:
    if pattern == "*" or pattern == topic:
        return True
    if pattern.endswith(".*"):
        return topic.startswith(pattern[:-1])  # keep the dot: "vehicle."
    return False


class Subscription:
    """Async iterator over messages matching one or more patterns."""

    def __init__(self, patterns: tuple[str, ...], maxsize: int) -> None:
        self.patterns = patterns
        self._queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=maxsize)
        self._closed = False

    def _deliver(self, msg: Message) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(msg)
        except asyncio.QueueFull:
            # Drop the oldest message; the fresh value matters more.
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(msg)

    def matches(self, topic: str) -> bool:
        return any(topic_matches(p, topic) for p in self.patterns)

    def __aiter__(self) -> AsyncIterator[Message]:
        return self

    async def __anext__(self) -> Message:
        if self._closed and self._queue.empty():
            raise StopAsyncIteration
        return await self._queue.get()

    def close(self) -> None:
        self._closed = True


@dataclass
class Bus:
    _subs: set[Subscription] = field(default_factory=set)
    _last: dict[str, Message] = field(default_factory=dict)

    def publish(self, topic: str, value: Any) -> None:
        msg = Message(topic=topic, value=value, ts=time.time())
        self._last[topic] = msg
        for sub in self._subs:
            if sub.matches(topic):
                sub._deliver(msg)

    def subscribe(
        self,
        *patterns: str,
        maxsize: int = 256,
        replay: bool = False,
    ) -> Subscription:
        """Subscribe to topics. With ``replay=True`` the last cached value of
        every matching topic is delivered immediately (priming)."""
        sub = Subscription(patterns or ("*",), maxsize=maxsize)
        self._subs.add(sub)
        if replay:
            for msg in self._last.values():
                if sub.matches(msg.topic):
                    sub._deliver(msg)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        sub.close()
        self._subs.discard(sub)

    def snapshot(self, pattern: str = "*") -> dict[str, Message]:
        """Last known value per topic — used to prime new WebSocket clients."""
        return {t: m for t, m in self._last.items() if topic_matches(pattern, t)}
