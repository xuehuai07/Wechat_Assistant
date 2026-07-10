from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "晴",
    1: "大致晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨",
    81: "强阵雨",
    82: "暴雨",
    95: "雷暴",
    96: "伴有冰雹的雷暴",
    99: "强冰雹雷暴",
}
WEATHER_MARKERS = ("天气", "气温", "温度", "下雨", "降雨", "降雪", "刮风", "风力")
LOCATION_NOISE = (
    "天气预报",
    "天气",
    "气温",
    "温度",
    "怎么样",
    "如何",
    "怎样",
    "帮我",
    "帮忙",
    "查询",
    "查一下",
    "查查",
    "一下",
    "请问",
    "今天",
    "明天",
    "后天",
    "未来三天",
    "未来3天",
    "未来",
    "的",
)


class WeatherError(RuntimeError):
    """A safe error for failures from the public weather provider."""


class LocationNotFoundError(WeatherError):
    """No location could be resolved from a user-provided city name."""


@dataclass(frozen=True)
class WeatherRequest:
    location: str | None
    day_offset: int


def parse_weather_request(message: str) -> WeatherRequest | None:
    """Recognize simple Chinese weather requests without asking the model to invent a tool call."""

    text = message.strip()
    if not text or not any(marker in text for marker in WEATHER_MARKERS):
        return None
    day_offset = 2 if "后天" in text else 1 if "明天" in text else 0
    location = text
    for noise in LOCATION_NOISE:
        location = location.replace(noise, "")
    location = re.sub(r"[，。！？、,.!?？\s]", "", location)
    return WeatherRequest(location=location or None, day_offset=day_offset)


class OpenMeteoWeatherService:
    def __init__(self, *, timeout_seconds: float = 12, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def weather(self, location: str, *, day_offset: int = 0) -> dict[str, Any]:
        if not location or len(location.strip()) < 2:
            raise LocationNotFoundError("请提供至少两个字符的城市或地点名称")
        if not 0 <= day_offset <= 6:
            raise WeatherError("天气预报日期超出可查询范围")
        place = await self._geocode(location.strip())
        payload = await self._request_forecast(place["latitude"], place["longitude"], day_offset)
        return self._normalize(place, payload, day_offset)

    async def _geocode(self, location: str) -> dict[str, Any]:
        payload = await self._get_json(
            GEOCODING_URL,
            {"name": location, "count": 1, "language": "zh", "format": "json"},
        )
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            raise LocationNotFoundError(f"未找到地点：{location}")
        result = results[0]
        try:
            float(result["latitude"])
            float(result["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherError("天气服务返回的地点数据无效") from exc
        return result

    async def _request_forecast(self, latitude: Any, longitude: Any, day_offset: int) -> dict[str, Any]:
        forecast_days = max(3, day_offset + 1)
        return await self._get_json(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
                "timezone": "auto",
                "forecast_days": forecast_days,
            },
        )

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise WeatherError("天气服务请求超时") from exc
        except httpx.HTTPError as exc:
            raise WeatherError("天气服务暂时不可用") from exc
        except ValueError as exc:
            raise WeatherError("天气服务返回了无效数据") from exc
        if not isinstance(payload, dict) or payload.get("error"):
            raise WeatherError("天气服务未返回可用数据")
        return payload

    @staticmethod
    def _normalize(place: dict[str, Any], payload: dict[str, Any], day_offset: int) -> dict[str, Any]:
        daily = payload.get("daily")
        if not isinstance(daily, dict):
            raise WeatherError("天气服务缺少每日预报")
        try:
            day = {
                "date": daily["time"][day_offset],
                "weather": WEATHER_CODES.get(int(daily["weather_code"][day_offset]), "未知天气"),
                "temperature_max_c": daily["temperature_2m_max"][day_offset],
                "temperature_min_c": daily["temperature_2m_min"][day_offset],
                "precipitation_probability_max": daily["precipitation_probability_max"][day_offset],
                "precipitation_sum_mm": daily["precipitation_sum"][day_offset],
            }
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise WeatherError("天气服务返回的每日预报无效") from exc

        current = payload.get("current") if day_offset == 0 else None
        if current is not None and not isinstance(current, dict):
            raise WeatherError("天气服务返回的实时数据无效")
        label_parts = [str(place.get("name") or ""), str(place.get("admin1") or ""), str(place.get("country") or "")]
        label = "，".join(part for index, part in enumerate(label_parts) if part and part not in label_parts[:index])
        return {
            "location": {
                "name": label or str(place.get("name") or "未知地点"),
                "latitude": float(place["latitude"]),
                "longitude": float(place["longitude"]),
            },
            "timezone": str(payload.get("timezone") or ""),
            "day": day,
            "current": OpenMeteoWeatherService._normalize_current(current) if current else None,
            "source": "Open-Meteo",
        }

    @staticmethod
    def _normalize_current(current: dict[str, Any]) -> dict[str, Any]:
        try:
            return {
                "time": current["time"],
                "weather": WEATHER_CODES.get(int(current["weather_code"]), "未知天气"),
                "temperature_c": current["temperature_2m"],
                "apparent_temperature_c": current["apparent_temperature"],
                "humidity": current["relative_humidity_2m"],
                "precipitation_mm": current["precipitation"],
                "wind_speed_kmh": current["wind_speed_10m"],
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherError("天气服务返回的实时数据无效") from exc

    async def describe(self, location: str, *, day_offset: int = 0) -> str:
        result = await self.weather(location, day_offset=day_offset)
        day = result["day"]
        current = result["current"]
        prefix = f"{result['location']['name']} {day['date']}天气：{day['weather']}，{day['temperature_min_c']}–{day['temperature_max_c']}°C"
        suffix = f"，最高降水概率 {day['precipitation_probability_max']}%，降水量 {day['precipitation_sum_mm']} mm。"
        if not current:
            return f"{prefix}{suffix} 数据来源：Open-Meteo。"
        current_text = (
            f"当前 {current['weather']}，{current['temperature_c']}°C（体感 {current['apparent_temperature_c']}°C），"
            f"湿度 {current['humidity']}%，风速 {current['wind_speed_kmh']} km/h；"
        )
        return f"{result['location']['name']}当前天气：{current_text}{prefix}{suffix} 数据时间：{current['time']}（{result['timezone']}），来源：Open-Meteo。"
