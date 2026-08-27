from __future__ import annotations

from typing import Any

import requests


def test_cloud_connection(secret: str, chat_url: str, model_id: str) -> dict[str, Any]:
    """Run the optional credential-store connectivity probe.

    This helper is distributed by GitHub.  Registry archives omit it because
    the Registry YARA policy flags every direct network probe, while the actual
    prompt providers continue to use the audited shared transport.
    """

    try:
        response = requests.post(
            chat_url,
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "Reply with OK."}],
                "max_tokens": 2,
                "stream": False,
            },
            timeout=(10, 45),
        )
    except requests.RequestException:
        return {"connected": False, "category": "network"}
    if 200 <= response.status_code < 300:
        return {"connected": True, "category": "ok"}
    if response.status_code in {401, 403}:
        category = "authentication"
    elif response.status_code == 402:
        category = "billing"
    elif response.status_code == 429:
        category = "rate_limit"
    elif response.status_code >= 500:
        category = "upstream_temporarily_unavailable"
    else:
        category = "request_rejected"
    return {"connected": False, "category": category}


__all__ = ["test_cloud_connection"]
