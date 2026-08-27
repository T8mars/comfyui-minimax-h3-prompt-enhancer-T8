from __future__ import annotations

import importlib
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
        _implementation = importlib.import_module(
            ".local_qwen_standalone_runtime",
            package=__package__,
        )
    except ModuleNotFoundError as error:
        expected = f"{__package__}.local_qwen_standalone_runtime"
        if error.name not in {"local_qwen_standalone_runtime", expected}:
            raise
        _implementation = importlib.import_module(
            ".local_qwen_python_runtime",
            package=__package__,
        )
else:
    try:
        _implementation = importlib.import_module("local_qwen_standalone_runtime")
    except ModuleNotFoundError as error:
        if error.name != "local_qwen_standalone_runtime":
            raise
        _implementation = importlib.import_module("local_qwen_python_runtime")

sys.modules[__name__] = _implementation
