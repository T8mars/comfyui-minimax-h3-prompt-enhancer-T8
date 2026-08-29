from __future__ import annotations

import functools
import os
import re
import struct
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO


NODE_ROOT = Path(__file__).resolve().parent
MODEL_CATEGORY = "LLM"
MODEL_SUBDIRECTORY = Path("LLM")
LEGACY_QWEN_SUBDIRECTORY = MODEL_SUBDIRECTORY / "Qwen3.8"
AUTO_MMPROJ = "AUTO（自动匹配）"
GGUF_SUFFIX = ".gguf"

_CATALOG_LOCK = threading.RLock()
_CATALOG_CACHE: tuple[float, tuple["GGUFModelInfo", ...]] | None = None
_CATALOG_TTL_SECONDS = 10.0
_MAX_METADATA_STRING_BYTES = 16 * 1024 * 1024
_MAX_ARRAY_ITEMS = 4_000_000


class GGUFMetadataError(RuntimeError):
    pass


@dataclass(frozen=True)
class GGUFModelInfo:
    identifier: str
    path: str
    filename: str
    size: int
    architecture: str = ""
    model_type: str = ""
    name: str = ""
    context_length: int = 0
    projector_type: str = ""
    has_vision_encoder: bool = False
    has_chat_template: bool = False
    metadata_readable: bool = False
    metadata_error: str = ""

    @property
    def is_projector(self) -> bool:
        filename = self.filename.casefold()
        return (
            self.model_type.casefold() == "mmproj"
            or self.architecture.casefold() == "clip"
            or filename.startswith("mmproj")
            or "mmproj" in filename
        )

    @property
    def is_model(self) -> bool:
        return not self.is_projector

    def as_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("path", None)
        payload.update(
            is_projector=self.is_projector,
            text_capable=self.is_model,
        )
        return payload


def _models_root() -> Path:
    try:
        import folder_paths

        return Path(folder_paths.models_dir).resolve()
    except (ImportError, AttributeError):
        return (NODE_ROOT.parents[1] / "models").resolve()


def llm_model_directory() -> Path:
    return (_models_root() / MODEL_SUBDIRECTORY).resolve()


def legacy_qwen_model_directory() -> Path:
    return (_models_root() / LEGACY_QWEN_SUBDIRECTORY).resolve()


def _registered_model_roots() -> tuple[Path, ...]:
    default_root = llm_model_directory()
    roots: list[Path] = [default_root]
    try:
        import folder_paths

        if MODEL_CATEGORY not in folder_paths.folder_names_and_paths:
            folder_paths.folder_names_and_paths[MODEL_CATEGORY] = (
                [str(default_root)],
                {GGUF_SUFFIX},
            )
        else:
            paths, extensions = folder_paths.folder_names_and_paths[MODEL_CATEGORY]
            if str(default_root) not in paths:
                paths.append(str(default_root))
            if hasattr(extensions, "add"):
                extensions.add(GGUF_SUFFIX)
        roots = [Path(value).resolve() for value in folder_paths.get_folder_paths(MODEL_CATEGORY)]
    except (ImportError, AttributeError, KeyError, TypeError, ValueError):
        pass
    result: list[Path] = []
    for root in roots:
        if root not in result:
            result.append(root)
    return tuple(result)


def _read_exact(handle: BinaryIO, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise GGUFMetadataError("Unexpected end of GGUF metadata.")
    return data


def _unpack(handle: BinaryIO, layout: str) -> Any:
    size = struct.calcsize(layout)
    return struct.unpack(layout, _read_exact(handle, size))[0]


def _read_string(handle: BinaryIO, *, keep: bool) -> str:
    length = int(_unpack(handle, "<Q"))
    if length < 0 or length > _MAX_METADATA_STRING_BYTES:
        raise GGUFMetadataError("GGUF metadata string is unreasonably large.")
    data = _read_exact(handle, length)
    return data.decode("utf-8", errors="replace") if keep else ""


_SCALAR_LAYOUTS = {
    0: "<B",   # UINT8
    1: "<b",   # INT8
    2: "<H",   # UINT16
    3: "<h",   # INT16
    4: "<I",   # UINT32
    5: "<i",   # INT32
    6: "<f",   # FLOAT32
    7: "<?",   # BOOL
    10: "<Q",  # UINT64
    11: "<q",  # INT64
    12: "<d",  # FLOAT64
}


def _read_value(handle: BinaryIO, value_type: int, *, keep: bool) -> Any:
    if value_type in _SCALAR_LAYOUTS:
        value = _unpack(handle, _SCALAR_LAYOUTS[value_type])
        return value if keep else None
    if value_type == 8:  # STRING
        return _read_string(handle, keep=keep)
    if value_type == 9:  # ARRAY
        element_type = int(_unpack(handle, "<I"))
        length = int(_unpack(handle, "<Q"))
        if length < 0 or length > _MAX_ARRAY_ITEMS:
            raise GGUFMetadataError("GGUF metadata array is unreasonably large.")
        if element_type in _SCALAR_LAYOUTS and not keep:
            handle.seek(struct.calcsize(_SCALAR_LAYOUTS[element_type]) * length, os.SEEK_CUR)
            return None
        values = [_read_value(handle, element_type, keep=keep) for _ in range(length)]
        return values if keep else None
    raise GGUFMetadataError(f"Unsupported GGUF metadata value type: {value_type}.")


def _metadata_values(path: Path) -> dict[str, Any]:
    wanted = {
        "general.architecture",
        "general.type",
        "general.name",
        "tokenizer.chat_template",
        "clip.projector_type",
        "clip.has_vision_encoder",
    }
    values: dict[str, Any] = {}
    with path.open("rb") as handle:
        if _read_exact(handle, 4) != b"GGUF":
            raise GGUFMetadataError("File does not start with the GGUF magic header.")
        version = int(_unpack(handle, "<I"))
        if version not in (2, 3):
            raise GGUFMetadataError(f"Unsupported GGUF version: {version}.")
        _tensor_count = int(_unpack(handle, "<Q"))
        kv_count = int(_unpack(handle, "<Q"))
        if kv_count < 0 or kv_count > 1_000_000:
            raise GGUFMetadataError("GGUF metadata entry count is invalid.")
        for _index in range(kv_count):
            key = _read_string(handle, keep=True)
            value_type = int(_unpack(handle, "<I"))
            keep = key in wanted or key.endswith(".context_length")
            value = _read_value(handle, value_type, keep=keep)
            if keep:
                values[key] = value
    return values


@functools.lru_cache(maxsize=512)
def _cached_model_info(path_value: str, identifier: str, size: int, mtime_ns: int) -> GGUFModelInfo:
    del mtime_ns
    path = Path(path_value)
    try:
        values = _metadata_values(path)
        architecture = str(values.get("general.architecture") or "")
        context_keys = [key for key in values if key.endswith(".context_length")]
        context_length = int(values.get(f"{architecture}.context_length") or 0)
        if not context_length and context_keys:
            context_length = int(values.get(context_keys[0]) or 0)
        return GGUFModelInfo(
            identifier=identifier,
            path=str(path),
            filename=path.name,
            size=size,
            architecture=architecture,
            model_type=str(values.get("general.type") or ""),
            name=str(values.get("general.name") or ""),
            context_length=context_length,
            projector_type=str(values.get("clip.projector_type") or ""),
            has_vision_encoder=bool(values.get("clip.has_vision_encoder", False)),
            has_chat_template=bool(str(values.get("tokenizer.chat_template") or "").strip()),
            metadata_readable=True,
        )
    except (OSError, ValueError, TypeError, GGUFMetadataError) as error:
        return GGUFModelInfo(
            identifier=identifier,
            path=str(path),
            filename=path.name,
            size=size,
            metadata_error=str(error),
        )


def _identifier_for(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    # The original node stored only the filename for models placed in the
    # historical Qwen3.8 folder. Keep that exact workflow value valid.
    if root == llm_model_directory() and path.parent == legacy_qwen_model_directory():
        return path.name
    return relative


def scan_gguf_catalog(*, refresh: bool = False) -> tuple[GGUFModelInfo, ...]:
    global _CATALOG_CACHE
    now = time.monotonic()
    with _CATALOG_LOCK:
        if not refresh and _CATALOG_CACHE and now - _CATALOG_CACHE[0] < _CATALOG_TTL_SECONDS:
            return _CATALOG_CACHE[1]
        entries: dict[str, GGUFModelInfo] = {}
        for root in _registered_model_roots():
            if not root.is_dir():
                continue
            try:
                paths = root.rglob("*")
                for path in paths:
                    if not path.is_file() or path.suffix.casefold() != GGUF_SUFFIX:
                        continue
                    resolved = path.resolve()
                    # Keep the user-facing identifier anchored to the lexical
                    # models/LLM path, while allowing the file itself to be a
                    # symlink into a mounted model store.  Path traversal is
                    # still blocked when identifiers are resolved for use.
                    identifier = _identifier_for(path, root)
                    # The first registered root wins on identifier collisions,
                    # matching ComfyUI's model folder resolution behavior.
                    if identifier in entries:
                        continue
                    stat = resolved.stat()
                    entries[identifier] = _cached_model_info(
                        str(resolved), identifier, int(stat.st_size), int(stat.st_mtime_ns)
                    )
            except OSError:
                continue
        catalog = tuple(sorted(entries.values(), key=lambda item: item.identifier.casefold()))
        _CATALOG_CACHE = (now, catalog)
        return catalog


def _safe_identifier(value: str, *, label: str) -> str:
    identifier = str(value or "").strip().replace("\\", "/")
    if not identifier:
        raise GGUFMetadataError(f"{label} is empty.")
    path = Path(identifier)
    if path.is_absolute() or ".." in path.parts or path.suffix.casefold() != GGUF_SUFFIX:
        raise GGUFMetadataError(f"{label} must be a relative GGUF path inside ComfyUI/models/LLM.")
    return Path(*path.parts).as_posix()


def resolve_gguf_path(identifier: str, *, label: str, required: bool = True) -> Path:
    safe = _safe_identifier(identifier, label=label)
    roots = _registered_model_roots()
    legacy_root = legacy_qwen_model_directory()
    candidates: list[Path] = []
    if "/" not in safe:
        candidates.append((legacy_root / safe).resolve())
    candidates.extend((root / Path(safe)).resolve() for root in roots)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if "/" not in safe:
        matches = [
            Path(item.path)
            for item in scan_gguf_catalog()
            if item.filename.casefold() == safe.casefold()
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            choices = ", ".join(item.identifier for item in scan_gguf_catalog() if Path(item.path) in matches)
            raise GGUFMetadataError(
                f"{label} filename is ambiguous. Select its relative path instead: {choices}"
            )
    fallback = candidates[0] if candidates else llm_model_directory() / safe
    if required:
        raise GGUFMetadataError(f"Missing {label}: {fallback}.")
    return fallback


def model_info_for(identifier: str) -> GGUFModelInfo | None:
    try:
        path = resolve_gguf_path(identifier, label="local GGUF", required=False)
    except GGUFMetadataError:
        return None
    if not path.is_file():
        return None
    stat = path.stat()
    for item in scan_gguf_catalog():
        if Path(item.path) == path:
            return item
    return _cached_model_info(str(path), identifier, int(stat.st_size), int(stat.st_mtime_ns))


def model_info_for_path(path: Path) -> GGUFModelInfo | None:
    resolved = Path(path).resolve()
    for item in scan_gguf_catalog():
        if Path(item.path) == resolved:
            return item
    if not resolved.is_file() or resolved.suffix.casefold() != GGUF_SUFFIX:
        return None
    stat = resolved.stat()
    return _cached_model_info(
        str(resolved), resolved.name, int(stat.st_size), int(stat.st_mtime_ns)
    )


def model_options() -> list[str]:
    values = [item.identifier for item in scan_gguf_catalog() if item.is_model]
    return values


def projector_options() -> list[str]:
    values = [item.identifier for item in scan_gguf_catalog() if item.is_projector]
    return [AUTO_MMPROJ, *values]


def _normalized_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _filename_tokens(value: str) -> set[str]:
    normalized = value.casefold().replace(".gguf", "")
    for separator in ("-", "_", "."):
        normalized = normalized.replace(separator, " ")
    ignored = {
        "mmproj", "f16", "f32", "bf16", "q8", "q8_0", "q4", "q4_k_m",
        "q6", "q6_k", "q3", "q3_k_s", "gguf", "fp8",
    }
    return {token for token in normalized.split() if token and token not in ignored}


def _parameter_scale(*values: str) -> str:
    for value in values:
        match = re.search(r"(?<![a-z0-9])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", value.casefold())
        if match:
            token = match.group(1)
            if "." in token:
                token = token.rstrip("0").rstrip(".")
            return token + "b"
    return ""


def _vision_family(*values: str) -> str:
    # Values are ordered from strongest metadata to weakest filename hints.
    # Return on the first recognized source so a descriptive filename cannot
    # override an authoritative architecture or projector type.
    for value in values:
        normalized = str(value or "").casefold()
        compact = "".join(character for character in normalized if character.isalnum())
        if "gemma4" in compact:
            return "gemma4"
        if "gemma3" in compact:
            return "gemma3"
        if "qwen3" in compact:
            return "qwen3"
        if "qwen2" in compact:
            return "qwen2"
    return ""


def recommended_projector(model_identifier: str) -> GGUFModelInfo | None:
    model = model_info_for(model_identifier)
    if model is None or model.is_projector:
        return None
    projectors = [item for item in scan_gguf_catalog() if item.is_projector]
    if not projectors:
        return None
    model_name = _normalized_name(model.name)
    model_parent = Path(model.path).parent
    model_scale = _parameter_scale(model.name, model.filename)
    model_family = _vision_family(model.architecture, model.name, model.filename)
    compatible_projectors: list[GGUFModelInfo] = []
    for projector in projectors:
        projector_family = _vision_family(
            projector.projector_type,
            projector.name,
            projector.filename,
        )
        if model_family and projector_family and model_family != projector_family:
            continue
        projector_scale = _parameter_scale(projector.name, projector.filename)
        if model_scale and projector_scale and model_scale != projector_scale:
            continue
        compatible_projectors.append(projector)
    projectors = compatible_projectors
    if not projectors:
        return None

    def score(projector: GGUFModelInfo) -> tuple[int, str]:
        value = 0
        projector_name = _normalized_name(projector.name)
        if model_name and projector_name and model_name == projector_name:
            value += 100
        if Path(projector.path).parent == model_parent:
            value += 40
        projector_scale = _parameter_scale(projector.name, projector.filename)
        if model_scale and projector_scale:
            # A same-directory projector is not enough: a 27B projector must
            # never be auto-selected for a 9B model. Matching parameter scale
            # is a much stronger compatibility signal than folder placement.
            value += 60 if model_scale == projector_scale else -120
        if model.architecture.casefold() == "qwen35" and "qwen3vl" in projector.projector_type.casefold():
            value += 25
        projector_family = _vision_family(
            projector.projector_type,
            projector.name,
            projector.filename,
        )
        if model_family and projector_family == model_family:
            value += 80
        if projector.has_vision_encoder:
            value += 5
        model_tokens = _filename_tokens(model.filename)
        projector_tokens = _filename_tokens(projector.filename)
        if model_tokens and projector_tokens:
            overlap = len(model_tokens & projector_tokens) / len(model_tokens | projector_tokens)
            value += round(overlap * 30)
        return value, projector.identifier.casefold()

    ranked = sorted(projectors, key=lambda item: (-score(item)[0], score(item)[1]))
    best = ranked[0]
    best_score = score(best)[0]
    if best_score >= 40:
        return best
    if len(projectors) == 1:
        projector_scale = _parameter_scale(best.name, best.filename)
        if model_scale and projector_scale and model_scale != projector_scale:
            return None
        return best
    return None


def resolve_projector_path(selection: str, *, model_identifier: str) -> Path:
    value = str(selection or "").strip()
    if not value or value == AUTO_MMPROJ:
        projector = recommended_projector(model_identifier)
        if projector is None:
            raise GGUFMetadataError(
                "No matching vision projector was found. Put the model's mmproj GGUF in "
                f"{llm_model_directory()} or select it explicitly."
            )
        return Path(projector.path)
    path = resolve_gguf_path(value, label="local vision projector")
    info = model_info_for(value)
    if info is not None and info.metadata_readable and not info.is_projector:
        raise GGUFMetadataError(f"Selected vision projector is a model GGUF, not an mmproj: {value}")
    return path


def catalog_public_payload(*, refresh: bool = False) -> dict[str, Any]:
    catalog = scan_gguf_catalog(refresh=refresh)
    models = [item for item in catalog if item.is_model]
    projectors = [item for item in catalog if item.is_projector]
    model_payload: list[dict[str, Any]] = []
    for item in models:
        data = item.as_public_dict()
        projector = recommended_projector(item.identifier)
        data["recommended_projector"] = projector.identifier if projector else ""
        data["vision_capable"] = projector is not None
        model_payload.append(data)
    return {
        "model_directory": str(llm_model_directory()),
        "model_count": len(models),
        "projector_count": len(projectors),
        "models": model_payload,
        "projectors": [item.as_public_dict() for item in projectors],
        "model_options": [item.identifier for item in models],
        "projector_options": [AUTO_MMPROJ, *(item.identifier for item in projectors)],
    }


__all__ = [
    "AUTO_MMPROJ",
    "GGUFMetadataError",
    "GGUFModelInfo",
    "catalog_public_payload",
    "legacy_qwen_model_directory",
    "llm_model_directory",
    "model_info_for",
    "model_info_for_path",
    "model_options",
    "projector_options",
    "recommended_projector",
    "resolve_gguf_path",
    "resolve_projector_path",
    "scan_gguf_catalog",
]
