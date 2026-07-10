import pytest

from app.tools.policy import ToolRegistry


class EchoTool:
    name = "maps_weather"

    async def execute(self, params):
        return params


@pytest.mark.asyncio
async def test_tool_registry_filters_and_checks_execution():
    registry = ToolRegistry(["maps_*"])
    registry.register(EchoTool())
    assert registry.names() == ["maps_weather"]
    assert await registry.execute("maps_weather", {"city": "上海"}) == {"city": "上海"}
    with pytest.raises(PermissionError):
        await registry.execute("bash", {})


def test_empty_allowlist_is_fail_closed():
    registry = ToolRegistry([])
    registry.register(EchoTool())
    assert registry.names() == []
    assert not registry.is_allowed("maps_weather")
