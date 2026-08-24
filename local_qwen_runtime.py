from __future__ import annotations

import atexit
import gc
import importlib.util
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

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


NODE_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = NODE_ROOT / "runtime" / "local_qwen"
RUNTIME_CONFIG_PATH = RUNTIME_ROOT / "runtime_config.json"
DEFAULT_MODEL_FILENAME = "Qwen3.8-27B-Q4_K_M.gguf"
UNCENSORED_MODEL_FILENAME = "qwen3.8-27b-uncensored-fp8-q4_k_m.gguf"
DEFAULT_MMPROJ_FILENAME = "mmproj-F16.gguf"
DEFAULT_MODEL_SIZE = 17_106_775_008
DEFAULT_MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
UNCENSORED_MODEL_SIZE = 16_810_714_976
UNCENSORED_MODEL_SHA256 = "66bb238d41de38b11dd406d932d8fb97433d529022cef60f2f422b9221cae743"
DEFAULT_MMPROJ_SIZE = 927_607_488
DEFAULT_MMPROJ_SHA256 = "cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e"
KNOWN_MODEL_FILES = {
    DEFAULT_MODEL_FILENAME: (DEFAULT_MODEL_SIZE, DEFAULT_MODEL_SHA256),
    UNCENSORED_MODEL_FILENAME: (UNCENSORED_MODEL_SIZE, UNCENSORED_MODEL_SHA256),
}
LOCAL_MODEL_ALIAS = "qwen3.8-27b"
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


def normalize_llama_seed(seed: int) -> int:
    return int(seed) % LLAMA_SEED_MODULUS


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


@dataclass(frozen=True)
class RuntimeSpec:
    executable: Path
    library_dirs: tuple[Path, ...]
    backend: str
    n_gpu_layers: str = "auto"
    fit: bool = True
    fit_target_mib: int = 1536
    flash_attention: str = "auto"
    source: str = "bundled"


@dataclass(frozen=True)
class PythonRuntimeSpec:
    backend: str = "llama-cpp-python"
    version: str = "unknown"
    source: str = "ComfyUI Python environment"


def _runtime_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise LocalQwenRuntimeError(f"Invalid {label} in {RUNTIME_CONFIG_PATH}.")
    raw = Path(value).expanduser()
    path = raw.resolve() if raw.is_absolute() else (RUNTIME_ROOT / raw).resolve()
    return path


def load_runtime_spec() -> RuntimeSpec:
    if not RUNTIME_CONFIG_PATH.is_file():
        raise LocalQwenRuntimeError(
            f"Local llama.cpp runtime is not installed. Run install_local_qwen.py --runtime from {NODE_ROOT}."
        )
    try:
        payload = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LocalQwenRuntimeError(
            f"Cannot read {RUNTIME_CONFIG_PATH}. Run install_local_qwen.py --runtime --force."
        ) from error
    if payload.get("schema_version") != 1:
        raise LocalQwenRuntimeError("Unsupported local Qwen runtime configuration schema.")
    executable = _runtime_path(payload.get("executable"), "runtime executable")
    if not executable.is_file():
        raise LocalQwenRuntimeError(f"llama-server is missing: {executable}")
    raw_dirs = payload.get("library_dirs") or [str(executable.parent)]
    if not isinstance(raw_dirs, list):
        raise LocalQwenRuntimeError("runtime library_dirs must be a list.")
    options = payload.get("runtime_options") or {}
    return RuntimeSpec(
        executable=executable,
        library_dirs=tuple(_runtime_path(value, "runtime library directory") for value in raw_dirs),
        backend=str(payload.get("backend") or "unknown"),
        n_gpu_layers=str(options.get("n_gpu_layers") or "auto"),
        fit=bool(options.get("fit", True)),
        fit_target_mib=max(256, int(options.get("fit_target_mib", 1536))),
        flash_attention=str(options.get("flash_attention") or "auto"),
        source=str(RUNTIME_CONFIG_PATH),
    )


def _path_runtime_spec() -> RuntimeSpec | None:
    executable = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if not executable:
        return None
    path = Path(executable).resolve()
    return RuntimeSpec(
        executable=path,
        library_dirs=(path.parent,),
        backend="llama.cpp PATH",
        source="PATH",
    )


def load_python_runtime_spec() -> PythonRuntimeSpec:
    if importlib.util.find_spec("llama_cpp") is None:
        raise LocalQwenRuntimeError("llama-cpp-python is not installed in the active ComfyUI Python environment.")
    try:
        import llama_cpp
    except (ImportError, OSError) as error:
        raise LocalQwenRuntimeError(
            "llama-cpp-python was found but could not load its native library. "
            f"{type(error).__name__}: {error}"
        ) from error
    return PythonRuntimeSpec(version=str(getattr(llama_cpp, "__version__", "unknown")))


def available_runtime_specs() -> tuple[list[RuntimeSpec | PythonRuntimeSpec], list[str]]:
    specs: list[RuntimeSpec | PythonRuntimeSpec] = []
    warnings: list[str] = []
    if RUNTIME_CONFIG_PATH.is_file():
        try:
            specs.append(load_runtime_spec())
        except LocalQwenRuntimeError as error:
            warnings.append(str(error))
    path_spec = _path_runtime_spec()
    if path_spec is not None and not any(
        isinstance(item, RuntimeSpec) and item.executable == path_spec.executable for item in specs
    ):
        specs.append(path_spec)
    try:
        specs.append(load_python_runtime_spec())
    except LocalQwenRuntimeError as error:
        if not specs:
            warnings.append(str(error))
    return specs, warnings


def select_runtime_spec() -> RuntimeSpec | PythonRuntimeSpec:
    specs, warnings = available_runtime_specs()
    if specs:
        # Keep the pinned standalone runtime first for fully compatible old
        # installs, then PATH, then llama-cpp-python as a no-private-runtime
        # fallback shared with other ComfyUI nodes.
        return specs[0]
    details = " ".join(warnings)
    raise LocalQwenRuntimeError(
        "No usable local llama.cpp runtime was found. Install llama-cpp-python in the active ComfyUI "
        "Python environment, place llama-server on PATH, or run install_local_qwen.py --runtime. "
        + details
    )


def runtime_status(*, refresh: bool = False) -> dict[str, Any]:
    model_status = {}
    for filename, (expected_size, _expected_sha256) in KNOWN_MODEL_FILES.items():
        path = resolve_model_path(filename, label="local model", required=False)
        model_status[filename] = bool(
            path.is_file() and path.stat().st_size == expected_size
        )
    model_installed = model_status[DEFAULT_MODEL_FILENAME]
    uncensored_model_installed = model_status[UNCENSORED_MODEL_FILENAME]
    any_model_installed = any(model_status.values())
    mmproj_path = resolve_model_path(
        DEFAULT_MMPROJ_FILENAME, label="vision projector", required=False
    )
    mmproj_installed = (
        mmproj_path.is_file() and mmproj_path.stat().st_size == DEFAULT_MMPROJ_SIZE
    )
    catalog = catalog_public_payload(refresh=refresh)
    verified_names = {
        filename for filename, installed in model_status.items() if installed
    }
    for item in catalog.get("models", []):
        if item.get("filename") in verified_names:
            item["verification_tier"] = "project_tested_pinned_size_match"
        elif item.get("metadata_readable"):
            item["verification_tier"] = "runtime_supported_unverified"
        else:
            item["verification_tier"] = "discovered_unverified"
    result: dict[str, Any] = {
        "runtime_installed": False,
        "model_installed": model_installed,
        "uncensored_model_installed": uncensored_model_installed,
        "available_verified_models": [
            filename for filename, installed in model_status.items() if installed
        ],
        "mmproj_installed": mmproj_installed,
        **catalog,
        "legacy_model_directory": str(qwen_model_directory()),
    }
    specs, warnings = available_runtime_specs()
    if specs:
        result.update(
            runtime_installed=True,
            backend=specs[0].backend,
            runtime_source=specs[0].source,
            runtime_backends=[
                {
                    "backend": item.backend,
                    "source": item.source,
                    "version": getattr(item, "version", ""),
                }
                for item in specs
            ],
        )
    if warnings:
        result["runtime_warnings"] = warnings
    discovered_models = int(catalog.get("model_count") or 0)
    discovered_projectors = int(catalog.get("projector_count") or 0)
    result["text_ready"] = bool(
        result["runtime_installed"] and (discovered_models or any_model_installed)
    )
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


def _runtime_environment(spec: RuntimeSpec) -> dict[str, str]:
    environment = dict(os.environ)
    library_path = os.pathsep.join(str(path) for path in spec.library_dirs)
    environment["PATH"] = library_path + os.pathsep + environment.get("PATH", "")
    if os.name != "nt":
        key = "DYLD_LIBRARY_PATH" if os.uname().sysname == "Darwin" else "LD_LIBRARY_PATH"
        environment[key] = library_path + os.pathsep + environment.get(key, "")
    return environment


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


class LlamaServer:
    def __init__(
        self,
        *,
        model: Path,
        mmproj: Path | None,
        context_size: int,
        spec: RuntimeSpec,
    ):
        self.model = model
        self.mmproj = mmproj
        self.context_size = int(context_size)
        self.spec = spec
        self.port = self._find_free_port()
        self.token = secrets.token_urlsafe(32)
        self.process: subprocess.Popen[bytes] | None = None
        self.log = tempfile.TemporaryFile(mode="w+b")
        self._stop_lock = threading.RLock()

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _log_tail(self) -> str:
        if self.log.closed:
            return ""
        self.log.flush()
        self.log.seek(0)
        return self.log.read().decode("utf-8", errors="replace")[-4000:]

    def start(self, timeout: float = 240.0) -> None:
        arguments = [
            str(self.spec.executable),
            "--model",
            str(self.model),
            "--alias",
            LOCAL_MODEL_ALIAS,
            "--api-key",
            self.token,
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--ctx-size",
            str(self.context_size),
            "--parallel",
            "1",
            "--n-gpu-layers",
            self.spec.n_gpu_layers,
            "--flash-attn",
            self.spec.flash_attention,
            "--cache-type-k",
            "q8_0",
            "--cache-type-v",
            "q8_0",
            "--jinja",
            "--no-webui",
        ]
        if self.mmproj is not None:
            arguments.extend(
                ["--mmproj", str(self.mmproj), "--image-min-tokens", "1024", "--image-max-tokens", "1024"]
            )
        if self.spec.fit:
            arguments.extend(["--fit", "on", "--fit-target", str(self.spec.fit_target_mib)])
        options: dict[str, Any] = {}
        if os.name == "nt":
            options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            arguments,
            cwd=self.spec.executable.parent,
            env=_runtime_environment(self.spec),
            stdin=subprocess.DEVNULL,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            **options,
        )
        deadline = time.monotonic() + timeout
        headers = {"Authorization": f"Bearer {self.token}"}
        while time.monotonic() < deadline:
            _throw_if_interrupted()
            if self.process.poll() is not None:
                raise LocalQwenRuntimeError(
                    "llama-server exited while loading the model. " + self._log_tail()
                )
            try:
                response = requests.get(self.base_url + "/health", headers=headers, timeout=2)
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(0.25)
        raise LocalQwenRuntimeError(
            f"llama-server did not become ready within {timeout:.0f} seconds. " + self._log_tail()
        )

    def stop(self) -> None:
        with self._stop_lock:
            process = self.process
            self.process = None
            try:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            except (OSError, ProcessLookupError, subprocess.SubprocessError):
                # Another cancellation/exit path may win the process race.
                pass
            finally:
                if not self.log.closed:
                    self.log.close()

    def _chat_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                self.base_url + "/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=(10, 1800),
            )
        except requests.RequestException as error:
            raise LocalQwenRuntimeError(f"Local llama-server request failed: {type(error).__name__}.") from error
        if response.status_code != 200:
            raise LocalQwenRuntimeError(
                f"Local llama-server HTTP {response.status_code}. Response text was hidden for privacy."
            )
        try:
            data = response.json()
        except ValueError as error:
            raise LocalQwenRuntimeError("Local llama-server returned invalid JSON.") from error
        if not isinstance(data, dict):
            raise LocalQwenRuntimeError("Local llama-server returned an invalid response object.")
        return data

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
        if not self.is_running:
            raise LocalQwenRuntimeError("Local llama-server is not running.")
        payload: dict[str, Any] = {
            "model": LOCAL_MODEL_ALIAS,
            "messages": messages,
            "seed": normalize_llama_seed(seed),
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "stream": False,
            "chat_template_kwargs": {
                "enable_thinking": bool(think_mode),
                "preserve_thinking": False,
            },
        }
        if think_mode:
            payload.update(
                temperature=1.0,
                top_p=0.95,
                top_k=20,
                min_p=0.0,
                presence_penalty=0.0,
                repeat_penalty=1.0,
            )
            payload["reasoning_effort"] = reasoning_effort
        else:
            payload.update(
                top_p=0.8,
                top_k=20,
                min_p=0.0,
                presence_penalty=1.5,
                repeat_penalty=1.0,
            )

        completed = threading.Event()
        result: dict[str, Any] = {}
        failure: list[BaseException] = []

        def worker() -> None:
            try:
                result.update(self._chat_sync(payload))
            except BaseException as error:  # propagate on the ComfyUI execution thread
                failure.append(error)
            finally:
                completed.set()

        thread = threading.Thread(target=worker, name="t8-local-qwen-chat", daemon=True)
        thread.start()
        try:
            while not completed.wait(0.25):
                _throw_if_interrupted()
        except BaseException:
            self.stop()
            completed.wait(5)
            raise
        if failure:
            raise failure[0]
        try:
            content = result["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise LocalQwenRuntimeError(
                "Local llama-server response is missing choices[0].message.content."
            ) from error
        if isinstance(content, list):
            content = "".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") in (None, "text")
            )
        if not isinstance(content, str) or not content.strip():
            raise LocalQwenRuntimeError(
                "Qwen returned no final answer. Disable thinking or increase the local output token limit."
            )
        return content.strip(), result.get("usage") or {}


class LlamaPythonRuntime:
    """In-process fallback for ComfyUI installs that already provide llama-cpp-python."""

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
            "Update it or use the bundled llama-server runtime."
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
            self.llm = Llama(
                model_path=str(self.model),
                chat_handler=handler,
                n_gpu_layers=-1,
                n_ctx=self.context_size,
                verbose=False,
            )
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
        if isinstance(content, list):
            content = "".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") in (None, "text")
            )
        if not isinstance(content, str) or not content.strip():
            raise LocalQwenRuntimeError(
                "The local GGUF returned no final answer. Disable thinking or increase max output tokens."
            )
        return content.strip(), result.get("usage") or {}


class LocalQwenManager:
    def __init__(self):
        self._run_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._inference_lock = threading.Lock()
        self._server: LlamaServer | LlamaPythonRuntime | None = None
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
    ) -> LlamaServer | LlamaPythonRuntime:
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
    ) -> LlamaServer | LlamaPythonRuntime:
        spec = select_runtime_spec()
        runtime_identity: tuple[Any, ...]
        if isinstance(spec, RuntimeSpec):
            runtime_identity = ("server", spec.executable.resolve(), spec.backend)
        else:
            runtime_identity = ("python", spec.version, spec.backend)
        key = (
            model.resolve(),
            mmproj.resolve() if mmproj else None,
            int(context_size),
            bool(think_mode),
            *runtime_identity,
        )
        with self._lifecycle_lock:
            self._cancel_timer()
            if self._server is not None and self._key == key and self._server.is_running:
                return self._server
            self.release()
            _release_comfy_models_if_needed(comfy_memory_policy)
            if isinstance(spec, RuntimeSpec):
                server: LlamaServer | LlamaPythonRuntime = LlamaServer(
                    model=model, mmproj=mmproj, context_size=context_size, spec=spec
                )
            else:
                server = LlamaPythonRuntime(
                    model=model,
                    mmproj=mmproj,
                    context_size=context_size,
                    spec=spec,
                    think_mode=think_mode,
                )
            try:
                server.start()
            except BaseException:
                server.stop()
                raise
            self._server = server
            self._key = key
            return server

    def complete(
        self, server: LlamaServer | LlamaPythonRuntime, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        with self._inference_lock:
            _throw_if_interrupted()
            if server is not self._server or not server.is_running:
                raise LocalQwenRuntimeError("Local GGUF runtime changed before the request could run.")
            return server.chat(**kwargs)

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
                            server = self._server
                            self._server = None
                            self._key = None
                            if server is not None:
                                server.stop()
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
            server = self._server
            self._server = None
            self._key = None
            if server is not None:
                server.stop()


LOCAL_QWEN_MANAGER = LocalQwenManager()
atexit.register(LOCAL_QWEN_MANAGER.release)


__all__ = [
    "AUTO_MMPROJ",
    "DEFAULT_MMPROJ_FILENAME",
    "DEFAULT_MODEL_FILENAME",
    "KNOWN_MODEL_FILES",
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
