from __future__ import annotations

import sys

"""Select the richest local GGUF runtime shipped by the current install.

GitHub clones contain ``local_qwen_standalone_runtime.py`` and therefore keep
the pinned llama-server/PATH/llama-cpp-python compatibility stack.  The Comfy
Registry archive intentionally omits the standalone process launcher so its
automated security review can distribute the node without flagging legitimate
``subprocess`` and loopback-socket use.  Registry installs transparently fall
back to the in-process llama-cpp-python implementation.
"""

if __package__:
    try:
        from .local_qwen_standalone_runtime import *  # noqa: F403

        _implementation = sys.modules[f"{__package__}.local_qwen_standalone_runtime"]
    except ModuleNotFoundError as error:
        expected = f"{__package__}.local_qwen_standalone_runtime"
        if error.name not in {"local_qwen_standalone_runtime", expected}:
            raise
        from .local_qwen_python_runtime import *  # noqa: F403

        _implementation = sys.modules[f"{__package__}.local_qwen_python_runtime"]
else:
    try:
        from local_qwen_standalone_runtime import *  # noqa: F403

        _implementation = sys.modules["local_qwen_standalone_runtime"]
    except ModuleNotFoundError as error:
        if error.name != "local_qwen_standalone_runtime":
            raise
        from local_qwen_python_runtime import *  # noqa: F403

        _implementation = sys.modules["local_qwen_python_runtime"]

sys.modules[__name__] = _implementation
