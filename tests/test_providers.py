from core.providers.time import TimeProvider


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
