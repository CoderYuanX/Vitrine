from manager.weather_provider import WeatherProvider


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected request")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_fetch_current_weather_from_ip_location(tmp_path):
    session = _Session([
        _Resp({
            "status": "success",
            "city": "Beijing",
            "regionName": "Beijing",
            "country": "China",
            "lat": 39.9,
            "lon": 116.4,
        }),
        _Resp({
            "current": {
                "temperature_2m": 26.4,
                "relative_humidity_2m": 61,
                "weather_code": 1,
            },
            "daily": {
                "temperature_2m_max": [31.2],
                "temperature_2m_min": [20.5],
            },
        }),
    ])
    provider = WeatherProvider(session=session, cache_path=tmp_path / "weather.json")

    data = provider.current()

    assert data["city"] == "Beijing"
    assert data["cityFull"] == "Beijing"
    assert data["temp"] == "26°"
    assert data["desc"] == "晴朗"
    assert data["hi"] == "↑ 31°"
    assert data["lo"] == "↓ 20°"
    assert data["humidity"] == "61%"
    assert "ip-api.com" in session.calls[0][0]
    assert "api.open-meteo.com" in session.calls[1][0]
    assert session.calls[1][1]["params"]["latitude"] == 39.9
    assert session.calls[1][1]["params"]["longitude"] == 116.4


def test_uses_recent_cache_without_network(tmp_path):
    cache = tmp_path / "weather.json"
    provider = WeatherProvider(cache_path=cache)
    provider._save_cache({
        "city": "上海",
        "cityFull": "上海市",
        "temp": "22°",
        "desc": "多云",
        "hi": "↑ 26°",
        "lo": "↓ 18°",
        "humidity": "70%",
    })
    session = _Session([])
    provider = WeatherProvider(session=session, cache_path=cache)

    assert provider.current()["city"] == "上海"
    assert session.calls == []


def test_manual_city_geocodes_then_fetches(tmp_path):
    session = _Session([
        _Resp({"results": [{
            "name": "上海", "admin1": "上海市", "country": "中国",
            "latitude": 31.23, "longitude": 121.47,
        }]}),
        _Resp({
            "current": {"temperature_2m": 22.1, "relative_humidity_2m": 70, "weather_code": 2},
            "daily": {"temperature_2m_max": [25.0], "temperature_2m_min": [18.0]},
        }),
    ])
    provider = WeatherProvider(
        session=session, cache_path=tmp_path / "w.json",
        settings=lambda: {"autoLocate": False, "city": "上海"},
    )

    data = provider.current()

    assert data["city"] == "上海"
    assert data["temp"] == "22°"
    # 走地理编码,不走 ip 定位
    assert "geocoding-api.open-meteo.com" in session.calls[0][0]
    assert all("ip-api.com" not in c[0] for c in session.calls)


def test_status_ok_when_city_found(tmp_path):
    session = _Session([
        _Resp({"results": [{"name": "上海", "admin1": "上海市", "country": "中国",
                            "latitude": 31.2, "longitude": 121.5}]}),
        _Resp({"current": {"temperature_2m": 22, "relative_humidity_2m": 70, "weather_code": 2},
               "daily": {"temperature_2m_max": [25], "temperature_2m_min": [18]}}),
    ])
    provider = WeatherProvider(session=session, cache_path=tmp_path / "w.json",
                               settings=lambda: {"autoLocate": False, "city": "上海"})
    provider.current()
    assert provider.last_status == "ok"


def test_status_notfound_for_unknown_city(tmp_path):
    session = _Session([_Resp({"results": []})])  # 地理编码无结果
    provider = WeatherProvider(session=session, cache_path=tmp_path / "w.json",
                               settings=lambda: {"autoLocate": False, "city": "qwertyxyz"})
    data = provider.current()
    assert provider.last_status == "notfound"
    assert data["city"] == "北京"  # 无缓存 → FALLBACK


def test_status_disabled_when_no_city(tmp_path):
    provider = WeatherProvider(session=_Session([]), cache_path=tmp_path / "w.json",
                               settings=lambda: {"autoLocate": False, "city": ""})
    provider.current()
    assert provider.last_status == "disabled"


def test_disabled_without_city_skips_network(tmp_path):
    provider = WeatherProvider(
        session=_Session([RuntimeError("不应联网")]),
        cache_path=tmp_path / "w.json",
        settings=lambda: {"autoLocate": False, "city": ""},
    )
    data = provider.current()
    assert data["city"] == "北京"          # FALLBACK
    assert provider.session.calls == []     # 完全没联网


def test_falls_back_to_stale_cache_when_network_fails(tmp_path):
    cache = tmp_path / "weather.json"
    provider = WeatherProvider(cache_path=cache, ttl_seconds=0)
    provider._save_cache({
        "city": "广州",
        "cityFull": "广州市",
        "temp": "30°",
        "desc": "阴",
        "hi": "↑ 33°",
        "lo": "↓ 25°",
        "humidity": "80%",
    })
    provider = WeatherProvider(
        session=_Session([RuntimeError("offline")]),
        cache_path=cache,
        ttl_seconds=0,
    )

    assert provider.current()["city"] == "广州"
