"""멀티턴 평가용 데이터클래스 정의."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TurnTestSpec:
    """한 턴의 테스트 스펙 (CSV 한 행).

    Parameters:
        subindex: 케이스 내 턴 순서 (0-based).
        query: 유저 입력.
        expected_skills: 이번 턴에 반드시 호출돼야 하는 skill 이름 리스트.
        expected_tools: 이번 턴에 반드시 호출돼야 하는 tool 이름 리스트.
        expected_state: 이번 턴 종료 후 state 에 반드시 존재해야 하는
            (key, value) 맵. value 가 None 이면 키 존재 여부만 확인.
        required_keywords: 이번 턴 응답에 반드시 포함돼야 하는 키워드.
    """

    subindex: int
    query: str
    expected_skills: list[str] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    expected_state: dict[str, Any] = field(default_factory=dict)
    required_keywords: list[str] = field(default_factory=list)


@dataclass
class MultiturnTestCase:
    """하나의 케이스 (1 개 이상의 subindex turn 으로 구성)."""

    index: str
    turns: list[TurnTestSpec]


@dataclass
class ModelCallRecord:
    """한 번의 LLM 호출 단위 기록."""

    prompt_text: str
    response_text: str
    input_tokens: int
    output_tokens: int


@dataclass
class ToolCallRecord:
    """한 번의 tool/skill 호출 단위 기록."""

    tool_name: str
    tool_args: dict[str, Any]
    result_preview: str
    error: Optional[str] = None
    is_skill: bool = False


@dataclass
class TurnRecord:
    """한 턴 실행 결과.

    모든 필드는 runner 에서 채워지며 evaluator 가 pass/fail 을 기록한다.
    """

    subindex: int
    user_input: str
    final_response: str = ""
    skills_used: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    model_calls: list[ModelCallRecord] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    artifact_snapshot: dict[str, Any] = field(default_factory=dict)
    state_delta: dict[str, Any] = field(default_factory=dict)
    artifact_delta: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    model_request_count: int = 0
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None
    required_keywords_present: dict[str, bool] = field(default_factory=dict)
    passed: bool = True
    fail_reasons: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    """한 케이스(멀티턴) 집계 결과."""

    index: str
    turn_count: int
    turns: list[TurnRecord]
    passed: bool
    total_input_tokens: int
    total_output_tokens: int
    total_model_requests: int
    total_elapsed_seconds: float
    details_json_path: str
    error_message: Optional[str] = None
