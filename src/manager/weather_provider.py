import json
import time
from pathlib import Path

import requests


IP_API_URL = (
    "http://ip-api.com/json/"
    "?fields=status,message,country,regionName,city,lat,lon"
)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


class CityNotFound(Exception):
    """手填城市在地理编码服务里查无结果。"""

WEATHER_CODES = {
    0: "晴朗",
    1: "晴朗",
    2: "少云",
    3: "阴",
    45: "有雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨",
    81: "阵雨",
    82: "强阵雨",
    95: "雷雨",
    96: "雷雨冰雹",
    99: "雷雨冰雹",
}

FALLBACK = {
    "city": "北京",
    "cityFull": "北京市",
    "temp": "18°",
    "desc": "多云",
    "hi": "↑ 21°",
    "lo": "↓ 12°",
    "humidity": "63%",
}


def _round_degree(value):
    return f"{round(float(value))}°"


class WeatherProvider:
    """共享天气数据提供器:IP 定位 + Open-Meteo 当前天气 + 本地缓存。"""

    def __init__(self, session=None, cache_path=None, ttl_seconds=1800, timeout=6,
                 settings=None):
        self.session = session or requests.Session()
        self.cache_path = Path(cache_path) if cache_path else (
            Path.home() / ".config" / "deepin-widgets" / "weather.json")
        self.ttl_seconds = ttl_seconds
        self.timeout = timeout
        # 返回 {"autoLocate": bool, "city": str};默认自动定位、无手填城市
        self._settings = settings or (lambda: {"autoLocate": True, "city": ""})
        # 最近一次取数状态:ok / notfound / disabled / fallback,供 UI 反馈
        self.last_status = "idle"

    @staticmethod
    def _key(auto, city):
        """缓存键:自动定位=ip;否则按城市;关定位且无城市=none。换源即换键,旧缓存失效。"""
        if auto:
            return "ip"
        return "city:" + city.lower() if city else "none"

    def current(self):
        prefs = self._settings() or {}
        auto = bool(prefs.get("autoLocate", True))
        city = str(prefs.get("city") or "").strip()
        key = self._key(auto, city)

        cached = self._load_cache()
        fresh = cached and time.time() - cached.get("_fetchedAt", 0) < self.ttl_seconds
        key_ok = cached and cached.get("_key", key) == key  # 无 _key 视为旧版缓存,放行
        if fresh and key_ok:
            self.last_status = "ok"
            return self._public(cached)
        try:
            if auto:
                location = self._locate()
            elif city:
                location = self._geocode(city)
            else:
                # 关闭自动定位且未填城市:不联网
                self.last_status = "disabled"
                return self._public(cached) if key_ok else dict(FALLBACK)
            weather = self._fetch_weather(location["lat"], location["lon"])
            data = self._build(location, weather)
            data["_key"] = key
            self._save_cache(data)
            self.last_status = "ok"
            return self._public(data)
        except CityNotFound:
            self.last_status = "notfound"
            return self._public(cached) if key_ok else dict(FALLBACK)
        except Exception:
            self.last_status = "fallback"
            if key_ok:
                return self._public(cached)
            return dict(FALLBACK)

    def _locate(self):
        resp = self.session.get(IP_API_URL, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise RuntimeError(data.get("message") or "ip location failed")
        return {
            "city": str(data.get("city") or ""),
            "region": str(data.get("regionName") or ""),
            "country": str(data.get("country") or ""),
            "lat": float(data["lat"]),
            "lon": float(data["lon"]),
        }

    def _geocode(self, city):
        resp = self.session.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "zh", "format": "json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        results = (resp.json() or {}).get("results") or []
        if not results:
            raise CityNotFound(city)
        r = results[0]
        return {
            "city": str(r.get("name") or city),
            "region": str(r.get("admin1") or ""),
            "country": str(r.get("country") or ""),
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
        }

    def _fetch_weather(self, lat, lon):
        resp = self.session.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "forecast_days": 1,
                "timezone": "auto",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _build(self, location, weather):
        current = weather.get("current") or {}
        daily = weather.get("daily") or {}
        highs = daily.get("temperature_2m_max") or []
        lows = daily.get("temperature_2m_min") or []
        city = location["city"] or location["region"] or location["country"] or "当前位置"
        region = location["region"]
        city_full = city if not region or region == city else f"{city}, {region}"
        return {
            "city": city,
            "cityFull": city_full,
            "temp": _round_degree(current.get("temperature_2m", 0)),
            "desc": WEATHER_CODES.get(int(current.get("weather_code", 3)), "多云"),
            "hi": "↑ " + _round_degree(highs[0] if highs else current.get("temperature_2m", 0)),
            "lo": "↓ " + _round_degree(lows[0] if lows else current.get("temperature_2m", 0)),
            "humidity": f"{round(float(current.get('relative_humidity_2m', 0)))}%",
        }

    def _load_cache(self):
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _save_cache(self, data):
        payload = dict(data)
        payload["_fetchedAt"] = time.time()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    @staticmethod
    def _public(data):
        return {k: data.get(k, FALLBACK[k]) for k in FALLBACK}
