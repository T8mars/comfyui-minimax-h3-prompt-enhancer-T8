from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit


TEMPERATURE_AUTO = "auto"
TEMPERATURE_SEND = "send"
TEMPERATURE_OMIT = "omit"
TEMPERATURE_POLICIES = frozenset({TEMPERATURE_AUTO, TEMPERATURE_SEND, TEMPERATURE_OMIT})

# These are optional OpenAI-compatible request fields whose meaning is stable
# enough to pass through. Core transport/auth/media fields remain owned by the
# node and can never be replaced through provider configuration.
ALLOWED_EXTRA_PARAMETERS = frozenset(
    {
        "frequency_penalty",
        "max_completion_tokens",
        "max_tokens",
        "presence_penalty",
        "reasoning_effort",
        "response_format",
        "seed",
        "stop",
        "top_p",
    }
)
PROTECTED_PARAMETERS = frozenset({"model", "messages", "stream", "temperature"})
MAX_EXTRA_PARAMETERS_BYTES = 4096


class ProviderCapabilityError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderRequestOptions:
    temperature_policy: str = TEMPERATURE_AUTO
    extra_parameters: Mapping[str, Any] | None = None


def _normalized_temperature_policy(value: Any) -> str:
    policy = str(value or TEMPERATURE_AUTO).strip().lower()
    if policy not in TEMPERATURE_POLICIES:
        raise ProviderCapabilityError(f"Unsupported temperature policy: {policy}")
    return policy


def _is_kimi_coding_endpoint(chat_url: str) -> bool:
    parsed = urlsplit(str(chat_url or "").strip())
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/").lower()
    return host == "api.kimi.com" and (path == "/coding" or path.startswith("/coding/"))


def should_send_temperature(chat_url: str, policy: Any = TEMPERATURE_AUTO) -> bool:
    normalized = _normalized_temperature_policy(policy)
    if normalized == TEMPERATURE_SEND:
        return True
    if normalized == TEMPERATURE_OMIT:
        return False
    # Kimi Coding Plan documents an OpenAI-shaped endpoint but rejects the
    # optional temperature field. All unknown providers retain the 1.2.0
    # behavior and continue receiving temperature.
    return not _is_kimi_coding_endpoint(chat_url)


def normalize_extra_parameters(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ProviderCapabilityError("Additional provider parameters must be valid JSON.") from exc
    if not isinstance(value, Mapping):
        raise ProviderCapabilityError("Additional provider parameters must be a JSON object.")
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if key in PROTECTED_PARAMETERS:
            raise ProviderCapabilityError(f"Provider parameter is managed by the node and cannot be overridden: {key}")
        if key not in ALLOWED_EXTRA_PARAMETERS:
            raise ProviderCapabilityError(f"Unsupported additional provider parameter: {key}")
        result[key] = raw_value
    try:
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProviderCapabilityError("Additional provider parameters are not JSON serializable.") from exc
    if len(encoded) > MAX_EXTRA_PARAMETERS_BYTES:
        raise ProviderCapabilityError("Additional provider parameters exceed the 4096-byte safety limit.")
    return result


def apply_chat_request_options(
    payload: Mapping[str, Any],
    *,
    chat_url: str,
    temperature: float,
    options: ProviderRequestOptions | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if options is None:
        normalized = ProviderRequestOptions()
    elif isinstance(options, ProviderRequestOptions):
        normalized = options
    elif isinstance(options, Mapping):
        normalized = ProviderRequestOptions(
            temperature_policy=str(options.get("temperature_policy", TEMPERATURE_AUTO)),
            extra_parameters=options.get("extra_parameters"),
        )
    else:
        raise ProviderCapabilityError("Provider request options must be an object.")

    result = dict(payload)
    if should_send_temperature(chat_url, normalized.temperature_policy):
        result["temperature"] = temperature
    else:
        result.pop("temperature", None)
    result.update(normalize_extra_parameters(normalized.extra_parameters))
    return result


def provider_capability_summary(chat_url: str, policy: Any = TEMPERATURE_AUTO) -> dict[str, Any]:
    return {
        "schema_version": "t8-provider-capability/v1",
        "temperature_policy": _normalized_temperature_policy(policy),
        "temperature_sent": should_send_temperature(chat_url, policy),
        "profile": "kimi-coding" if _is_kimi_coding_endpoint(chat_url) else "openai-compatible-unknown",
        "image_data_url": "unknown",
        "video_data_url": "unknown",
        "video_url": "unknown",
    }


__all__ = [
    "ALLOWED_EXTRA_PARAMETERS",
    "ProviderCapabilityError",
    "ProviderRequestOptions",
    "TEMPERATURE_AUTO",
    "TEMPERATURE_OMIT",
    "TEMPERATURE_POLICIES",
    "TEMPERATURE_SEND",
    "apply_chat_request_options",
    "normalize_extra_parameters",
    "provider_capability_summary",
    "should_send_temperature",
]
