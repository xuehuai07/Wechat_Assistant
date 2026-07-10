from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlencode


NavigationMode = Literal["car", "bus", "walk", "ride"]
NAVIGATION_URI = "https://uri.amap.com/navigation"


class MapError(ValueError):
    """Base error for safe, user-actionable map failures."""


class ProfileConfigurationError(MapError):
    """The local profile exists but does not match the expected schema."""


class PlaceNotFoundError(MapError):
    """A map request refers to a place that has not been saved locally."""


@dataclass(frozen=True)
class Place:
    alias: str
    name: str
    longitude: float
    latitude: float

    @classmethod
    def from_profile(cls, alias: str, value: object) -> Place:
        if not isinstance(value, Mapping):
            raise ProfileConfigurationError(f"地点 {alias!r} 必须是对象")
        name = str(value.get("name", alias)).strip()
        if not name or len(name) > 80:
            raise ProfileConfigurationError(f"地点 {alias!r} 的名称无效")
        try:
            longitude = float(value["longitude"])
            latitude = float(value["latitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProfileConfigurationError(f"地点 {alias!r} 缺少有效经纬度") from exc
        if not math.isfinite(longitude) or not -180 <= longitude <= 180:
            raise ProfileConfigurationError(f"地点 {alias!r} 的经度无效")
        if not math.isfinite(latitude) or not -90 <= latitude <= 90:
            raise ProfileConfigurationError(f"地点 {alias!r} 的纬度无效")
        return cls(alias=alias, name=name, longitude=longitude, latitude=latitude)

    def uri_value(self) -> str:
        return f"{self.longitude:.6f},{self.latitude:.6f},{self.name}"

    def public_summary(self) -> dict[str, str | float]:
        return {
            "alias": self.alias,
            "name": self.name,
            "longitude": self.longitude,
            "latitude": self.latitude,
        }


class MapProvider(Protocol):
    name: str

    def status(self) -> dict[str, str | bool]:
        ...


@dataclass(frozen=True)
class AmapWebServiceProvider:
    """Capability marker for the future authenticated Amap Web Service client."""

    api_key: str = ""
    name: str = "amap"

    def status(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "web_service_key_configured": bool(self.api_key),
            "web_service_queries": False,
        }


@dataclass(frozen=True)
class FixtureMapProvider:
    """Offline provider used by tests and local no-key development."""

    name: str = "fixture"

    def status(self) -> dict[str, str | bool]:
        return {"name": self.name, "web_service_key_configured": False, "web_service_queries": False}


class LocalProfile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_places(self) -> dict[str, Place]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileConfigurationError("本地地点配置无法读取") from exc
        if not isinstance(raw, Mapping):
            raise ProfileConfigurationError("本地地点配置必须是 JSON 对象")
        source = raw.get("places", {})
        if not isinstance(source, Mapping):
            raise ProfileConfigurationError("places 必须是对象")

        places: dict[str, Place] = {}
        for raw_alias, value in source.items():
            alias = str(raw_alias).strip()
            normalized = alias.casefold()
            if not alias or len(alias) > 80 or normalized in places:
                raise ProfileConfigurationError("地点别名无效或重复")
            places[normalized] = Place.from_profile(alias, value)
        return places


class MapService:
    def __init__(self, profile_path: Path, provider: MapProvider) -> None:
        self.profile = LocalProfile(profile_path)
        self.provider = provider

    def status(self) -> dict:
        try:
            places = self.profile.load_places()
        except ProfileConfigurationError:
            return {
                "provider": self.provider.status(),
                "uri_navigation": True,
                "profile": {"state": "invalid", "places": []},
            }
        return {
            "provider": self.provider.status(),
            "uri_navigation": True,
            "profile": {
                "state": "ready" if self.profile.path.exists() else "missing",
                "places": [place.public_summary() for place in sorted(places.values(), key=lambda item: item.alias.casefold())],
            },
        }

    def navigation_url(
        self,
        *,
        destination: str,
        origin: str | None = None,
        mode: NavigationMode = "car",
        policy: int = 0,
        callnative: bool = True,
    ) -> dict:
        if mode not in {"car", "bus", "walk", "ride"}:
            raise MapError("不支持的出行方式")
        if not 0 <= policy <= 3:
            raise MapError("路线策略必须在 0 到 3 之间")
        if mode in {"walk", "ride"} and policy:
            raise MapError("步行和骑行不支持路线策略")

        places = self.profile.load_places()
        destination_place = self._resolve_place(destination, places)
        origin_place = self._resolve_place(origin, places) if origin else None
        params: list[tuple[str, str]] = [("to", destination_place.uri_value())]
        if origin_place:
            params.insert(0, ("from", origin_place.uri_value()))
        params.extend(
            [
                ("mode", mode),
                ("policy", str(policy)),
                ("src", "private_wechat_agent"),
                ("callnative", "1" if callnative else "0"),
            ]
        )
        return {
            "url": f"{NAVIGATION_URI}?{urlencode(params)}",
            "origin": origin_place.public_summary() if origin_place else None,
            "destination": destination_place.public_summary(),
            "mode": mode,
            "policy": policy,
        }

    @staticmethod
    def _resolve_place(reference: str | None, places: Mapping[str, Place]) -> Place:
        normalized = (reference or "").strip().casefold()
        if not normalized:
            raise PlaceNotFoundError("请提供已保存的地点别名")
        place = places.get(normalized)
        if not place:
            raise PlaceNotFoundError(f"未找到地点别名：{reference.strip()}")
        return place
