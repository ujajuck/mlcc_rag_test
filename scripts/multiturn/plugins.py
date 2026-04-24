"""ADK BasePlugin 기반 멀티턴 추적 플러그인.

스킬/툴/모델 호출을 콜백으로 받아 현재 attach 된 TurnRecord 에 누적한다.
turn 경계는 runner 가 attach_turn/detach_turn 으로 제어한다.

skill 추적:
    load_skill / load_skill_resource 호출 시 → tools_used + skills_used 에 기록.
    그 외 tool 은 tools_used 에만 기록.
"""

from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from scripts.common.utils import (
    estimate_tokens_from_text,
    flatten_llm_request_to_text,
    flatten_llm_response_to_text,
    safe_json_dumps,
    truncate_text,
)

from .types import ModelCallRecord, ToolCallRecord, TurnRecord

_SKILL_LOADERS = frozenset({"load_skill", "load_skill_resource"})


class MultiturnTrackingPlugin(BasePlugin):

    def __init__(self) -> None:
        super().__init__(name="multiturn_tracking_plugin")
        self._current_turn: Optional[TurnRecord] = None

    def attach_turn(self, turn: TurnRecord) -> None:
        self._current_turn = turn

    def detach_turn(self) -> None:
        self._current_turn = None

    @staticmethod
    def _extract_skill_name(
        tool: BaseTool, tool_args: dict[str, Any]
    ) -> Optional[str]:
        if tool.name == "load_skill":
            return tool_args.get("name") or None
        if tool.name == "load_skill_resource":
            return tool_args.get("skill_name") or None
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        if self._current_turn is None:
            return None

        is_skill_loader = tool.name in _SKILL_LOADERS
        skill_name = self._extract_skill_name(tool, tool_args) if is_skill_loader else None

        self._current_turn.tool_calls.append(
            ToolCallRecord(
                tool_name=tool.name,
                tool_args=dict(tool_args),
                result_preview="__PENDING__",
                is_skill=is_skill_loader,
            )
        )

        if tool.name not in self._current_turn.tools_used:
            self._current_turn.tools_used.append(tool.name)

        if skill_name and skill_name not in self._current_turn.skills_used:
            self._current_turn.skills_used.append(skill_name)

        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        if self._current_turn is None:
            return None
        for rec in reversed(self._current_turn.tool_calls):
            if rec.tool_name == tool.name and rec.result_preview == "__PENDING__":
                rec.result_preview = truncate_text(safe_json_dumps(result))
                break
        return None

    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> Optional[dict]:
        if self._current_turn is None:
            return None
        for rec in reversed(self._current_turn.tool_calls):
            if rec.tool_name == tool.name and rec.result_preview == "__PENDING__":
                rec.result_preview = ""
                rec.error = str(error)
                break
        if self._current_turn.error_message is None:
            self._current_turn.error_message = f"{tool.name}: {error}"
        return None

    async def before_model_callback(
        self,
        *,
        callback_context,
        llm_request,
    ) -> Optional[Any]:
        if self._current_turn is None:
            return None
        prompt_text = flatten_llm_request_to_text(llm_request)
        self._current_turn.model_calls.append(
            ModelCallRecord(
                prompt_text=prompt_text,
                response_text="",
                input_tokens=0,
                output_tokens=0,
            )
        )
        return None

    async def after_model_callback(
        self,
        *,
        callback_context,
        llm_response,
        llm_request=None,
    ) -> Optional[Any]:
        if self._current_turn is None or not self._current_turn.model_calls:
            return None
        response_text = flatten_llm_response_to_text(llm_response)
        rec = self._current_turn.model_calls[-1]
        rec.response_text = response_text

        usage = getattr(llm_response, "usage_metadata", None)
        if usage:
            rec.input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            rec.output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        else:
            rec.input_tokens = estimate_tokens_from_text(rec.prompt_text)
            rec.output_tokens = estimate_tokens_from_text(response_text)
        return None
