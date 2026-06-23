from core.providers.time import TimeProvider
from core.providers.system import SystemProvider


def test_time_provider_topics_and_interval():
    p = TimeProvider()
    assert p.id == "time"
    assert p.topics() == ["time.now"]
    assert p.default_interval("time.now") == 1.0


def test_time_provider_poll_shape():
    data = TimeProvider().poll("time.now")
    assert set(data) == {"iso", "epoch", "tz"}
    assert isinstance(data["iso"], str) and "T" in data["iso"]
    assert isinstance(data["epoch"], float)
    assert isinstance(data["tz"], str) and data["tz"]


def test_system_provider_topics_and_intervals():
    p = SystemProvider()
    assert p.id == "system"
    assert p.topics() == ["system.cpu", "system.mem"]
    assert p.default_interval("system.cpu") == 1.0
    assert p.default_interval("system.mem") == 2.0


def test_system_provider_cpu_shape():
    data = SystemProvider().poll("system.cpu")
    assert isinstance(data["percent"], float)
    assert isinstance(data["per_core"], list)
    assert all(isinstance(x, float) for x in data["per_core"])


def test_system_provider_mem_shape():
    data = SystemProvider().poll("system.mem")
    assert isinstance(data["percent"], float)
    assert data["total"] > 0
    assert 0 <= data["used"] <= data["total"]
