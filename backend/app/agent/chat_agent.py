from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from ..config import Settings
from ..db import Database
from ..services.deepseek import DeepSeekClient
from ..services.weather import LocationNotFoundError, OpenMeteoWeatherService, WeatherError, parse_weather_request
from ..tools.policy import ToolRegistry


SYSTEM_PROMPT = """你是单用户的中文私人微信助手。
首版只支持文本聊天。你不能声称自己可以执行终端、读写文件、控制浏览器、安装插件、支付、下单、打车或后台定位。
系统可直接查询明确城市的实时天气和短期预报；其他实时数据或外部工具未启用时，应明确说明，不要编造结果。
回答应简洁、直接、中文优先。"""


class ChatState(TypedDict):
    conversation_id: str
    user_message: str
    reply: str


@dataclass
class ChatResult:
    conversation_id: str
    reply: str


class ChatAgent:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        deepseek: DeepSeekClient,
        tools: ToolRegistry,
        weather: OpenMeteoWeatherService,
    ) -> None:
        self.settings = settings
        self.db = db
        self.deepseek = deepseek
        self.tools = tools
        self.weather = weather
        self._graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return None

        graph = StateGraph(ChatState)

        async def call_model(state: ChatState) -> ChatState:
            state["reply"] = await self._call_model(state["conversation_id"], state["user_message"])
            return state

        graph.add_node("call_model", call_model)
        graph.set_entry_point("call_model")
        graph.add_edge("call_model", END)
        return graph.compile()

    async def run(self, conversation_id: str, user_message: str, *, source: str = "web", external_user_id: str | None = None, external_msg_id: str | None = None) -> ChatResult:
        self.db.upsert_conversation(conversation_id, source, external_user_id)
        inserted = self.db.add_message(conversation_id, "user", user_message, external_msg_id)
        if not inserted:
            previous = self.db.recent_messages(conversation_id, 1)
            return ChatResult(conversation_id=conversation_id, reply=previous[-1]["content"] if previous else "")

        weather_reply = await self._weather_reply(user_message)
        if weather_reply is not None:
            reply = weather_reply
        elif self._graph:
            result = await self._graph.ainvoke({"conversation_id": conversation_id, "user_message": user_message, "reply": ""})
            reply = result["reply"]
        else:
            reply = await self._call_model(conversation_id, user_message)

        self.db.add_message(conversation_id, "assistant", reply)
        return ChatResult(conversation_id=conversation_id, reply=reply)

    async def _weather_reply(self, user_message: str) -> str | None:
        if not self.settings.agent.weather_enabled:
            return None
        request = parse_weather_request(user_message)
        if request is None:
            return None
        if not request.location:
            return "可以，请告诉我要查询哪个城市或地点，例如“上海明天天气”。"
        try:
            return await self.weather.describe(request.location, day_offset=request.day_offset)
        except LocationNotFoundError:
            return f"没有找到“{request.location}”。请提供更明确的城市或地点名称。"
        except WeatherError:
            return "天气服务暂时不可用，请稍后再试；我不会根据常识猜测实时天气。"

    async def _call_model(self, conversation_id: str, user_message: str) -> str:
        recent = self.db.recent_messages(conversation_id, self.settings.agent.max_context_turns * 2)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for message in recent:
            role = message["role"]
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": message["content"]})
        if not recent or recent[-1]["content"] != user_message:
            messages.append({"role": "user", "content": user_message})
        return await self.deepseek.chat(messages)
