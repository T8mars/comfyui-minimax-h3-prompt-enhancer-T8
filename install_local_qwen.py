from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


NODE_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = NODE_ROOT / "runtime" / "local_qwen"
BOOTSTRAP_ROOT = RUNTIME_ROOT / "bootstrap"
RUNTIME_CONFIG_PATH = RUNTIME_ROOT / "runtime_config.json"
UPSTREAM_INSTALLER_COMMIT = "f8ea17991ea39111ef2b2ebdf6ccb631e21e0300"
UPSTREAM_INSTALLER_SHA256 = "c534879465c8a456f48fb11e8289e49a571f089a1f1fba3ca5a01c8397ad74fd"
UPSTREAM_INSTALLER_URL = (
    "https://raw.githubusercontent.com/chflame163/ComfyUI_Qwen_H3_Prompt/"
    f"{UPSTREAM_INSTALLER_COMMIT}/install_runtime.py"
)
MODEL_REVISION = "f1bfb127c64f7072bdd2cad55f258b9c8b2910fe"
MODEL_REPOSITORY = "unsloth/Qwen3.8-27B-GGUF"
UNCENSORED_MODEL_REVISION = "5bdf224e6f9b1e18c7598fea63e238e014ee8e3e"
UNCENSORED_MODEL_REPOSITORY = (
    "theresa00l/Qwen3.8-27B-Uncensored-FP8-Q4_K_M-GGUF"
)
MODEL_VARIANT_OFFICIAL = "official"
MODEL_VARIANT_UNCENSORED = "uncensored"
MODEL_VARIANT_ALL = "all"
MODEL_VARIANTS = (
    MODEL_VARIANT_OFFICIAL,
    MODEL_VARIANT_UNCENSORED,
    MODEL_VARIANT_ALL,
)
USER_AGENT = "comfyui-minimax-h3-prompt-enhancer-T8-local-qwen-installer/1.0"


@dataclass(frozen=True)
class Download:
    filename: str
    size: int
    sha256: str
    repository: str = MODEL_REPOSITORY
    revision: str = MODEL_REVISION

    @property
    def url(self) -> str:
        return (
            f"https://huggingface.co/{self.repository}/resolve/{self.revision}/"
            f"{self.filename}?download=true"
        )


OFFICIAL_MODEL_FILE = Download(
    "Qwen3.8-27B-Q4_K_M.gguf",
    17_106_775_008,
    "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169",
)
UNCENSORED_MODEL_FILE = Download(
    "qwen3.8-27b-uncensored-fp8-q4_k_m.gguf",
    16_810_714_976,
    "66bb238d41de38b11dd406d932d8fb97433d529022cef60f2f422b9221cae743",
    repository=UNCENSORED_MODEL_REPOSITORY,
    revision=UNCENSORED_MODEL_REVISION,
)
VISION_PROJECTOR_FILE = Download(
    "mmproj-F16.gguf",
    927_607_488,
    "cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e",
)
MODEL_FILES = (OFFICIAL_MODEL_FILE, VISION_PROJECTOR_FILE)


def model_files_for_variant(variant: str) -> tuple[Download, ...]:
    normalized = str(variant or MODEL_VARIANT_OFFICIAL).strip().casefold()
    if normalized == MODEL_VARIANT_OFFICIAL:
        return OFFICIAL_MODEL_FILE, VISION_PROJECTOR_FILE
    if normalized == MODEL_VARIANT_UNCENSORED:
        return UNCENSORED_MODEL_FILE, VISION_PROJECTOR_FILE
    if normalized == MODEL_VARIANT_ALL:
        return OFFICIAL_MODEL_FILE, UNCENSORED_MODEL_FILE, VISION_PROJECTOR_FILE
    raise ValueError(
        f"Unsupported model variant {variant!r}; choose one of {', '.join(MODEL_VARIANTS)}."
    )


def _models_root() -> Path:
    try:
        import folder_paths

        return Path(folder_paths.models_dir).resolve()
    except (ImportError, AttributeError):
        return (NODE_ROOT.parents[1] / "models").resolve()


def model_directory() -> Path:
    return (_models_root() / "LLM" / "Qwen3.8").resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _space_required(downloads: tuple[Download, ...], destination: Path) -> int:
    required = 0
    for item in downloads:
        target = destination / item.filename
        partial = target.with_suffix(target.suffix + ".part")
        if target.is_file() and target.stat().st_size == item.size:
            continue
        partial_size = partial.stat().st_size if partial.is_file() else 0
        required += max(0, item.size - partial_size)
    return required


def _preserve_invalid(path: Path, reason: str) -> Path:
    backup = path.with_name(path.name + f".{reason}-{int(time.time())}")
    path.replace(backup)
    print(f"[WARN] Preserved invalid {path.name} as {backup.name}")
    return backup


def _prepare_existing(item: Download, destination: Path, *, offline: bool) -> bool:
    partial = destination.with_suffix(destination.suffix + ".part")
    if destination.is_file():
        if destination.stat().st_size == item.size:
            print(f"[INFO] Verifying existing {item.filename} ...")
            if sha256_file(destination) == item.sha256:
                print(f"[OK] {item.filename}")
                return True
        if offline:
            raise RuntimeError(f"Offline file is not a verified {item.filename}: {destination}")
        _preserve_invalid(destination, "invalid")

    if partial.is_file() and partial.stat().st_size == item.size:
        print(f"[INFO] Verifying completed partial {item.filename} ...")
        if sha256_file(partial) == item.sha256:
            partial.replace(destination)
            print(f"[OK] Promoted verified partial to {destination}")
            return True
        if offline:
            raise RuntimeError(f"Offline partial failed SHA256: {partial}")
        _preserve_invalid(partial, "invalid")
    elif partial.is_file() and partial.stat().st_size > item.size:
        if offline:
            raise RuntimeError(f"Offline partial is larger than expected: {partial}")
        _preserve_invalid(partial, "oversize")
    return False


def _check_disk_space(destination: Path, downloads: tuple[Download, ...]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    required = _space_required(downloads, destination)
    free = shutil.disk_usage(destination).free
    reserve = 2 * 1024**3
    if free < required + reserve:
        raise RuntimeError(
            f"Insufficient disk space in {destination}: need about {(required + reserve) / 1024**3:.1f} GiB, "
            f"free {free / 1024**3:.1f} GiB."
        )


def _download_with_resume(item: Download, destination: Path, *, offline: bool) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if offline:
        raise RuntimeError(f"Offline mode requires an already verified {destination}")

    partial = destination.with_suffix(destination.suffix + ".part")
    downloaded = partial.stat().st_size if partial.is_file() else 0
    if downloaded > item.size:
        backup = partial.with_name(partial.name + f".oversize-{int(time.time())}")
        partial.replace(backup)
        downloaded = 0
    headers = {"User-Agent": USER_AGENT}
    if downloaded:
        headers["Range"] = f"bytes={downloaded}-"
    request = urllib.request.Request(item.url, headers=headers)
    print(
        f"[INFO] Downloading {item.filename} from {downloaded / 1024**3:.2f} GiB "
        f"of {item.size / 1024**3:.2f} GiB"
    )
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        if downloaded and error.code == 416:
            partial.unlink(missing_ok=True)
            _check_disk_space(destination.parent, (item,))
            return _download_with_resume(item, destination, offline=False)
        raise RuntimeError(f"Download failed for {item.filename}: HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Download failed for {item.filename}: {error}") from error
    status = getattr(response, "status", response.getcode())
    if downloaded and status != 206:
        response.close()
        partial.unlink(missing_ok=True)
        _check_disk_space(destination.parent, (item,))
        return _download_with_resume(item, destination, offline=False)
    mode = "ab" if downloaded else "wb"
    next_report = downloaded + 256 * 1024 * 1024
    with response, partial.open(mode) as output:
        while True:
            chunk = response.read(8 * 1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            if downloaded >= next_report:
                print(f"[INFO] {item.filename}: {downloaded / item.size * 100:5.1f}%")
                next_report += 256 * 1024 * 1024
        output.flush()
        os.fsync(output.fileno())
    if partial.stat().st_size != item.size:
        raise RuntimeError(
            f"Downloaded size mismatch for {item.filename}: {partial.stat().st_size}, expected {item.size}. "
            "The .part file was kept for resume."
        )
    print(f"[INFO] Verifying SHA256 for {item.filename} ...")
    actual = sha256_file(partial)
    if actual != item.sha256:
        raise RuntimeError(
            f"SHA256 mismatch for {item.filename}: {actual}, expected {item.sha256}. "
            "The .part file was kept for inspection."
        )
    partial.replace(destination)
    print(f"[OK] Installed {destination}")
    return destination


def install_models(*, variant: str, offline: bool, dry_run: bool) -> None:
    downloads = model_files_for_variant(variant)
    destination = model_directory()
    print(f"[PLAN] Model directory: {destination}")
    print(f"[PLAN] Model variant: {variant}")
    for item in downloads:
        print(
            f"[PLAN] {item.filename}: {item.size / 1024**3:.2f} GiB, "
            f"sha256={item.sha256}, source={item.repository}@{item.revision}"
        )
    if dry_run:
        return
    verified = {
        item.filename: _prepare_existing(item, destination / item.filename, offline=offline)
        for item in downloads
    }
    _check_disk_space(destination, downloads)
    for item in downloads:
        if not verified[item.filename]:
            _download_with_resume(item, destination / item.filename, offline=offline)


def _ensure_upstream_installer(*, offline: bool) -> Path:
    BOOTSTRAP_ROOT.mkdir(parents=True, exist_ok=True)
    path = BOOTSTRAP_ROOT / "install_runtime.py"
    if path.is_file() and sha256_file(path) == UPSTREAM_INSTALLER_SHA256:
        return path
    if path.exists():
        backup = path.with_name(path.name + f".invalid-{int(time.time())}")
        path.replace(backup)
    if offline:
        raise RuntimeError("Offline mode requires the pinned runtime bootstrap installer in the cache.")
    request = urllib.request.Request(UPSTREAM_INSTALLER_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not download the pinned runtime installer: {error}") from error
    if hashlib.sha256(data).hexdigest() != UPSTREAM_INSTALLER_SHA256:
        raise RuntimeError("Pinned runtime installer SHA256 mismatch.")
    temporary = path.with_suffix(".py.part")
    temporary.write_bytes(data)
    temporary.replace(path)
    return path


def _translate_runtime_config() -> None:
    upstream_path = BOOTSTRAP_ROOT / "runtime_config.json"
    if not upstream_path.is_file():
        raise RuntimeError("Pinned runtime installer completed without runtime_config.json.")
    payload = json.loads(upstream_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise RuntimeError("Pinned runtime installer returned an unsupported configuration schema.")

    def prefix(value: str) -> str:
        path = (BOOTSTRAP_ROOT / value).resolve()
        path.relative_to(RUNTIME_ROOT.resolve())
        return path.relative_to(RUNTIME_ROOT).as_posix()

    translated = dict(payload)
    translated["executable"] = prefix(str(payload["executable"]))
    translated["library_dirs"] = [prefix(str(value)) for value in payload.get("library_dirs") or []]
    translated["source_installer"] = {
        "repository": "chflame163/ComfyUI_Qwen_H3_Prompt",
        "commit": UPSTREAM_INSTALLER_COMMIT,
        "sha256": UPSTREAM_INSTALLER_SHA256,
        "license": "MIT",
    }
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = RUNTIME_CONFIG_PATH.with_suffix(".json.part")
    temporary.write_text(json.dumps(translated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(RUNTIME_CONFIG_PATH)
    executable = (RUNTIME_ROOT / translated["executable"]).resolve()
    if not executable.is_file():
        raise RuntimeError(f"Translated llama-server path does not exist: {executable}")
    print(f"[OK] Runtime configured: {executable}")


def install_runtime(*, backend: str, offline: bool, force: bool, dry_run: bool) -> None:
    print(f"[PLAN] llama.cpp b10436 runtime, backend={backend}")
    print(f"[PLAN] Pinned bootstrap: {UPSTREAM_INSTALLER_COMMIT} / {UPSTREAM_INSTALLER_SHA256}")
    if dry_run:
        return
    installer = _ensure_upstream_installer(offline=offline)
    arguments = [sys.executable, str(installer), "--backend", backend]
    if offline:
        arguments.append("--offline")
    if force:
        arguments.append("--force")
    completed = subprocess.run(arguments, cwd=BOOTSTRAP_ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Pinned llama.cpp runtime installer failed with exit code {completed.returncode}.")
    _translate_runtime_config()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install the pinned local Qwen3.8 GGUF model and llama.cpp runtime for the three T8 enhancer nodes."
    )
    parser.add_argument("--model", action="store_true", help="Install/verify GGUF model and mmproj only.")
    parser.add_argument(
        "--model-variant",
        choices=MODEL_VARIANTS,
        default=MODEL_VARIANT_OFFICIAL,
        help=(
            "Model set to install: official (default), uncensored (third-party FP8-derived Q4_K_M), "
            "or all. Both vision-capable variants reuse the pinned mmproj after compatibility testing."
        ),
    )
    parser.add_argument("--runtime", action="store_true", help="Install/verify llama.cpp runtime only.")
    parser.add_argument("--backend", default="auto", help="Runtime backend; default auto hardware detection.")
    parser.add_argument("--offline", action="store_true", help="Use only existing verified files/caches.")
    parser.add_argument("--force", action="store_true", help="Force the runtime installer to rebuild/reinstall its target.")
    parser.add_argument("--dry-run", action="store_true", help="Print the exact plan without downloading or changing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    install_model = args.model or not args.runtime
    install_llama = args.runtime or not args.model
    try:
        if install_llama:
            install_runtime(
                backend=str(args.backend),
                offline=bool(args.offline),
                force=bool(args.force),
                dry_run=bool(args.dry_run),
            )
        if install_model:
            install_models(
                variant=str(args.model_variant),
                offline=bool(args.offline),
                dry_run=bool(args.dry_run),
            )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
