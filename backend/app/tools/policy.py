from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict

    def as_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class Tool(Protocol):
    name: str
    spec: ToolSpec

    async def execute(self, params: dict) -> dict:
        ...


class ToolRegistry:
    def __init__(self, allowlist: list[str] | None = None) -> None:
        self.allowlist = allowlist or []
        self._tools: dict[str, Tool] = {}

    def is_allowed(self, name: str) -> bool:
        if not self.allowlist:
            return False
        return any(fnmatchcase(name, pattern) for pattern in self.allowlist)

    def register(self, tool: Tool) -> None:
        if self.is_allowed(tool.name):
            self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def is_registered(self, name: str) -> bool:
        return name in self._tools

    def schemas(self) -> list[dict]:
        return [self._tools[name].spec.as_openai_tool() for name in self.names()]

    async def execute(self, name: str, params: dict) -> dict:
        if not self.is_allowed(name):
            raise PermissionError(f"tool not allowed: {name}")
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"tool not registered: {name}")
        return await tool.execute(params)
