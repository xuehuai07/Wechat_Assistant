from urllib.parse import parse_qs

import httpx
import pytest

from app.agent.chat_agent import ChatAgent
from app.config import load_settings
from app.db import Database
from app.services.deepseek import ModelReply, ToolCall
from app.services.weather import LocationNotFoundError, OpenMeteoWeatherService, parse_weather_request
from app.tools.builtin import WeatherForecastTool
from app.tools.policy import ToolRegistry


def weather_transport(request: httpx.Request) -> httpx.Response:
    if request.url.host == "geocoding-api.open-meteo.com":
        assert parse_qs(request.url.query.decode())["name"] == ["上海"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "name": "上海",
                        "admin1": "上海市",
                        "country": "中国",
                        "latitude": 31.2304,
                        "longitude": 121.4737,
                    }
                ]
            },
        )
    assert request.url.host == "api.open-meteo.com"
    query = parse_qs(request.url.query.decode())
    assert query["latitude"] == ["31.2304"]
    assert query["longitude"] == ["121.4737"]
    assert query["timezone"] == ["auto"]
    return httpx.Response(
        200,
        json={
            "timezone": "Asia/Shanghai",
            "current": {
                "time": "2026-07-10T10:00",
                "temperature_2m": 30.2,
                "apparent_temperature": 34.8,
                "relative_humidity_2m": 75,
                "precipitation": 0.0,
                "weather_code": 2,
                "wind_speed_10m": 12.4,
            },
            "daily": {
                "time": ["2026-07-10", "2026-07-11", "2026-07-12"],
                "weather_code": [2, 61, 3],
                "temperature_2m_max": [33.0, 30.0, 31.0],
                "temperature_2m_min": [27.0, 26.0, 25.0],
                "precipitation_probability_max": [20, 80, 10],
                "precipitation_sum": [0.0, 9.2, 0.0],
            },
        },
    )


@pytest.mark.asyncio
async def test_weather_uses_public_geocoding_and_forecast_without_key():
    service = OpenMeteoWeatherService(transport=httpx.MockTransport(weather_transport))

    result = await service.weather("上海")

    assert result["location"]["name"] == "上海，上海市，中国"
    assert result["current"]["weather"] == "局部多云"
    assert result["day"]["temperature_max_c"] == 33.0
    assert "来源：Open-Meteo" in await service.describe("上海")


@pytest.mark.asyncio
async def test_weather_reports_missing_location_without_calling_forecast():
    async def unused_handler(request):  # pragma: no cover - defensive only
        raise AssertionError(request.url)

    service = OpenMeteoWeatherService(transport=httpx.MockTransport(unused_handler))
    with pytest.raises(LocationNotFoundError, match="至少两个字符"):
        await service.weather("上")


def test_parse_weather_request_extracts_city_and_date():
    request = parse_weather_request("上海明天天气怎么样？")
    assert request is not None
    assert request.location == "上海"
    assert request.day_offset == 1
    missing_location = parse_weather_request("今天天气")
    assert missing_location is not None
    assert missing_location.location is None
    assert parse_weather_request("帮我写一封邮件") is None


@pytest.mark.asyncio
async def test_agent_uses_weather_service_for_explicit_weather_request(tmp_path):
    class UnexpectedModel:
        async def chat(self, messages):  # pragma: no cover - must not be reached
            raise AssertionError(messages)

    settings = load_settings(validate=True)
    db = Database(tmp_path / "agent.sqlite3")
    db.initialize()
    weather = OpenMeteoWeatherService(transport=httpx.MockTransport(weather_transport))
    agent = ChatAgent(settings, db, UnexpectedModel(), ToolRegistry(), weather)

    result = await agent.run("web:test", "上海今天天气")

    assert "来源：Open-Meteo" in result.reply


@pytest.mark.asyncio
async def test_agent_executes_weather_tool_call_and_finishes_with_model_reply(tmp_path):
    class ToolCallingModel:
        def __init__(self):
            self.calls = []

        async def chat(self, messages, tools=None):
            self.calls.append((messages, tools))
            if len(self.calls) == 1:
                assert tools and tools[0]["function"]["name"] == "weather.get_forecast"
                return ModelReply(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="call_weather",
                            name="weather.get_forecast",
                            arguments={"location": "上海", "day_offset": 1},
                        )
                    ],
                )
            assert messages[-1]["role"] == "tool"
            assert "Open-Meteo" in messages[-1]["content"]
            return ModelReply(content="上海明天有小雨，建议带伞。")

    settings = load_settings(validate=True)
    db = Database(tmp_path / "agent.sqlite3")
    db.initialize()
    weather = OpenMeteoWeatherService(transport=httpx.MockTransport(weather_transport))
    tools = ToolRegistry(["weather.get_forecast"])
    tools.register(WeatherForecastTool(weather))
    model = ToolCallingModel()
    agent = ChatAgent(settings, db, model, tools, weather)

    result = await agent.run("web:test", "上海明天天气怎么样")

    assert result.reply == "上海明天有小雨，建议带伞。"
    assert len(model.calls) == 2
    stored = db.list_messages("web:test")
    assert [message["role"] for message in stored] == ["user", "tool", "assistant"]
    assert '"tool": "weather.get_forecast"' in stored[1]["content"]
