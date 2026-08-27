from __future__ import annotations

import atexit
import gc
import importlib.util
import inspect
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .local_gguf_catalog import (
        AUTO_MMPROJ,
        GGUFMetadataError,
        catalog_public_payload,
        legacy_qwen_model_directory,
        llm_model_directory,
        model_info_for_path,
        model_options,
        projector_options,
        resolve_gguf_path,
        resolve_projector_path,
    )
except ImportError:
    from local_gguf_catalog import (
        AUTO_MMPROJ,
        GGUFMetadataError,
        catalog_public_payload,
        legacy_qwen_model_directory,
        llm_model_directory,
        model_info_for_path,
        model_options,
        projector_options,
        resolve_gguf_path,
        resolve_projector_path,
    )


LLAMA_CPP_PYTHON_WHEELS_URL = "https://github.com/JamePeng/llama-cpp-python/releases"
DEFAULT_MODEL_FILENAME = "Qwen3.8-27B-Q4_K_M.gguf"
UNCENSORED_MODEL_FILENAME = "qwen3.8-27b-uncensored-fp8-q4_k_m.gguf"
HERETIC_9B_MODEL_FILENAME = "Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf"
DEFAULT_MMPROJ_FILENAME = "mmproj-F16.gguf"
DEFAULT_MODEL_SIZE = 17_106_775_008
DEFAULT_MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
UNCENSORED_MODEL_SIZE = 16_810_714_976
UNCENSORED_MODEL_SHA256 = "66bb238d41de38b11dd406d932d8fb97433d529022cef60f2f422b9221cae743"
HERETIC_9B_MODEL_SIZE = 7_359_260_416
HERETIC_9B_MODEL_SHA256 = "dfedf8412ee4a7f1200916783d224ebedb87044784434b75f4068b4b5e25f780"
DEFAULT_MMPROJ_SIZE = 927_607_488
DEFAULT_MMPROJ_SHA256 = "cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e"
KNOWN_MODEL_FILES = {
    DEFAULT_MODEL_FILENAME: (DEFAULT_MODEL_SIZE, DEFAULT_MODEL_SHA256),
    UNCENSORED_MODEL_FILENAME: (UNCENSORED_MODEL_SIZE, UNCENSORED_MODEL_SHA256),
    HERETIC_9B_MODEL_FILENAME: (HERETIC_9B_MODEL_SIZE, HERETIC_9B_MODEL_SHA256),
}
LLAMA_SEED_MODULUS = 0xFFFFFFFF

LOCAL_UNLOAD_AFTER_RUN = "执行后卸载（推荐）"
LOCAL_KEEP_WARM = "保持驻留"
LOCAL_IDLE_TTL = "空闲10分钟后卸载"
LOCAL_UNLOAD_POLICIES = [LOCAL_UNLOAD_AFTER_RUN, LOCAL_KEEP_WARM, LOCAL_IDLE_TTL]
LOCAL_IDLE_TTL_SECONDS = 600

LOCAL_RELEASE_COMFY_AUTO = "AUTO（显存不足时释放）"
LOCAL_KEEP_COMFY_MODELS = "不主动释放 ComfyUI 模型"
LOCAL_COMFY_MEMORY_POLICIES = [LOCAL_RELEASE_COMFY_AUTO, LOCAL_KEEP_COMFY_MODELS]

LOCAL_THINK_OFF = "关闭（推荐，速度优先）"
LOCAL_THINK_ON = "开启（质量优先）"
LOCAL_THINK_OPTIONS = [LOCAL_THINK_OFF, LOCAL_THINK_ON]
LOCAL_REASONING_OPTIONS = ["low", "medium", "xhigh"]


class LocalQwenRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class PythonRuntimeSpec:
    backend: str = "llama-cpp-python"
    version: str = "unknown"
    source: str = "ComfyUI Python environment"


_THINK_BLOCK_PATTERN = re.compile(r"<think(?:\s[^>]*)?>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
_LEADING_THINK_END_PATTERN = re.compile(r"^\s*</think\s*>\s*", re.IGNORECASE)
_UNCLOSED_THINK_PATTERN = re.compile(r"<think(?:\s[^>]*)?>", re.IGNORECASE)


def normalize_llama_seed(seed: int) -> int:
    return int(seed) % LLAMA_SEED_MODULUS


def _finalize_local_content(content: Any, *, think_mode: bool) -> str:
    if isinstance(content, list):
        content = "".join(
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        )
    if not isinstance(content, str):
        return ""
    text = content.strip()
    if think_mode:
        return text
    text = _THINK_BLOCK_PATTERN.sub("", text)
    text = _LEADING_THINK_END_PATTERN.sub("", text)
    unclosed = _UNCLOSED_THINK_PATTERN.search(text)
    if unclosed is not None:
        text = text[: unclosed.start()]
    return text.strip()


def qwen_model_directory() -> Path:
    return legacy_qwen_model_directory()


def resolve_model_path(filename: str, *, label: str, required: bool = True) -> Path:
    raw = str(filename or "").strip()
    if raw and "/" not in raw and "\\" not in raw and Path(raw).suffix.casefold() == ".gguf":
        legacy_candidate = (qwen_model_directory() / raw).resolve()
        if legacy_candidate.is_file():
            return legacy_candidate
    try:
        return resolve_gguf_path(filename, label=label, required=required)
    except GGUFMetadataError as error:
        raise LocalQwenRuntimeError(str(error)) from error


def resolve_mmproj_path(selection: str, *, model_filename: str) -> Path:
    try:
        return resolve_projector_path(selection, model_identifier=model_filename)
    except GGUFMetadataError as error:
        raise LocalQwenRuntimeError(str(error)) from error


def list_gguf_models() -> list[str]:
    return model_options() or [DEFAULT_MODEL_FILENAME]


def list_mmproj_models() -> list[str]:
    values = projector_options()
    if len(values) == 1:
        values.append(DEFAULT_MMPROJ_FILENAME)
    return values


def load_python_runtime_spec() -> PythonRuntimeSpec:
    if importlib.util.find_spec("llama_cpp") is None:
        raise LocalQwenRuntimeError(
            "llama-cpp-python is not installed in the active ComfyUI Python environment. "
            f"Optional prebuilt wheels: {LLAMA_CPP_PYTHON_WHEELS_URL}."
        )
    try:
        import llama_cpp
    except (ImportError, OSError) as error:
        raise LocalQwenRuntimeError(
            "llama-cpp-python was found but could not load its native library. "
            f"{type(error).__name__}: {error}"
        ) from error
    return PythonRuntimeSpec(version=str(getattr(llama_cpp, "__version__", "unknown")))


def available_runtime_specs() -> tuple[list[PythonRuntimeSpec], list[str]]:
    try:
        return [load_python_runtime_spec()], []
    except LocalQwenRuntimeError as error:
        return [], [str(error)]


def select_runtime_spec() -> PythonRuntimeSpec:
    specs, warnings = available_runtime_specs()
    if specs:
        return specs[0]
    details = " ".join(warnings)
    raise LocalQwenRuntimeError(
        "No usable in-process local llama.cpp runtime was found. Install llama-cpp-python in the "
        "active ComfyUI Python environment and fully restart ComfyUI. "
        f"Optional prebuilt wheels: {LLAMA_CPP_PYTHON_WHEELS_URL}. {details}"
    )


def runtime_status(*, refresh: bool = False) -> dict[str, Any]:
    model_status: dict[str, bool] = {}
    for filename, (expected_size, _expected_sha256) in KNOWN_MODEL_FILES.items():
        path = resolve_model_path(filename, label="local model", required=False)
        model_status[filename] = bool(path.is_file() and path.stat().st_size == expected_size)
    mmproj_path = resolve_model_path(DEFAULT_MMPROJ_FILENAME, label="vision projector", required=False)
    mmproj_installed = bool(
        mmproj_path.is_file() and mmproj_path.stat().st_size == DEFAULT_MMPROJ_SIZE
    )
    catalog = catalog_public_payload(refresh=refresh)
    verified_names = {filename for filename, installed in model_status.items() if installed}
    for item in catalog.get("models", []):
        if item.get("filename") in verified_names:
            item["verification_tier"] = "project_tested_pinned_size_match"
        elif item.get("metadata_readable"):
            item["verification_tier"] = "runtime_supported_unverified"
        else:
            item["verification_tier"] = "discovered_unverified"
    specs, warnings = available_runtime_specs()
    any_model_installed = any(model_status.values())
    result: dict[str, Any] = {
        "runtime_installed": bool(specs),
        "model_installed": bool(model_status.get(DEFAULT_MODEL_FILENAME)),
        "uncensored_model_installed": bool(model_status.get(UNCENSORED_MODEL_FILENAME)),
        "heretic_9b_model_installed": bool(model_status.get(HERETIC_9B_MODEL_FILENAME)),
        "available_verified_models": [
            filename for filename, installed in model_status.items() if installed
        ],
        "mmproj_installed": mmproj_installed,
        **catalog,
        "legacy_model_directory": str(qwen_model_directory()),
        "llama_cpp_python_wheels_url": LLAMA_CPP_PYTHON_WHEELS_URL,
        "runtime_distribution": "registry_in_process",
    }
    if specs:
        result.update(
            backend=specs[0].backend,
            runtime_source=specs[0].source,
            runtime_backends=[
                {
                    "backend": item.backend,
                    "source": item.source,
                    "version": item.version,
                }
                for item in specs
            ],
        )
    if warnings:
        result["runtime_warnings"] = warnings
    discovered_models = int(catalog.get("model_count") or 0)
    discovered_projectors = int(catalog.get("projector_count") or 0)
    result["text_ready"] = bool(result["runtime_installed"] and (discovered_models or any_model_installed))
    result["vision_ready"] = bool(
        result["text_ready"]
        and (
            mmproj_installed
            or (
                discovered_projectors
                and any(item.get("vision_capable") for item in catalog.get("models", []))
            )
        )
    )
    return result


def _throw_if_interrupted() -> None:
    try:
        from comfy import model_management

        model_management.throw_exception_if_processing_interrupted()
    except ImportError:
        return


def _release_comfy_models_if_needed(policy: str) -> None:
    if policy != LOCAL_RELEASE_COMFY_AUTO:
        return
    try:
        from comfy import model_management

        free_memory = int(model_management.get_free_memory())
        if free_memory < 22 * 1024**3:
            model_management.unload_all_models()
            model_management.soft_empty_cache()
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return


class LlamaPythonRuntime:
    def __init__(
        self,
        *,
        model: Path,
        mmproj: Path | None,
        context_size: int,
        spec: PythonRuntimeSpec,
        think_mode: bool,
    ):
        self.model = model
        self.mmproj = mmproj
        self.context_size = int(context_size)
        self.spec = spec
        self.think_mode = bool(think_mode)
        self.llm: Any = None
        self.chat_handler: Any = None
        self._stop_lock = threading.RLock()

    @property
    def is_running(self) -> bool:
        return self.llm is not None

    def _handler_class(self, architecture: str) -> tuple[type[Any], dict[str, Any]]:
        try:
            from llama_cpp import llama_chat_format
        except (ImportError, OSError) as error:
            raise LocalQwenRuntimeError("llama-cpp-python chat handlers could not be loaded.") from error
        normalized = architecture.casefold().replace("-", "").replace("_", "")
        candidates: list[tuple[str, dict[str, Any]]] = []
        if normalized == "qwen35":
            candidates.append(("Qwen35ChatHandler", {"enable_thinking": self.think_mode}))
        elif "qwen3" in normalized:
            candidates.append(("Qwen3VLChatHandler", {"force_reasoning": self.think_mode}))
        elif "qwen2" in normalized:
            candidates.append(("Qwen25VLChatHandler", {}))
        elif "gemma3" in normalized:
            candidates.append(("Gemma3ChatHandler", {}))
        elif "gemma4" in normalized:
            candidates.append(("Gemma4ChatHandler", {}))
        candidates.append(("MTMDChatHandler", {}))
        for name, options in candidates:
            handler = getattr(llama_chat_format, name, None)
            if handler is not None:
                return handler, options
        raise LocalQwenRuntimeError(
            "The installed llama-cpp-python build has no compatible multimodal chat handler. "
            "Install a newer matching wheel."
        )

    def start(self, timeout: float = 240.0) -> None:
        del timeout
        try:
            from llama_cpp import Llama
        except (ImportError, OSError) as error:
            raise LocalQwenRuntimeError(
                "llama-cpp-python could not be imported from the active ComfyUI Python environment."
            ) from error
        handler = None
        if self.mmproj is not None:
            model_info = model_info_for_path(self.model)
            architecture = model_info.architecture if model_info else ""
            handler_class, handler_options = self._handler_class(architecture)
            try:
                handler = handler_class(
                    clip_model_path=str(self.mmproj),
                    verbose=False,
                    use_gpu=True,
                    image_min_tokens=1024,
                    image_max_tokens=1024,
                    **handler_options,
                )
            except (TypeError, ValueError, RuntimeError, OSError) as error:
                raise LocalQwenRuntimeError(
                    "llama-cpp-python could not initialize the selected model/mmproj pair. "
                    f"{type(error).__name__}: {error}"
                ) from error
        try:
            self.chat_handler = handler
            llama_options: dict[str, Any] = {
                "model_path": str(self.model),
                "chat_handler": handler,
                "n_gpu_layers": -1,
                "n_ctx": self.context_size,
                "verbose": False,
            }
            try:
                llama_parameters = inspect.signature(Llama).parameters
            except (TypeError, ValueError):
                llama_parameters = {}
            if "chat_template_kwargs" in llama_parameters:
                llama_options["chat_template_kwargs"] = {
                    "enable_thinking": self.think_mode,
                    "preserve_thinking": False,
                }
            self.llm = Llama(**llama_options)
        except (TypeError, ValueError, RuntimeError, OSError) as error:
            self.stop()
            raise LocalQwenRuntimeError(
                "llama-cpp-python failed to load the selected GGUF. "
                f"{type(error).__name__}: {error}"
            ) from error

    def stop(self) -> None:
        with self._stop_lock:
            llm = self.llm
            handler = self.chat_handler
            self.llm = None
            self.chat_handler = None
            try:
                if llm is not None:
                    llm.close()
            except (AttributeError, RuntimeError, OSError):
                pass
            try:
                exit_stack = getattr(handler, "_exit_stack", None)
                if exit_stack is not None:
                    exit_stack.close()
            except (AttributeError, RuntimeError, OSError):
                pass
            gc.collect()

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        seed: int,
        max_tokens: int,
        temperature: float,
        think_mode: bool,
        reasoning_effort: str,
    ) -> tuple[str, dict[str, Any]]:
        del reasoning_effort
        if self.llm is None:
            raise LocalQwenRuntimeError("llama-cpp-python model is not loaded.")
        if bool(think_mode) != self.think_mode and self.mmproj is not None:
            raise LocalQwenRuntimeError(
                "The active llama-cpp-python vision handler was loaded with a different thinking mode."
            )
        options: dict[str, Any] = {
            "messages": messages,
            "seed": normalize_llama_seed(seed),
            "max_tokens": int(max_tokens),
            "temperature": 1.0 if think_mode else float(temperature),
            "stream": False,
            "top_p": 0.95 if think_mode else 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "repeat_penalty": 1.0,
            "present_penalty": 0.0 if think_mode else 1.5,
        }
        try:
            result = self.llm.create_chat_completion(**options)
        except (TypeError, ValueError, RuntimeError, OSError) as error:
            raise LocalQwenRuntimeError(
                "llama-cpp-python inference failed. "
                f"{type(error).__name__}: {error}"
            ) from error
        try:
            content = result["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise LocalQwenRuntimeError(
                "llama-cpp-python response is missing choices[0].message.content."
            ) from error
        content = _finalize_local_content(content, think_mode=think_mode)
        if not content:
            raise LocalQwenRuntimeError(
                "The local GGUF returned no final answer. Disable thinking or increase max output tokens."
            )
        return content, result.get("usage") or {}


class LocalQwenManager:
    def __init__(self):
        self._run_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._inference_lock = threading.Lock()
        self._runtime: LlamaPythonRuntime | None = None
        self._key: tuple[Any, ...] | None = None
        self._idle_timer: threading.Timer | None = None
        self._idle_epoch = 0

    def begin_run(
        self,
        *,
        model: Path,
        mmproj: Path | None,
        context_size: int,
        comfy_memory_policy: str,
        think_mode: bool = False,
    ) -> LlamaPythonRuntime:
        while not self._run_lock.acquire(timeout=0.25):
            _throw_if_interrupted()
        try:
            return self.acquire(
                model=model,
                mmproj=mmproj,
                context_size=context_size,
                comfy_memory_policy=comfy_memory_policy,
                think_mode=think_mode,
            )
        except BaseException:
            self._run_lock.release()
            raise

    def end_run(self, unload_policy: str, *, force: bool = False) -> None:
        try:
            if force:
                self.release()
            else:
                self.finish(unload_policy)
        finally:
            self._run_lock.release()

    def _cancel_timer(self) -> None:
        self._idle_epoch += 1
        timer = self._idle_timer
        self._idle_timer = None
        if timer is not None:
            timer.cancel()

    def acquire(
        self,
        *,
        model: Path,
        mmproj: Path | None,
        context_size: int,
        comfy_memory_policy: str,
        think_mode: bool = False,
    ) -> LlamaPythonRuntime:
        spec = select_runtime_spec()
        key = (
            model.resolve(),
            mmproj.resolve() if mmproj else None,
            int(context_size),
            bool(think_mode),
            spec.version,
        )
        with self._lifecycle_lock:
            self._cancel_timer()
            if self._runtime is not None and self._key == key and self._runtime.is_running:
                return self._runtime
            self.release()
            _release_comfy_models_if_needed(comfy_memory_policy)
            runtime = LlamaPythonRuntime(
                model=model,
                mmproj=mmproj,
                context_size=context_size,
                spec=spec,
                think_mode=think_mode,
            )
            try:
                runtime.start()
            except BaseException:
                runtime.stop()
                raise
            self._runtime = runtime
            self._key = key
            return runtime

    def complete(self, runtime: LlamaPythonRuntime, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        with self._inference_lock:
            _throw_if_interrupted()
            if runtime is not self._runtime or not runtime.is_running:
                raise LocalQwenRuntimeError("Local GGUF runtime changed before the request could run.")
            return runtime.chat(**kwargs)

    def finish(self, unload_policy: str) -> None:
        if unload_policy == LOCAL_UNLOAD_AFTER_RUN:
            self.release()
            return
        if unload_policy == LOCAL_IDLE_TTL:
            with self._lifecycle_lock:
                self._cancel_timer()
                epoch = self._idle_epoch

                def release_if_still_idle() -> None:
                    if not self._run_lock.acquire(blocking=False):
                        return
                    try:
                        with self._lifecycle_lock:
                            if epoch != self._idle_epoch or self._idle_timer is not timer:
                                return
                            self._idle_timer = None
                            self._idle_epoch += 1
                            runtime = self._runtime
                            self._runtime = None
                            self._key = None
                            if runtime is not None:
                                runtime.stop()
                    finally:
                        self._run_lock.release()

                timer = threading.Timer(LOCAL_IDLE_TTL_SECONDS, release_if_still_idle)
                timer.daemon = True
                self._idle_timer = timer
                timer.start()
            return
        if unload_policy != LOCAL_KEEP_WARM:
            raise LocalQwenRuntimeError(f"Unsupported local unload policy: {unload_policy}")

    def release(self) -> None:
        with self._lifecycle_lock:
            self._cancel_timer()
            runtime = self._runtime
            self._runtime = None
            self._key = None
            if runtime is not None:
                runtime.stop()


LOCAL_QWEN_MANAGER = LocalQwenManager()
atexit.register(LOCAL_QWEN_MANAGER.release)


__all__ = [
    "AUTO_MMPROJ",
    "DEFAULT_MMPROJ_FILENAME",
    "DEFAULT_MODEL_FILENAME",
    "HERETIC_9B_MODEL_FILENAME",
    "HERETIC_9B_MODEL_SHA256",
    "HERETIC_9B_MODEL_SIZE",
    "KNOWN_MODEL_FILES",
    "LLAMA_CPP_PYTHON_WHEELS_URL",
    "UNCENSORED_MODEL_FILENAME",
    "UNCENSORED_MODEL_SHA256",
    "UNCENSORED_MODEL_SIZE",
    "LOCAL_COMFY_MEMORY_POLICIES",
    "LOCAL_IDLE_TTL",
    "LOCAL_KEEP_COMFY_MODELS",
    "LOCAL_KEEP_WARM",
    "LOCAL_QWEN_MANAGER",
    "LOCAL_REASONING_OPTIONS",
    "LOCAL_RELEASE_COMFY_AUTO",
    "LOCAL_THINK_OFF",
    "LOCAL_THINK_ON",
    "LOCAL_THINK_OPTIONS",
    "LOCAL_UNLOAD_AFTER_RUN",
    "LOCAL_UNLOAD_POLICIES",
    "LocalQwenRuntimeError",
    "LlamaPythonRuntime",
    "PythonRuntimeSpec",
    "available_runtime_specs",
    "catalog_public_payload",
    "llm_model_directory",
    "list_gguf_models",
    "list_mmproj_models",
    "normalize_llama_seed",
    "qwen_model_directory",
    "resolve_mmproj_path",
    "resolve_model_path",
    "runtime_status",
    "select_runtime_spec",
]
