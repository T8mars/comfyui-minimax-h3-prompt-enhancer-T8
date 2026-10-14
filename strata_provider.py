"""Opt-in protocol-1 client for an already running Strata service.

No import, scope entry or metadata request loads/stops a model. Only chat POSTs
perform inference; service-side autoload follows the user's Strata settings.
The connection cancellation/framing design follows Comfyui-Strata-T8 core.py
at 2e53bf09ffc3d9c436ab3716de3b07b47996a58a (MIT). No lifecycle code is used.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, asdict
import functools
import http.client
import inspect
import ipaddress
import json
import math
import re
import socket
import sys
import threading
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

STRATA_API_MODE = "Strata 本地服务（桥接）"
PROVIDER_STRATA = "Strata"
STRATA_BASE_URL = "http://127.0.0.1:8080"
STRATA_CHAT_URL = "strata://bridge"
MAX_REQUEST_BYTES = 64 * 1024**2
MAX_RESPONSE_BYTES = 16 * 1024**2
_RUN: ContextVar[Any] = ContextVar("t8_strata_run", default=None)
_LOCKS: dict[tuple[str, int], threading.RLock] = {}
_LOCK_GUARD = threading.Lock()


class StrataProviderError(RuntimeError):
    def __init__(self, message: str, category: str = "strata_error"):
        self.category = category
        super().__init__(message)


def is_strata_mode(value: Any) -> bool:
    return str(value or "").strip() in {STRATA_API_MODE, PROVIDER_STRATA}


def current_strata_run():
    return _RUN.get()


def interrupted() -> None:
    module = sys.modules.get("comfy.model_management")
    check = getattr(module, "throw_exception_if_processing_interrupted", None)
    if callable(check):
        check()
    run = current_strata_run()
    if run is not None:
        run.remaining()


def strict_json(text):
    def pairs(items):
        out = {}
        for key, item in items:
            if key in out:
                raise ValueError("duplicate member")
            out[key] = item
        return out
    def finite_number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite")
        return result
    def invalid_constant(_value):
        raise ValueError("nonfinite")
    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_float=finite_number,
                            parse_constant=invalid_constant)
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise StrataProviderError("Strata 返回无效或歧义 JSON / Invalid service JSON.", "invalid_json") from None


def request_bytes(body):
    if body is None:
        return None
    pending, count = [(body, 0)], 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > 64 or count > 200000:
            raise StrataProviderError("Strata 请求结构过大 / Request JSON exceeds its structural budget.", "request_budget")
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise StrataProviderError("Strata JSON 字段名必须是文字 / JSON keys must be strings.")
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, (list, tuple)):
            pending.extend((item, depth + 1) for item in value)
    try:
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        raise StrataProviderError("Strata 请求包含无效 JSON / Invalid request JSON.") from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise StrataProviderError("桥接请求超过 64 MiB；请降低图片分辨率或采样帧数 / Bridge request exceeds 64 MiB.", "request_budget")
    return encoded


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise StrataProviderError(f"Strata {name} must be an integer in {low}..{high}.", "configuration")
    return value


def _number(value, name, low, high):
    # Check bounds before converting unusually large JSON integers to float.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or not math.isfinite(value):
        raise StrataProviderError(f"Strata {name} must be a finite number in {low}..{high}.", "configuration")
    return float(value)


@dataclass(frozen=True)
class StrataSettings:
    url: str = STRATA_BASE_URL
    model: str = "AUTO"
    credential_alias: str = ""
    reasoning_effort: str = "none"
    max_tokens: int = 0
    reasoning_budget_tokens: int = 0
    video_mode: str = "frames"
    video_sample_fps: float = 1.0
    video_max_frames: int = 8
    timeout_s: float = 1800.0
    allow_private_network: bool = False

    @classmethod
    def from_values(cls, values: Any = None):
        if isinstance(values, cls):
            values = asdict(values)
        values = {} if values is None else values
        if not isinstance(values, Mapping):
            raise StrataProviderError("Strata settings must be an object.", "configuration")
        defaults = asdict(cls())
        fields = {key: values.get("strata_" + key, values.get(key, default)) for key, default in defaults.items()}
        for key in ("url", "model", "credential_alias", "reasoning_effort", "video_mode"):
            if not isinstance(fields[key], str) or len(fields[key]) > (1024 if key == "url" else 256):
                raise StrataProviderError(f"Invalid Strata {key}.", "configuration")
            fields[key] = fields[key].strip()
        fields["url"] = fields["url"] or STRATA_BASE_URL
        fields["model"] = fields["model"] or "AUTO"
        if fields["credential_alias"] and not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", fields["credential_alias"]):
            raise StrataProviderError("Invalid Strata credential alias.", "configuration")
        if fields["reasoning_effort"] not in {"none", "low", "medium", "high"} or fields["video_mode"] not in {"frames", "native"}:
            raise StrataProviderError("Invalid Strata thinking/video mode.", "configuration")
        _integer(fields["max_tokens"], "max_tokens", 0, 2147483647)
        _integer(fields["reasoning_budget_tokens"], "reasoning_budget_tokens", 0, 2147483647)
        _integer(fields["video_max_frames"], "video_max_frames", 2, 64)
        fields["video_sample_fps"] = _number(fields["video_sample_fps"], "video_sample_fps", .25, 30)
        fields["timeout_s"] = _number(fields["timeout_s"], "timeout_s", 5, 86400)
        if type(fields["allow_private_network"]) is not bool:
            raise StrataProviderError("Invalid Strata private-network setting.", "configuration")
        result = cls(**fields)
        validate_endpoint(result)
        return result

    def public_values(self):
        return asdict(self)


def validate_endpoint(settings: StrataSettings):
    try:
        parsed = urlsplit(settings.url)
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise StrataProviderError("Invalid Strata service address.", "configuration") from None
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or parsed.path.rstrip("/") not in {"", "/v1"}:
        raise StrataProviderError("Strata 地址仅支持 HTTP(S) 服务根地址或 /v1，不允许密码、查询参数或重定向 / Invalid service URL.", "configuration")
    if not 1 <= port <= 65535:
        raise StrataProviderError("Invalid Strata port.", "configuration")
    if host in {"localhost", "127.0.0.1", "::1"}:
        return host, port
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Named container targets are resolved and pinned by the client, never
        # passed through proxy environment variables.
        address = None
    if address is not None and address.is_loopback:
        return host, port
    if not settings.allow_private_network:
        raise StrataProviderError("默认仅连接本机；私网/容器地址请显式允许并配置 Strata 凭据 / Loopback only by default.", "configuration")
    return host, port


def _private_address(address):
    ip = ipaddress.ip_address(address)
    return ip.is_loopback or (ip.version == 4 and any(ip in ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))) or (ip.version == 6 and ip in ipaddress.ip_network("fc00::/7"))


def resolve_key(settings):
    if settings.credential_alias:
        try:
            from .credential_store import get_credential
        except ImportError:
            from credential_store import get_credential
        try:
            key = get_credential(settings.credential_alias)
        except Exception:
            raise StrataProviderError("Strata 凭据别名不存在或无法读取 / Credential alias unavailable.", "authentication") from None
    else:
        try:
            from .environment_defaults import optional_environment_value
        except ImportError:
            try:
                from environment_defaults import optional_environment_value
            except ImportError:
                optional_environment_value = lambda _name: ""
        key = optional_environment_value("STRATA_API_KEY")
    key = str(key or "").strip()
    try:
        key.encode("latin-1")
    except UnicodeError:
        raise StrataProviderError("Strata key contains invalid header characters.", "authentication") from None
    if len(key) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in key):
        raise StrataProviderError("Strata key contains invalid header characters.", "authentication")
    return key


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, pinned, timeout):
        super().__init__(host, port, timeout=timeout)
        self.pinned = pinned

    def connect(self):
        sock = socket.create_connection((self.pinned, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class StrataClient:
    """Direct bounded HTTP. There are no proxies, redirects or POST retries."""
    STATUS_CATEGORIES = {}
    GET_PATHS = frozenset({"/health", "/v1/status", "/v1/models", "/v1/chat/completions"})
    POST_PATHS = frozenset({"/v1/chat/completions"})
    RESPONSE_LIMIT = MAX_RESPONSE_BYTES
    def __init__(self, settings, key=None):
        self.settings = StrataSettings.from_values(settings)
        self.host, self.port = validate_endpoint(self.settings)
        self.key = resolve_key(self.settings) if key is None else key
        try:
            # Numeric loopback (the default) never requires a DNS lookup.
            numeric = ipaddress.ip_address(self.host)
        except ValueError:
            numeric = None
        try:
            if numeric is not None:
                addresses = [str(numeric)]
            elif self.host == "localhost":
                addresses = ["127.0.0.1"]
            else:
                # Resolver calls cannot be killed safely. Bound the wait and
                # abandon only this daemon resolver; it never sends HTTP later.
                resolved, ready = {}, threading.Event()
                def resolve():
                    try:
                        resolved["addresses"] = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)))
                    except OSError:
                        resolved["failed"] = True
                    finally:
                        ready.set()
                threading.Thread(target=resolve, name="t8-strata-dns", daemon=True).start()
                deadline = time.monotonic() + 5
                while not ready.wait(.1):
                    interrupted()
                    if time.monotonic() >= deadline:
                        raise StrataProviderError("Strata hostname lookup timed out.", "timeout")
                if resolved.get("failed"):
                    raise OSError
                addresses = resolved["addresses"]
        except OSError:
            raise StrataProviderError("Strata service hostname cannot be resolved.", "connection") from None
        if not addresses or any(not _private_address(item) for item in addresses):
            raise StrataProviderError("Strata bridge only permits loopback or explicitly allowed private targets.", "configuration")
        if any(not ipaddress.ip_address(item).is_loopback for item in addresses) and not self.key:
            raise StrataProviderError("私网 Strata 必须配置独立凭据 / Private-network service requires authentication.", "authentication")
        self.pinned = addresses[0]

    def request(self, path, body=None, *, timeout=5, check=interrupted, on_submit=None):
        if path not in (self.POST_PATHS if body is not None else self.GET_PATHS):
            raise StrataProviderError("Strata bridge does not expose lifecycle or arbitrary endpoints.")
        timeout = _number(timeout, "request timeout", .001, 86400)
        encoded = request_bytes(body)
        check and check()
        if urlsplit(self.settings.url).scheme == "https":
            conn = _PinnedHTTPS(self.host, self.port, self.pinned, min(5, timeout))
        else:
            conn = http.client.HTTPConnection(self.pinned, self.port, timeout=min(5, timeout))
        conn.auto_open = 0
        result, finished, cancelled = {}, threading.Event(), threading.Event()
        deadline = time.monotonic() + timeout

        def worker():
            response = None
            try:
                if cancelled.is_set():
                    return
                conn.connect()
                result["socket"] = conn.sock
                if cancelled.is_set():
                    return
                conn.sock.settimeout(max(.001, deadline - time.monotonic()))
                headers = {"Content-Type": "application/json", "Cache-Control": "no-cache", "Host": (f"[{self.host}]" if ":" in self.host else self.host) + f":{self.port}"}
                if self.key:
                    headers["Authorization"] = "Bearer " + self.key
                if body is not None and on_submit:
                    on_submit()
                if cancelled.is_set():
                    return
                conn.request("POST" if body is not None else "GET", path, encoded, headers)
                response = conn.getresponse()
                if 300 <= response.status < 400:
                    raise StrataProviderError("Strata 不跟随重定向 / Redirect refused.", "redirect")
                lengths = [v.strip() for k, v in response.getheaders() if k.lower() == "content-length"]
                transfers = [v.strip().lower() for k, v in response.getheaders() if k.lower() == "transfer-encoding"]
                if len(lengths) > 1 or len(transfers) > 1 or (lengths and transfers) or (transfers and transfers != ["chunked"]):
                    raise StrataProviderError("Ambiguous Strata response framing.", "invalid_response")
                if lengths and (not re.fullmatch(r"[0-9]{1,10}", lengths[0]) or int(lengths[0]) > self.RESPONSE_LIMIT):
                    raise StrataProviderError("Strata response exceeds its size limit.", "response_budget")
                expected = getattr(response, "length", None)
                raw = response.read(self.RESPONSE_LIMIT + 1)
                if len(raw) > self.RESPONSE_LIMIT or (type(expected) is int and len(raw) != expected):
                    raise StrataProviderError("Strata response is oversized or incomplete.", "invalid_response")
                if response.status != 200:
                    categories = {401: "authentication", 403: "authentication", 404: "not_found", 413: "request_budget", 422: "structured_output", 502: "service_error", 503: "service_busy"}
                    category = self.STATUS_CATEGORIES.get(response.status, categories.get(response.status, "service_error"))
                    try:
                        error_code = strict_json(raw).get("error", {}).get("code")
                        if error_code == "structured_output_failed":
                            category = "structured_output"
                    except (StrataProviderError, AttributeError):
                        pass
                    if response.status == 400:
                        try:
                            error_body = strict_json(raw)
                            error = error_body.get("error", {}) if isinstance(error_body, dict) else {}
                            message = error.get("message", "") if isinstance(error, dict) else ""
                            message = message if isinstance(message, str) else ""
                            category = "context_budget" if "context" in message.lower() else "invalid_request"
                        except StrataProviderError:
                            category = "invalid_request"
                    raise StrataProviderError(f"Strata HTTP {response.status} ({category})；上游正文已隐藏 / Response body hidden.", category)
                data = strict_json(raw)
                if not isinstance(data, dict):
                    raise StrataProviderError("Strata response must be an object.", "invalid_response")
                result["data"] = data
            except BaseException as error:
                result["error"] = error
            finally:
                try:
                    if response is not None:
                        response.close()
                finally:
                    try:
                        conn.close()
                    finally:
                        finished.set()

        thread = threading.Thread(target=worker, name="t8-strata-http", daemon=True)
        thread.start()
        try:
            while not finished.wait(.1):
                check and check()
                if time.monotonic() >= deadline:
                    raise StrataProviderError("Strata 总超时；已提交的结果未确认，不会盲目重发 / Deadline exceeded; result unconfirmed.", "timeout")
            check and check()
            if time.monotonic() >= deadline:
                raise StrataProviderError("Strata request exceeded its deadline.", "timeout")
            if "error" in result:
                error = result["error"]
                if isinstance(error, StrataProviderError):
                    raise error from None
                raise StrataProviderError(f"Strata 连接失败 / Connection failed: {type(error).__name__}.", "connection") from None
            return result["data"]
        except BaseException:
            cancelled.set()
            transport = result.get("socket") or conn.sock
            if transport is not None:
                try:
                    transport.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    transport.close()
                except OSError:
                    pass
            thread.join(.2)
            raise


def validate_status(data, *, require_ready=True):
    try:
        if data["service"] != "strata" or type(data["protocol_version"]) is not int or data["protocol_version"] != 1:
            raise ValueError
        model = data["model"]
        if not isinstance(model, str) or not model or len(model) > 256 or any(ord(c) < 32 for c in model):
            raise ValueError
        if type(data["loaded"]) is not bool or type(data["auto_load"]) is not bool:
            raise ValueError
        _integer(data["context"]["native"], "context", 1, 2147483647)
        _integer(data["concurrency"]["serving"], "concurrency", 1, 256)
        if type(data["vision"]["enabled"]) is not bool or type(data["vision"]["available"]) is not bool:
            raise ValueError
        _integer(data["started"], "service start identity", 1, 2**63 - 1)
        if data.get("instance_id") is not None and (not isinstance(data["instance_id"],str) or len(data["instance_id"])>256):
            raise ValueError
        capabilities = data.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValueError
        video = capabilities.get("video", {})
        if not isinstance(video, dict) or not isinstance(video.get("limits", {}), dict):
            raise ValueError
        if "modes" in video and (not isinstance(video["modes"], list) or any(not isinstance(mode, str) for mode in video["modes"])):
            raise ValueError
        if "contract_version" in video and type(video["contract_version"]) is not int:
            raise ValueError
        if "native_verified" in video and type(video["native_verified"]) is not bool:
            raise ValueError
        if "max_frames" in video.get("limits", {}):
            _integer(video["limits"]["max_frames"], "service frame limit", 1, 100000)
        if require_ready and not data["loaded"] and not data["auto_load"]:
            raise StrataProviderError("请先在 Strata 加载模型 / Load the model in Strata first.", "not_ready")
        return data
    except (KeyError, TypeError, ValueError):
        raise StrataProviderError("该地址不是有效的 Strata 协议 1 服务 / Invalid Strata protocol-1 status.", "protocol") from None


class StrataRun:
    def __init__(self, settings=None, *, seed=0):
        self.started = time.monotonic()
        self.settings = StrataSettings.from_values(settings)
        self.deadline = self.started + self.settings.timeout_s
        self.seed = _integer(seed, "seed", 0, 2**64 - 1)
        self._client = None
        self.snapshot = None
        self.pending_recovery = {}
        self.started_recovery = set()
        self.committing_recovery = False
        self.media_cache = {}
        self.video_cache = {}
        self.media_reports = []
        self.requests = 0
        self._lock = None
        self._lock_owned = False

    def remaining(self, cap=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise StrataProviderError("Strata 整个任务已超时 / Total run deadline exceeded.", "timeout")
        return min(remaining, cap) if cap is not None else remaining

    @property
    def client(self):
        if self._client is None:
            interrupted()
            client = StrataClient(self.settings)
            with _LOCK_GUARD:
                self._lock = _LOCKS.setdefault((client.pinned, client.port), threading.RLock())
            while not self._lock.acquire(timeout=min(.1, self.remaining())):
                interrupted()
            self._lock_owned = True
            self._client = client
        return self._client

    def identity(self):
        interrupted()
        data = validate_status(self.client.request("/v1/status", timeout=self.remaining(5)))
        identity = {key: data.get(key) for key in ("model", "instance_id", "started")}
        identity["context"] = data["context"]["native"]
        if self.snapshot is None:
            if self.settings.model != "AUTO" and self.settings.model != data["model"]:
                catalog = self.client.request("/v1/models", timeout=self.remaining(5)).get("data", [])
                if not any(isinstance(item, dict) and item.get("id") == self.settings.model and item.get("alias_of") == data["model"] for item in catalog):
                    raise StrataProviderError("指定模型不是 Strata 当前模型或已验证别名；请在服务中切换模型 / Model mismatch.", "model_mismatch")
            self.snapshot = identity
        elif identity != self.snapshot:
            raise StrataProviderError("Strata 服务实例、模型或上下文已改变；本次停止，不自动续跑 / Service identity changed.", "identity_changed")
        return data

    def defer_recovery(self, component, slot, provider, metadata):
        self.pending_recovery[(component, slot)] = (provider, metadata)

    def _on_submit(self):
        self.commit_recovery()
        self.requests += 1

    def commit_recovery(self):
        try:
            from .completion_recovery import begin_recovery_record
        except ImportError:
            from completion_recovery import begin_recovery_record
        # Worker threads do not inherit this ContextVar: the original function
        # commits here, only after local validation, GET and socket connection.
        self.committing_recovery = True
        try:
            for (component, slot), (provider, metadata) in self.pending_recovery.items():
                if (component, slot) not in self.started_recovery:
                    begin_recovery_record(component, slot, provider, metadata=metadata)
                    self.started_recovery.add((component, slot))
        finally:
            self.committing_recovery = False

    def complete(self, messages, *, temperature, seed=None, response_format=None):
        interrupted()
        if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) or not isinstance(m.get("role"), str) or m["role"] not in {"system", "user", "assistant"}
            or not isinstance(m.get("content"), (str, list)) for m in messages):
            raise StrataProviderError("Invalid Strata chat messages.", "media")
        data = self.identity()
        parts = [part for message in messages if isinstance(message.get("content"), list) for part in message["content"]]
        frame_count = 0
        for part in parts:
            if not isinstance(part, dict) or not isinstance(part.get("type"), str) or part["type"] not in {"text", "image_url", "strata_video"}:
                raise StrataProviderError("Strata 仅支持文字/图片/显式视频，不支持音频或 video_url / Unsupported media part.", "media")
            if part["type"] == "text" and not isinstance(part.get("text"), str):
                raise StrataProviderError("Strata text parts require a text string.", "media")
            if part["type"] == "image_url":
                field = part.get("image_url")
                source = field.get("url", "") if isinstance(field, dict) else ""
                if not isinstance(source, str) or not source.startswith("data:image/") or ";base64," not in source:
                    raise StrataProviderError("Strata bridge requires inline images.", "media")
            if part["type"] == "strata_video":
                capability = (data.get("capabilities") or {}).get("video", {})
                if capability.get("contract_version") != 1 or self.settings.video_mode not in capability.get("modes", []):
                    raise StrataProviderError("Strata 服务未声明所选视频协议/模式 / Video capability unavailable.", "capability")
                if self.settings.video_mode == "native" and capability.get("native_verified") is not True:
                    raise StrataProviderError("native 尚未核验；请先在 Strata 加载，或手动选择 frames / Native video not verified.", "capability")
                frames, metadata = part.get("frames"), part.get("metadata")
                if type(part.get("contract_version")) is not int or part["contract_version"] != 1 or part.get("mode") != self.settings.video_mode \
                    or not isinstance(frames, list) or not 1 <= len(frames) <= 64 or not isinstance(metadata, dict):
                    raise StrataProviderError("Invalid explicit Strata video contract.", "media")
                duration = _number(metadata.get("duration_s"), "video duration", .000001, 3600)
                _number(metadata.get("time_origin_s"), "video origin", -1e12, 1e12)
                previous = -1.
                for frame in frames:
                    if not isinstance(frame, dict) or not isinstance(frame.get("source"), str) or not frame["source"].startswith("data:image/") or ";base64," not in frame["source"]:
                        raise StrataProviderError("Video frames must be inline images.", "media")
                    stamp = _number(frame.get("timestamp_s"), "video timestamp", 0., duration)
                    _number(frame.get("source_timestamp_s"), "video source timestamp", -1e12, 1e12)
                    if stamp <= previous or stamp >= duration:
                        raise StrataProviderError("Video timestamps must increase inside the selected window.", "media")
                    previous = stamp
                frame_count += len(frames)
        if any(part.get("type") != "text" for part in parts) and not (data["vision"]["enabled"] and data["vision"]["available"]):
            raise StrataProviderError("Strata 未启用视觉，请在服务中开启 / Vision not enabled.", "capability")
        max_frames = min(64, _integer(((data.get("capabilities") or {}).get("video", {}).get("limits") or {}).get("max_frames", 64), "service frame limit", 1, 100000))
        if frame_count > max_frames:
            raise StrataProviderError(f"视频采样合计 {frame_count} 帧，服务本次上限 {max_frames}；请降低帧预算 / Too many video frames.", "media_budget")
        payload = {"model": data["model"], "messages": messages, "stream": False,
                   "temperature": _number(temperature, "temperature", 0, 2),
                   "max_tokens": self.settings.max_tokens,
                   "reasoning_effort": self.settings.reasoning_effort,
                   "reasoning_budget_tokens": self.settings.reasoning_budget_tokens}
        selected_seed = self.seed if seed is None else _integer(seed, "seed", 0, 2**64 - 1)
        if selected_seed > 0:
            payload["seed"] = selected_seed
        if response_format is not None:
            payload["response_format"] = response_format
        response = self.client.request("/v1/chat/completions", payload, timeout=self.remaining(), on_submit=self._on_submit)
        self.identity()
        if response.get("model") != self.snapshot["model"]:
            raise StrataProviderError("Strata 返回了不同模型；结果未提交 / Response model mismatch.", "identity_changed")
        try:
            choices = response["choices"]
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError
            choice = choices[0]
            if choice.get("finish_reason") != "stop":
                raise StrataProviderError("Strata 输出截断或未完成；请检查上下文、Token及思考设置 / Incomplete final answer.", "truncated")
            text = choice["message"]["content"]
            if not isinstance(text, str):
                raise ValueError
            try:
                from .provider_transport import strip_inline_reasoning
            except ImportError:
                from provider_transport import strip_inline_reasoning
            text = strip_inline_reasoning(text)
            if not text.strip():
                raise StrataProviderError("Strata 只返回思考或空正文 / Empty final answer.", "empty_content")
            return text
        except (KeyError, TypeError, IndexError, ValueError):
            raise StrataProviderError("Strata 缺少完整 choices/message/content / Invalid completion.", "invalid_response") from None

    def close(self):
        if self._lock_owned:
            self._lock.release()
            self._lock_owned = False
        self._client = None
        self._lock = None
        self.media_cache.clear()
        self.video_cache.clear()

    def cache_identity(self):
        self.identity()
        import hashlib
        return {"service": self.snapshot, "settings": self.settings.public_values(), "seed": self.seed,
                "credential_hash": hashlib.sha256(self.client.key.encode("utf-8")).hexdigest()}

    def summary(self):
        model = self.snapshot.get("model", "") if self.snapshot else "not-used"
        if not re.fullmatch(r"[A-Za-z0-9._/+\-]{1,128}", model) or re.search(r"sk-[A-Za-z0-9_-]{16,}", model):
            model = "[redacted-model]"
        return {"provider": "Strata", "model": model, "context": self.snapshot.get("context") if self.snapshot else None,
                "max_tokens": self.settings.max_tokens, "reasoning_effort": self.settings.reasoning_effort,
                "request_count": self.requests, "audio_analyzed": False, "lifecycle_owned": False,
                "videos": list(self.media_reports)}


def strata_execution(function):
    """An opt-in execution scope; existing mode signatures and paths are intact."""
    signature = inspect.signature(function)
    @functools.wraps(function)
    def execute(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        values = dict(bound.arguments)
        values.update(values.get("kwargs", {}))
        config = values.get("provider_config")
        mode = config.get("provider") if isinstance(config, Mapping) else values.get("api_mode")
        if values.get("recovery_action") == "restore_last" or not is_strata_mode(mode):
            return function(*args, **kwargs)
        if current_strata_run() is not None:
            return function(*args, **kwargs)
        settings = config.get("strata_settings") if isinstance(config, Mapping) else (values.get("provider_request_options") or {}).get("strata_settings")
        run = StrataRun(settings, seed=values.get("seed", 0))
        token = _RUN.set(run)
        try:
            result = function(*args, **kwargs)
            if hasattr(result, "result") and hasattr(result, "ui"):
                from comfy_api.latest import io
                result = io.NodeOutput(*result.result, ui={**(result.ui or {}), "strata_bridge": [run.summary()]})
            return result
        finally:
            run.close()
            _RUN.reset(token)
    return execute


def require_strata_run():
    run = current_strata_run()
    if run is None:
        raise StrataProviderError("Strata execution scope is missing.", "configuration")
    return run
