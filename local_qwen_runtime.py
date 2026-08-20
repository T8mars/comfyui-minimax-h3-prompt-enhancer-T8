from __future__ import annotations

import atexit
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


NODE_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = NODE_ROOT / "runtime" / "local_qwen"
RUNTIME_CONFIG_PATH = RUNTIME_ROOT / "runtime_config.json"
MODEL_SUBDIRECTORY = Path("LLM") / "Qwen3.8"
DEFAULT_MODEL_FILENAME = "Qwen3.8-27B-Q4_K_M.gguf"
DEFAULT_MMPROJ_FILENAME = "mmproj-F16.gguf"
DEFAULT_MODEL_SIZE = 17_106_775_008
DEFAULT_MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
DEFAULT_MMPROJ_SIZE = 927_607_488
DEFAULT_MMPROJ_SHA256 = "cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e"
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


def _models_root() -> Path:
    try:
        import folder_paths

        return Path(folder_paths.models_dir).resolve()
    except (ImportError, AttributeError):
        return (NODE_ROOT.parents[1] / "models").resolve()


def qwen_model_directory() -> Path:
    return (_models_root() / MODEL_SUBDIRECTORY).resolve()


def _safe_model_filename(value: str, *, label: str) -> str:
    filename = str(value or "").strip()
    if not filename:
        raise LocalQwenRuntimeError(f"{label} is empty.")
    if filename != Path(filename).name or Path(filename).suffix.casefold() != ".gguf":
        raise LocalQwenRuntimeError(f"{label} must be a GGUF filename without a directory path.")
    return filename


def resolve_model_path(filename: str, *, label: str, required: bool = True) -> Path:
    safe_name = _safe_model_filename(filename, label=label)
    root = qwen_model_directory()
    path = (root / safe_name).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise LocalQwenRuntimeError(f"{label} must remain inside {root}.") from error
    if required and not path.is_file():
        raise LocalQwenRuntimeError(
            f"Missing {label}: {path}. Run install_local_qwen.py --model to download and verify it."
        )
    return path


def list_gguf_models() -> list[str]:
    root = qwen_model_directory()
    if not root.is_dir():
        return [DEFAULT_MODEL_FILENAME]
    names = sorted(
        (item.name for item in root.iterdir() if item.is_file() and item.suffix.casefold() == ".gguf"),
        key=str.casefold,
    )
    non_projectors = [name for name in names if not name.casefold().startswith("mmproj")]
    return non_projectors or [DEFAULT_MODEL_FILENAME]


def list_mmproj_models() -> list[str]:
    root = qwen_model_directory()
    if not root.is_dir():
        return [DEFAULT_MMPROJ_FILENAME]
    names = sorted(
        (
            item.name
            for item in root.iterdir()
            if item.is_file()
            and item.suffix.casefold() == ".gguf"
            and item.name.casefold().startswith("mmproj")
        ),
        key=str.casefold,
    )
    return names or [DEFAULT_MMPROJ_FILENAME]


@dataclass(frozen=True)
class RuntimeSpec:
    executable: Path
    library_dirs: tuple[Path, ...]
    backend: str
    n_gpu_layers: str = "auto"
    fit: bool = True
    fit_target_mib: int = 1536
    flash_attention: str = "auto"


def _runtime_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise LocalQwenRuntimeError(f"Invalid {label} in {RUNTIME_CONFIG_PATH}.")
    path = (RUNTIME_ROOT / value).resolve()
    try:
        path.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as error:
        raise LocalQwenRuntimeError(f"{label} must remain inside {RUNTIME_ROOT}.") from error
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
    raw_dirs = payload.get("library_dirs") or [str(executable.parent.relative_to(RUNTIME_ROOT))]
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
    )


def runtime_status() -> dict[str, Any]:
    model_path = resolve_model_path(DEFAULT_MODEL_FILENAME, label="local model", required=False)
    mmproj_path = resolve_model_path(
        DEFAULT_MMPROJ_FILENAME, label="vision projector", required=False
    )
    model_installed = model_path.is_file() and model_path.stat().st_size == DEFAULT_MODEL_SIZE
    mmproj_installed = (
        mmproj_path.is_file() and mmproj_path.stat().st_size == DEFAULT_MMPROJ_SIZE
    )
    result: dict[str, Any] = {
        "runtime_installed": False,
        "model_installed": model_installed,
        "mmproj_installed": mmproj_installed,
        "model_directory": str(qwen_model_directory()),
    }
    try:
        spec = load_runtime_spec()
    except LocalQwenRuntimeError as error:
        result["runtime_error"] = str(error)
    else:
        result.update(
            runtime_installed=True,
            backend=spec.backend,
        )
    result["text_ready"] = bool(result["runtime_installed"] and model_installed)
    result["vision_ready"] = bool(result["text_ready"] and mmproj_installed)
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


class LocalQwenManager:
    def __init__(self):
        self._run_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._inference_lock = threading.Lock()
        self._server: LlamaServer | None = None
        self._key: tuple[Path, Path | None, int, Path, str] | None = None
        self._idle_timer: threading.Timer | None = None
        self._idle_epoch = 0

    def begin_run(
        self,
        *,
        model: Path,
        mmproj: Path | None,
        context_size: int,
        comfy_memory_policy: str,
    ) -> LlamaServer:
        while not self._run_lock.acquire(timeout=0.25):
            _throw_if_interrupted()
        try:
            return self.acquire(
                model=model,
                mmproj=mmproj,
                context_size=context_size,
                comfy_memory_policy=comfy_memory_policy,
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
    ) -> LlamaServer:
        spec = load_runtime_spec()
        key = (model.resolve(), mmproj.resolve() if mmproj else None, int(context_size), spec.executable.resolve(), spec.backend)
        with self._lifecycle_lock:
            self._cancel_timer()
            if self._server is not None and self._key == key and self._server.is_running:
                return self._server
            self.release()
            _release_comfy_models_if_needed(comfy_memory_policy)
            server = LlamaServer(model=model, mmproj=mmproj, context_size=context_size, spec=spec)
            try:
                server.start()
            except BaseException:
                server.stop()
                raise
            self._server = server
            self._key = key
            return server

    def complete(self, server: LlamaServer, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        with self._inference_lock:
            _throw_if_interrupted()
            if server is not self._server or not server.is_running:
                raise LocalQwenRuntimeError("Local Qwen server changed before the request could run.")
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
    "DEFAULT_MMPROJ_FILENAME",
    "DEFAULT_MODEL_FILENAME",
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
    "list_gguf_models",
    "list_mmproj_models",
    "normalize_llama_seed",
    "qwen_model_directory",
    "resolve_model_path",
    "runtime_status",
]
