"""ADK BasePlugin 기반 멀티턴 추적 플러그인.

스킬/툴/모델 호출을 콜백으로 받아 현재 attach 된 TurnRecord 에 누적한다.
turn 경계는 runner 가 attach_turn/detach_turn 으로 제어한다.

skill 추적 전략:
    1) load_skill / load_skill_resource 호출 시 → tools_used + skills_used 에 기록
    2) 이후 호출되는 tool 을 해당 skill 에 매핑 (_skill_tool_map)
    3) 다음 턴에서 load_skill 없이 tool 만 호출되면 → 매핑으로 부모 skill 자동 귀속
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
        # 세션 레벨: tool_name → skill_name 매핑 (턴 간 유지)
        self._skill_tool_map: dict[str, str] = {}
        # 직전에 로드된 skill 이름 (이후 tool 을 이 skill 에 매핑)
        self._last_loaded_skill: Optional[str] = None

    def attach_turn(self, turn: TurnRecord) -> None:
        self._current_turn = turn

    def detach_turn(self) -> None:
        self._current_turn = None
        self._last_loaded_skill = None

    def _extract_skill_name(
        self, tool: BaseTool, tool_args: dict[str, Any]
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

        if tool.name in _SKILL_LOADERS:
            skill_name = self._extract_skill_name(tool, tool_args)
            if skill_name:
                self._last_loaded_skill = skill_name
                if skill_name not in self._current_turn.skills_used:
                    self._current_turn.skills_used.append(skill_name)

            # load_skill 자체도 tool 로 기록
            self._current_turn.tool_calls.append(
                ToolCallRecord(
                    tool_name=tool.name,
                    tool_args=dict(tool_args),
                    result_preview="__PENDING__",
                    is_skill=False,
                )
            )
            if tool.name not in self._current_turn.tools_used:
                self._current_turn.tools_used.append(tool.name)
        else:
            # 새 tool 이면 직전 load_skill 의 skill 에 매핑
            if tool.name not in self._skill_tool_map and self._last_loaded_skill:
                self._skill_tool_map[tool.name] = self._last_loaded_skill

            parent_skill = self._skill_tool_map.get(tool.name)

            self._current_turn.tool_calls.append(
                ToolCallRecord(
                    tool_name=tool.name,
                    tool_args=dict(tool_args),
                    result_preview="__PENDING__",
                    is_skill=parent_skill is not None,
                )
            )
            if tool.name not in self._current_turn.tools_used:
                self._current_turn.tools_used.append(tool.name)
            if parent_skill and parent_skill not in self._current_turn.skills_used:
                self._current_turn.skills_used.append(parent_skill)

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
                input_tokens=estimate_tokens_from_text(prompt_text),
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
        rec.output_tokens = estimate_tokens_from_text(response_text)
        return None
