"""평가 파이프라인 공용 유틸.

- json 직렬화/역직렬화 + 길이 제한 헬퍼
- ADK llm_request / llm_response 를 평범한 텍스트로 평탄화
- vLLM tokenize endpoint 기반 토큰 추정 (실패 시 char 길이 fallback)
- dict delta 계산
"""

import json
from functools import lru_cache
from typing import Any

import requests


# 실제 환경에 맞게 변경. tokenize 실패 시 char/4 추정으로 fallback 한다.
VLLM_TOKENIZE_URL = "http://ip:port/gpt-oss-120b/tokenize"


# ---- json / string utils ----


def safe_json_loads(raw: Any, default: Any) -> Any:
    """JSON 문자열 파싱. None/빈문자열/파싱 실패 시 default.

    safe_json_dumps 가 쌍따옴표를 작은따옴표로 치환하므로,
    파싱 실패 시 역치환 후 재시도한다.
    """
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return json.loads(str(raw).replace("'", '"'))
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(value: Any) -> str:
    """CSV 에 안전하게 들어가는 JSON 직렬화.

    내부 쌍따옴표를 작은따옴표로 치환해 CSV 이스케이프 중첩을 방지한다.
    """
    return json.dumps(value, ensure_ascii=False, default=str).replace('"', "'")


def truncate_text(value: str, max_len: int = 800) -> str:
    """CSV/preview 용 안전한 길이 제한."""
    if value is None:
        return ""
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


# ---- token estimation ----


def _truncate_for_estimation(text: str, limit: int = 8000) -> str:
    """토큰 추정용 long-prompt head+tail 트리밍."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n...\n" + text[-half:]


@lru_cache(maxsize=1024)
def _cached_tokenize(text: str) -> int:
    """vLLM tokenize endpoint 호출. 실패 시 char/4 추정."""
    try:
        response = requests.post(
            VLLM_TOKENIZE_URL, json={"text": text}, timeout=5
        )
        response.raise_for_status()
        data = response.json()
        tokens = data.get("tokens") or data.get("token_ids")
        if tokens is not None:
            return len(tokens)
        if "count" in data:
            return int(data["count"])
        return 0
    except Exception:
        return max(1, len(text) // 4)


def estimate_tokens_from_text(text: str) -> int:
    """텍스트 토큰 수 추정."""
    if not text:
        return 0
    return _cached_tokenize(_truncate_for_estimation(text, limit=8000))


# ---- ADK llm request / response flattening ----


def flatten_llm_request_to_text(llm_request: Any) -> str:
    """ADK LLM request 객체를 텍스트로 평탄화 (토큰 추정/로그용)."""
    parts: list[str] = []

    system_instruction = getattr(llm_request, "system_instruction", None)
    if system_instruction:
        parts.append(str(system_instruction))

    contents = getattr(llm_request, "contents", None) or []
    for content in contents:
        role = getattr(content, "role", None)
        if role:
            parts.append(f"[{role}]")
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                parts.append(text)
            elif hasattr(part, "function_call") and getattr(part, "function_call", None):
                parts.append(str(getattr(part, "function_call")))
            elif hasattr(part, "function_response") and getattr(part, "function_response", None):
                parts.append(str(getattr(part, "function_response")))

    tools = getattr(llm_request, "tools", None)
    if tools:
        parts.append(str(tools))

    return "\n".join(parts)


def flatten_llm_response_to_text(llm_response: Any) -> str:
    """ADK LLM response 객체를 텍스트로 평탄화."""
    parts: list[str] = []

    content = getattr(llm_response, "content", None)
    if content:
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                parts.append(text)
            elif hasattr(part, "function_call") and getattr(part, "function_call", None):
                parts.append(str(getattr(part, "function_call")))
            elif hasattr(part, "function_response") and getattr(part, "function_response", None):
                parts.append(str(getattr(part, "function_response")))

    return "\n".join(parts)


# ---- diff ----


def compute_dict_delta(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    """(added / removed / changed) 로 dict 차이 요약."""
    added = {k: curr[k] for k in curr if k not in prev}
    removed = {k: prev[k] for k in prev if k not in curr}
    changed = {
        k: {"old": prev[k], "new": curr[k]}
        for k in curr
        if k in prev and prev[k] != curr[k]
    }
    return {"added": added, "removed": removed, "changed": changed}
