from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from ..config import Settings
from ..db import Database
from ..services.deepseek import DeepSeekClient
from ..tools.policy import ToolRegistry


SYSTEM_PROMPT = """你是单用户的中文私人微信助手。
首版只支持文本聊天。你不能声称自己可以执行终端、读写文件、控制浏览器、安装插件、支付、下单、打车或后台定位。
如果用户请求实时数据或外部工具，而当前没有对应工具，应明确说明暂未启用，不要编造结果。
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
    def __init__(self, settings: Settings, db: Database, deepseek: DeepSeekClient, tools: ToolRegistry) -> None:
        self.settings = settings
        self.db = db
        self.deepseek = deepseek
        self.tools = tools
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

        if self._graph:
            result = await self._graph.ainvoke({"conversation_id": conversation_id, "user_message": user_message, "reply": ""})
            reply = result["reply"]
        else:
            reply = await self._call_model(conversation_id, user_message)

        self.db.add_message(conversation_id, "assistant", reply)
        return ChatResult(conversation_id=conversation_id, reply=reply)

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
