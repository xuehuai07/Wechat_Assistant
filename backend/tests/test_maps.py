from urllib.parse import parse_qs, urlparse

import pytest

from app.maps.service import FixtureMapProvider, MapService, PlaceNotFoundError, ProfileConfigurationError


def write_profile(path, places):
    path.write_text('{"places": ' + places + '}', encoding="utf-8")


def test_status_without_profile_is_safe(tmp_path):
    service = MapService(tmp_path / "missing.json", FixtureMapProvider())

    assert service.status() == {
        "provider": {"name": "fixture", "web_service_key_configured": False, "web_service_queries": False},
        "uri_navigation": True,
        "profile": {"state": "missing", "places": []},
    }


def test_navigation_url_uses_saved_places_only(tmp_path):
    profile = tmp_path / "profile.local.json"
    write_profile(
        profile,
        '{"家": {"name": "家", "longitude": 121.4737, "latitude": 31.2304}, '
        '"公司": {"name": "办公室", "longitude": 121.4998, "latitude": 31.2397}}',
    )
    service = MapService(profile, FixtureMapProvider())

    result = service.navigation_url(destination="公司", origin="家", mode="car", policy=1)
    query = parse_qs(urlparse(result["url"]).query)

    assert urlparse(result["url"]).netloc == "uri.amap.com"
    assert query == {
        "from": ["121.473700,31.230400,家"],
        "to": ["121.499800,31.239700,办公室"],
        "mode": ["car"],
        "policy": ["1"],
        "src": ["private_wechat_agent"],
        "callnative": ["1"],
    }
    assert result["destination"]["alias"] == "公司"


def test_navigation_allows_current_mobile_location_and_rejects_unknown_alias(tmp_path):
    profile = tmp_path / "profile.local.json"
    write_profile(profile, '{"家": {"longitude": 121.4737, "latitude": 31.2304}}')
    service = MapService(profile, FixtureMapProvider())

    query = parse_qs(urlparse(service.navigation_url(destination="家", mode="walk")["url"]).query)
    assert "from" not in query
    assert query["mode"] == ["walk"]
    with pytest.raises(PlaceNotFoundError, match="未找到地点别名"):
        service.navigation_url(destination="不存在")
    with pytest.raises(ValueError, match="步行和骑行"):
        service.navigation_url(destination="家", mode="walk", policy=1)


def test_invalid_profile_is_reported_without_network_access(tmp_path):
    profile = tmp_path / "profile.local.json"
    write_profile(profile, '{"家": {"longitude": 181, "latitude": 31.2304}}')
    service = MapService(profile, FixtureMapProvider())

    assert service.status()["profile"] == {"state": "invalid", "places": []}
    with pytest.raises(ProfileConfigurationError, match="经度无效"):
        service.navigation_url(destination="家")
