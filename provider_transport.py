from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

import requests


_THINK_BLOCK_PATTERN = re.compile(
    r"<think(?:\s[^>]*)?>.*?</think\s*>",
    re.IGNORECASE | re.DOTALL,
)
_LEADING_THINK_END_PATTERN = re.compile(r"^\s*</think\s*>\s*", re.IGNORECASE)
_UNCLOSED_THINK_PATTERN = re.compile(r"<think(?:\s[^>]*)?>", re.IGNORECASE)


@dataclass(frozen=True)
class ChatTransportResult:
    text: str
    attempts: int
    response_id: str = ""


@dataclass
class _StreamAccumulator:
    text: str = ""
    response_id: str = ""
    complete: bool = False


def strip_inline_reasoning(content: str) -> str:
    """Remove reasoning traces embedded in OpenAI-compatible message content.

    Some reasoning providers do not use ``reasoning_content`` and instead put
    private reasoning in ``content``. Preserve byte-for-byte compatibility when
    no think marker is present; when one is present, return only the final text.
    """
    text = str(content)
    cleaned = _THINK_BLOCK_PATTERN.sub("", text)
    cleaned = _LEADING_THINK_END_PATTERN.sub("", cleaned)
    unclosed = _UNCLOSED_THINK_PATTERN.search(cleaned)
    if unclosed is not None:
        cleaned = cleaned[: unclosed.start()]
    return cleaned.strip() if cleaned != text else text


def _text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            str(part.get("text", ""))
            for part in value
            if isinstance(part, dict) and part.get("type") in (None, "text")
        )
    return ""


def _consume_openai_stream(
    response: Any,
    accumulator: _StreamAccumulator,
    on_checkpoint: Callable[[str, bool, str], None] | None,
) -> None:
    # Always request raw bytes and decode SSE as UTF-8 ourselves. Some gateways
    # omit a charset or advertise an incorrect one; requests may otherwise turn
    # valid Chinese into Latin-1/cp1252 mojibake before the JSON parser sees it.
    for raw_line in response.iter_lines(decode_unicode=False):
        if not raw_line:
            continue
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line)
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data_text = line[5:].strip()
        if data_text == "[DONE]":
            accumulator.complete = bool(accumulator.text.strip())
            if accumulator.complete and on_checkpoint is not None:
                on_checkpoint(strip_inline_reasoning(accumulator.text), True, accumulator.response_id)
            continue
        try:
            event = json.loads(data_text)
        except (TypeError, ValueError):
            continue
        if not isinstance(event, dict):
            continue
        if not accumulator.response_id:
            accumulator.response_id = str(event.get("id") or "")[:160]
        for choice in event.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            message = choice.get("message")
            if isinstance(delta, dict):
                accumulator.text += _text_content(delta.get("content"))
            elif isinstance(message, dict):
                # Some compatible gateways answer stream=true with a single
                # OpenAI message event rather than token deltas.
                accumulator.text = _text_content(message.get("content"))
            if choice.get("finish_reason") is not None:
                accumulator.complete = bool(accumulator.text.strip())
        if on_checkpoint is not None and accumulator.text:
            on_checkpoint(
                strip_inline_reasoning(accumulator.text),
                accumulator.complete,
                accumulator.response_id,
            )


def request_chat_completion(
    *,
    session: requests.Session,
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: tuple[int, int] | int,
    retry_delays: tuple[float, ...],
    retryable_status_codes: frozenset[int],
    route_kwargs: Callable[[int, bool], dict[str, Any]],
    is_retryable_network_error: Callable[[requests.RequestException], bool],
    sleep: Callable[[float], None],
    network_error: Callable[[requests.RequestException, int, tuple[float, ...]], Exception],
    http_error: Callable[[Any, int], None],
    invalid_json_error: Callable[[], Exception],
    missing_content_error: Callable[[], Exception],
    empty_content_error: Callable[[], Exception],
    strip_result: bool = False,
    on_attempt: Callable[[int, str], None] | None = None,
    extra_headers: dict[str, str] | None = None,
    on_checkpoint: Callable[[str, bool, str], None] | None = None,
) -> ChatTransportResult:
    """Run one OpenAI-compatible chat request with a caller-owned paid retry policy.

    The transport never logs payloads, API keys, URLs, response bodies, lyrics, or
    prompt/template text. Provider-specific wording and HTTP classification remain
    caller callbacks so existing public error contracts stay compatible.
    """
    attempt = 0
    streaming = payload.get("stream") is True
    while True:
        attempt += 1
        on_attempt and on_attempt(attempt, "start")
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            if extra_headers:
                headers.update({str(key): str(value) for key, value in extra_headers.items()})
            response = session.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
                stream=streaming,
                **route_kwargs(attempt, bool(retry_delays)),
            )
        except requests.RequestException as error:
            can_retry = is_retryable_network_error(error)
            if can_retry and attempt <= len(retry_delays):
                on_attempt and on_attempt(attempt, "retry_network")
                sleep(retry_delays[attempt - 1])
                continue
            raise network_error(error, attempt, retry_delays) from error
        if response.status_code in retryable_status_codes and attempt <= len(retry_delays):
            on_attempt and on_attempt(attempt, f"retry_http_{response.status_code}")
            close = getattr(response, "close", None)
            if callable(close):
                close()
            sleep(retry_delays[attempt - 1])
            continue
        break

    if response.status_code != 200:
        http_error(response, attempt)
    content_type = str(getattr(response, "headers", {}).get("Content-Type", "")).lower()
    if streaming and callable(getattr(response, "iter_lines", None)) and "json" not in content_type:
        accumulator = _StreamAccumulator()
        try:
            _consume_openai_stream(response, accumulator, on_checkpoint)
        except requests.RequestException as error:
            # Once HTTP 200 or any stream bytes arrived, the paid request was
            # accepted. Never resubmit it blindly. A finish marker is enough to
            # return the fully checkpointed answer even if the proxy drops the
            # final connection close.
            if accumulator.complete and accumulator.text.strip():
                content = strip_inline_reasoning(accumulator.text)
                on_attempt and on_attempt(attempt, "success_after_stream_disconnect")
                return ChatTransportResult(content.strip() if strip_result else content, attempt, accumulator.response_id)
            raise network_error(error, attempt, ()) from error
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        content = strip_inline_reasoning(accumulator.text)
        if not accumulator.complete:
            raise missing_content_error()
        if not content.strip():
            raise empty_content_error()
        on_attempt and on_attempt(attempt, "success")
        return ChatTransportResult(content.strip() if strip_result else content, attempt, accumulator.response_id)
    try:
        data = response.json()
    except ValueError as error:
        raise invalid_json_error() from error
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise missing_content_error() from error
    content = _text_content(content)
    if isinstance(content, str):
        content = strip_inline_reasoning(content)
    if not isinstance(content, str) or not content.strip():
        raise empty_content_error()
    response_id = str(data.get("id") or "")[:160] if isinstance(data, dict) else ""
    if on_checkpoint is not None:
        on_checkpoint(content, True, response_id)
    on_attempt and on_attempt(attempt, "success")
    return ChatTransportResult(content.strip() if strip_result else content, attempt, response_id)
