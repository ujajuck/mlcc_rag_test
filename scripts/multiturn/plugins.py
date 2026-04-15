"""ADK BasePlugin 기반 멀티턴 추적 플러그인.

스킬/툴/모델 호출을 콜백으로 받아 현재 attach 된 TurnRecord 에 누적한다.
turn 경계는 runner 가 attach_turn/detach_turn 으로 제어한다.
"""

from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from scripts.run_skill_regression import (
    _safe_json_dumps,
    _truncate_text,
    estimate_tokens_from_text,
    flatten_llm_request_to_text,
    flatten_llm_response_to_text,
)

from .types import ModelCallRecord, ToolCallRecord, TurnRecord


class MultiturnTrackingPlugin(BasePlugin):
    """단일 플러그인으로 skill / tool / model 을 모두 추적.

    skill 여부는 tool.name 이 known_skill_names 에 포함되는지로 판정한다.
    ADK SkillToolset 은 skill 을 tool 인터페이스로 노출하므로 tool 콜백에서
    같이 잡힌다.

    Parameters:
        known_skill_names: skill 로 분류할 tool 이름 집합.
    """

    def __init__(self, known_skill_names: Optional[set[str]] = None) -> None:
        super().__init__(name="multiturn_tracking_plugin")
        self.known_skill_names: set[str] = set(known_skill_names or [])
        self._current_turn: Optional[TurnRecord] = None

    def attach_turn(self, turn: TurnRecord) -> None:
        """현재 턴을 세팅. 이후 모든 콜백 이벤트는 이 turn 에 누적된다."""
        self._current_turn = turn

    def detach_turn(self) -> None:
        """턴 경계 해제."""
        self._current_turn = None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        """tool/skill 시작 시 호출 기록 append."""
        if self._current_turn is None:
            return None

        is_skill = tool.name in self.known_skill_names
        self._current_turn.tool_calls.append(
            ToolCallRecord(
                tool_name=tool.name,
                tool_args=dict(tool_args),
                result_preview="__PENDING__",
                is_skill=is_skill,
            )
        )

        if is_skill:
            if tool.name not in self._current_turn.skills_used:
                self._current_turn.skills_used.append(tool.name)
        else:
            if tool.name not in self._current_turn.tools_used:
                self._current_turn.tools_used.append(tool.name)
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        """tool/skill 성공 시 결과 preview 채움."""
        if self._current_turn is None:
            return None
        for rec in reversed(self._current_turn.tool_calls):
            if rec.tool_name == tool.name and rec.result_preview == "__PENDING__":
                rec.result_preview = _truncate_text(_safe_json_dumps(result))
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
        """tool/skill 예외 시 에러 기록."""
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
        """LLM 호출 직전 프롬프트 텍스트/토큰 수 기록."""
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
        """LLM 호출 직후 응답 텍스트/토큰 수 기록."""
        if self._current_turn is None or not self._current_turn.model_calls:
            return None
        response_text = flatten_llm_response_to_text(llm_response)
        rec = self._current_turn.model_calls[-1]
        rec.response_text = response_text
        rec.output_tokens = estimate_tokens_from_text(response_text)
        return None
