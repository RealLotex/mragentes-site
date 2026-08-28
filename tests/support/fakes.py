from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class FakeClock:
    current: datetime = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, *, seconds: int) -> datetime:
        self.current += timedelta(seconds=seconds)
        return self.current


@dataclass
class FakeResponse:
    status_code: int = 200
    json_data: Any = field(default_factory=dict)
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        return self.json_data


@dataclass
class FakeTransport:
    responses: list[FakeResponse]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError("fake transport has no queued response")
        return self.responses.pop(0)
