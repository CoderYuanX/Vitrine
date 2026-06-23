from datetime import datetime

from core.providers.base import Provider


class TimeProvider(Provider):
    id = "time"

    def topics(self) -> list[str]:
        return ["time.now"]

    def default_interval(self, topic: str) -> float:
        return 1.0

    def poll(self, topic: str) -> dict:
        now = datetime.now().astimezone()
        return {
            "iso": now.isoformat(),
            "epoch": now.timestamp(),
            "tz": now.tzname() or "",
        }
