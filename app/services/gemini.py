from enum import Enum
from typing import Any

from google import genai
from google.genai import errors, types

from app.services.ai import AiProviderError, AiProviderRequest, AiProviderResult

_MAX_TOKEN_COUNT = 2_147_483_647
_SAFETY_RATING_LIMIT = 20


class GeminiProvider:
    key = "gemini"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key.strip() if type(api_key) is str else ""

    def generate(self, request: AiProviderRequest) -> AiProviderResult:
        if not self._api_key:
            raise AiProviderError("AI_PROVIDER_DISABLED")
        try:
            try:
                with genai.Client(
                    api_key=self._api_key,
                    http_options=types.HttpOptions(
                        timeout=int(request.timeout_seconds * 1000)
                    ),
                ) as client:
                    response = client.models.generate_content(
                        model=request.model_id,
                        contents=request.user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=request.system_prompt,
                            response_mime_type="application/json",
                            response_json_schema=request.output_schema,
                            max_output_tokens=request.max_output_tokens,
                            temperature=request.temperature,
                        ),
                    )
                    try:
                        return _normalize_response(response)
                    except AiProviderError:
                        raise
                    except Exception:  # noqa: BLE001 -- untrusted SDK response
                        raise AiProviderError(
                            "AI_PROVIDER_RESPONSE_INVALID"
                        ) from None
            except AiProviderError:
                raise
            except errors.APIError as error:
                raise AiProviderError(_map_api_error(error)) from None
            except TimeoutError:
                raise AiProviderError("AI_PROVIDER_TIMEOUT") from None
            except (OSError, RuntimeError, ValueError):
                raise AiProviderError("AI_PROVIDER_TRANSPORT") from None
        except AiProviderError:
            raise
        except Exception:  # noqa: BLE001 -- final ordinary-exception SDK boundary
            raise AiProviderError("AI_PROVIDER_ERROR") from None


def _normalize_response(response: Any) -> AiProviderResult:
    candidates = response.candidates
    if candidates is None:
        candidate = None
    elif type(candidates) in (list, tuple):
        candidate = candidates[0] if candidates else None
    else:
        raise AiProviderError("AI_PROVIDER_RESPONSE_INVALID")

    finish_reason = candidate.finish_reason if candidate is not None else None
    finish_value = _safe_enum_value(finish_reason, 100)
    if finish_value is not None and any(
        marker in finish_value.upper()
        for marker in ("SAFETY", "BLOCKLIST", "PROHIBITED")
    ):
        raise AiProviderError("AI_PROVIDER_SAFETY_BLOCKED")

    text = response.text
    if type(text) is not str or not text.strip():
        raise AiProviderError("AI_PROVIDER_RESPONSE_INVALID")

    input_tokens, output_tokens, total_tokens = _safe_usage(response.usage_metadata)
    return AiProviderResult(
        output_text=text,
        provider_request_id=_safe_scalar(response.response_id, 200),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        finish_reason=finish_value,
        safety_metadata=_safe_safety(candidate),
    )


def _map_api_error(error: object) -> str:
    try:
        code = error.code
    except Exception:  # noqa: BLE001 -- SDK error properties are outside our control
        code = None

    if type(code) is int:
        if not 100 <= code <= 599:
            return "AI_PROVIDER_TRANSPORT"
        if code == 401 or code == 403:
            return "AI_PROVIDER_AUTHENTICATION"
        if code == 429:
            return "AI_PROVIDER_RATE_LIMITED"
        if code == 408 or code == 504:
            return "AI_PROVIDER_TIMEOUT"
        if 500 <= code <= 599:
            return "AI_PROVIDER_UNAVAILABLE"
        return "AI_PROVIDER_TRANSPORT"

    try:
        status = error.status
    except Exception:  # noqa: BLE001 -- SDK error properties are outside our control
        status = None

    if type(status) is not str or len(status) > 100:
        return "AI_PROVIDER_TRANSPORT"
    if status == "UNAUTHENTICATED" or status == "PERMISSION_DENIED":
        return "AI_PROVIDER_AUTHENTICATION"
    if status == "RESOURCE_EXHAUSTED":
        return "AI_PROVIDER_RATE_LIMITED"
    if status == "DEADLINE_EXCEEDED":
        return "AI_PROVIDER_TIMEOUT"
    if status == "UNAVAILABLE":
        return "AI_PROVIDER_UNAVAILABLE"
    return "AI_PROVIDER_TRANSPORT"


def _safe_scalar(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    if type(value) is str:
        rendered = value
    elif type(value) is int:
        rendered = f"{value:d}"
    else:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in rendered):
        return None
    return rendered.strip()[:limit] or None


def _safe_enum_value(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    return _safe_scalar(value, limit)


def _nonnegative(value: Any) -> int | None:
    if (
        type(value) is not int
        or not 0 <= value <= _MAX_TOKEN_COUNT
    ):
        return None
    return value


def _safe_usage(usage: Any) -> tuple[int | None, int | None, int | None]:
    if usage is None:
        return None, None, None
    try:
        input_tokens = _nonnegative(usage.prompt_token_count)
        output_tokens = _nonnegative(usage.candidates_token_count)
        total_tokens = _nonnegative(usage.total_token_count)
        if None in (input_tokens, output_tokens, total_tokens):
            return None, None, None
        if total_tokens != input_tokens + output_tokens:
            return None, None, None
    except Exception:  # noqa: BLE001 -- SDK metadata properties are outside our control
        return None, None, None
    return input_tokens, output_tokens, total_tokens


def _safe_safety(candidate: Any) -> dict[str, Any] | None:
    if candidate is None:
        return None
    ratings = candidate.safety_ratings
    if ratings is None:
        return None
    if type(ratings) not in (list, tuple):
        raise AiProviderError("AI_PROVIDER_RESPONSE_INVALID")
    values: list[dict[str, Any]] = []
    for rating in ratings[:_SAFETY_RATING_LIMIT]:
        blocked = rating.blocked
        if blocked is not None and not isinstance(blocked, bool):
            blocked = None
        values.append(
            {
                "category": _safe_enum_value(rating.category, 100),
                "probability": _safe_enum_value(rating.probability, 100),
                "blocked": blocked,
            }
        )
    return {"ratings": values} if values else None
