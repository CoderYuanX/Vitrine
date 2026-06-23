import psutil

from core.providers.base import Provider

_INTERVALS = {"system.cpu": 1.0, "system.mem": 2.0}


class SystemProvider(Provider):
    id = "system"

    def topics(self) -> list[str]:
        return ["system.cpu", "system.mem"]

    def default_interval(self, topic: str) -> float:
        return _INTERVALS[topic]

    def poll(self, topic: str) -> dict:
        if topic == "system.cpu":
            return {
                "percent": float(psutil.cpu_percent(interval=None)),
                "per_core": [float(x) for x in psutil.cpu_percent(interval=None, percpu=True)],
            }
        if topic == "system.mem":
            vm = psutil.virtual_memory()
            return {"percent": float(vm.percent), "used": int(vm.used), "total": int(vm.total)}
        raise ValueError(f"unknown topic: {topic}")
