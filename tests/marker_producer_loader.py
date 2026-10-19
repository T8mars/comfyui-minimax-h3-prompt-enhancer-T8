"""Explicit read-only integration loader; never executed by production nodes."""
import importlib
from pathlib import Path
import sys
import types


def load_producer(path):
    root = Path(path).resolve() / "h3_t8"
    if not (root / "visual_marker.py").is_file():
        raise ValueError("Explicit producer checkout must contain h3_t8/visual_marker.py")
    # No plugin entrypoint, model loading or bytecode writes in the other repo.
    sys.dont_write_bytecode = True
    name = "t8_readonly_marker_integration"
    package = types.ModuleType(name)
    package.__path__ = [str(root)]
    sys.modules[name] = package
    return importlib.import_module(name + ".visual_marker")
