from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import requests


@dataclass(frozen=True)
class ChatTransportResult:
    text: str
    attempts: int


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
) -> ChatTransportResult:
    """Run one OpenAI-compatible chat request with a caller-owned paid retry policy.

    The transport never logs payloads, API keys, URLs, response bodies, lyrics, or
    prompt/template text. Provider-specific wording and HTTP classification remain
    caller callbacks so existing public error contracts stay compatible.
    """
    attempt = 0
    while True:
        attempt += 1
        on_attempt and on_attempt(attempt, "start")
        try:
            response = session.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
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
            sleep(retry_delays[attempt - 1])
            continue
        break

    if response.status_code != 200:
        http_error(response, attempt)
    try:
        data = response.json()
    except ValueError as error:
        raise invalid_json_error() from error
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise missing_content_error() from error
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        )
    if not isinstance(content, str) or not content.strip():
        raise empty_content_error()
    on_attempt and on_attempt(attempt, "success")
    return ChatTransportResult(content.strip() if strip_result else content, attempt)
