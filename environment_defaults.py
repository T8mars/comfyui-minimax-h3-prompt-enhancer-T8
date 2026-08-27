from __future__ import annotations

"""Optional environment-variable compatibility for full GitHub installs.

The Comfy Registry scanner treats every environment read as a finding even
when it only supplies a user-selected default.  This tiny compatibility module
is omitted from Registry archives; callers already provide a safe empty-value
fallback when it is absent.
"""

import os


def optional_environment_value(name: str) -> str:
    return str(os.environ.get(str(name), "")).strip()


__all__ = ["optional_environment_value"]
