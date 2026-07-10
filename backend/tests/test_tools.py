import pytest

from app.tools.policy import ToolRegistry, ToolSpec


class EchoTool:
    name = "maps_weather"
    spec = ToolSpec(
        name=name,
        description="Echo parameters for tests.",
        parameters={"type": "object", "properties": {}, "additionalProperties": True},
    )

    async def execute(self, params):
        return params


@pytest.mark.asyncio
async def test_tool_registry_filters_and_checks_execution():
    registry = ToolRegistry(["maps_*"])
    registry.register(EchoTool())
    assert registry.names() == ["maps_weather"]
    assert registry.schemas() == [
        {
            "type": "function",
            "function": {
                "name": "maps_weather",
                "description": "Echo parameters for tests.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
            },
        }
    ]
    assert await registry.execute("maps_weather", {"city": "上海"}) == {"city": "上海"}
    with pytest.raises(PermissionError):
        await registry.execute("bash", {})


def test_empty_allowlist_is_fail_closed():
    registry = ToolRegistry([])
    registry.register(EchoTool())
    assert registry.names() == []
    assert not registry.is_allowed("maps_weather")
