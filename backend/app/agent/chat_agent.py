from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypedDict

from ..config import Settings
from ..db import Database
from ..services.deepseek import DeepSeekClient, ModelReply, ToolCall
from ..services.weather import LocationNotFoundError, OpenMeteoWeatherService, WeatherError, parse_weather_request
from ..tools.policy import ToolRegistry


SYSTEM_PROMPT = """你是单用户的中文私人微信助手。
首版只支持文本聊天。你不能声称自己可以执行终端、读写文件、控制浏览器、安装插件、支付、下单、打车或后台定位。
系统可在后端工具启用时查询明确城市的实时天气和短期预报，也可根据本地已保存地点别名生成高德导航链接。
其他实时数据或外部工具未启用时，应明确说明，不要编造结果。
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

    async def run(
        self,
        conversation_id: str,
        user_message: str,
        *,
        source: str = "web",
        external_user_id: str | None = None,
        external_msg_id: str | None = None,
    ) -> ChatResult:
        self.db.upsert_conversation(conversation_id, source, external_user_id)
        inserted = self.db.add_message(conversation_id, "user", user_message, external_msg_id)
        if not inserted:
            previous = self.db.recent_messages(conversation_id, 1)
            return ChatResult(conversation_id=conversation_id, reply=previous[-1]["content"] if previous else "")

        weather_reply = await self._compat_weather_reply(user_message)
        if weather_reply is not None:
            reply = weather_reply
        elif self._graph:
            result = await self._graph.ainvoke({"conversation_id": conversation_id, "user_message": user_message, "reply": ""})
            reply = result["reply"]
        else:
            reply = await self._call_model(conversation_id, user_message)

        self.db.add_message(conversation_id, "assistant", reply)
        return ChatResult(conversation_id=conversation_id, reply=reply)

    async def _compat_weather_reply(self, user_message: str) -> str | None:
        if not self.settings.agent.weather_enabled or self.tools.is_registered("weather.get_forecast"):
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
        messages = self._build_messages(conversation_id, user_message)
        tools = self.tools.schemas()
        if not tools:
            return (await self._chat_model(messages)).content

        for _ in range(self.settings.agent.max_steps):
            reply = await self._chat_model(messages, tools)
            if not reply.tool_calls:
                return reply.content or "我暂时无法生成回复。"
            messages.append(self._assistant_tool_call_message(reply))
            for tool_call in reply.tool_calls:
                tool_result = await self._execute_tool_call(tool_call)
                tool_content = json.dumps(tool_result, ensure_ascii=False)
                self.db.add_message(conversation_id, "tool", tool_content)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": tool_content,
                    }
                )
        return "工具调用次数已达到上限，请把需求拆小一点再试。"

    def _build_messages(self, conversation_id: str, user_message: str) -> list[dict[str, Any]]:
        recent = self.db.recent_messages(conversation_id, self.settings.agent.max_context_turns * 2)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for message in recent:
            role = message["role"]
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": message["content"]})
        if not recent or recent[-1]["content"] != user_message:
            messages.append({"role": "user", "content": user_message})
        return messages

    async def _chat_model(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> ModelReply:
        try:
            reply = await self.deepseek.chat(messages, tools)
        except TypeError:
            reply = await self.deepseek.chat(messages)
        if isinstance(reply, ModelReply):
            return reply
        return ModelReply(content=str(reply or "").strip())

    async def _execute_tool_call(self, tool_call: ToolCall) -> dict:
        try:
            result = await self.tools.execute(tool_call.name, tool_call.arguments)
            return {"ok": True, "tool": tool_call.name, "result": result}
        except Exception as exc:
            return {"ok": False, "tool": tool_call.name, "error": str(exc)}

    @staticmethod
    def _assistant_tool_call_message(reply: ModelReply) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in reply.tool_calls
            ],
        }
