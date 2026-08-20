import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
COMFYUI_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(COMFYUI_ROOT))
sys.path.insert(0, str(PROJECT_DIR))

from comfy_api.latest import VideoFromFile
from live_smoke import IMAGE_CODE, make_image_fixture
from workshop_live_smoke import (
    EARLY_VIDEO_CODE,
    LATE_VIDEO_CODE,
    evaluate_result as evaluate_visual_result,
    make_complete_video_fixture,
)


SPEC = importlib.util.spec_from_file_location(
    "t8_local_qwen_live_package",
    PROJECT_DIR / "__init__.py",
    submodule_search_locations=[str(PROJECT_DIR)],
)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)
h3 = sys.modules[f"{SPEC.name}.nodes"]
seedance20 = sys.modules[f"{SPEC.name}.seedance20"]
music3 = sys.modules[f"{SPEC.name}.music3"]
local_provider = sys.modules[f"{SPEC.name}.local_qwen_provider"]
local_runtime = sys.modules[f"{SPEC.name}.local_qwen_runtime"]


REPORT_PATH = PROJECT_DIR / "tests" / "fixtures" / "local_qwen_quality_2026-08-19.json"
LOCAL_COMMON = {
    "api_mode": local_provider.LOCAL_QWEN_API_MODE,
    "local_context_size": 32768,
    "local_max_tokens": 4096,
    "local_think_mode": local_runtime.LOCAL_THINK_OFF,
    "local_reasoning_effort": "medium",
    "local_unload_policy": local_runtime.LOCAL_KEEP_WARM,
    "local_comfy_memory_policy": local_runtime.LOCAL_RELEASE_COMFY_AUTO,
}


class ResourceMonitor:
    def __init__(self):
        self.stop_event = threading.Event()
        self.samples = []
        self.thread = threading.Thread(target=self._run, name="t8-local-qwen-resource-monitor", daemon=True)

    @staticmethod
    def _gpu_used_mib():
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            values = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
            return max(values) if values else None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _system_ram_used_mib():
        try:
            import psutil

            return round(psutil.virtual_memory().used / 1024**2)
        except (ImportError, AttributeError):
            return None

    def _run(self):
        while not self.stop_event.wait(1.0):
            self.samples.append(
                {
                    "gpu_used_mib": self._gpu_used_mib(),
                    "system_ram_used_mib": self._system_ram_used_mib(),
                }
            )

    def __enter__(self):
        self.samples.append(
            {
                "gpu_used_mib": self._gpu_used_mib(),
                "system_ram_used_mib": self._system_ram_used_mib(),
            }
        )
        self.thread.start()
        return self

    def __exit__(self, *_args):
        # Release the managed llama-server before taking the final resource
        # sample; otherwise "after_release" would actually describe a loaded
        # 17 GB model.
        local_runtime.LOCAL_QWEN_MANAGER.release()
        baseline_gpu = self.samples[0].get("gpu_used_mib") if self.samples else None
        deadline = time.monotonic() + 15.0
        while baseline_gpu is not None and time.monotonic() < deadline:
            current = self._gpu_used_mib()
            if current is None or current <= baseline_gpu + 1024:
                break
            time.sleep(0.5)
        self.stop_event.set()
        self.thread.join(timeout=5)
        self.samples.append(
            {
                "gpu_used_mib": self._gpu_used_mib(),
                "system_ram_used_mib": self._system_ram_used_mib(),
            }
        )

    def summary(self):
        def values(name):
            return [sample[name] for sample in self.samples if sample.get(name) is not None]

        gpu = values("gpu_used_mib")
        ram = values("system_ram_used_mib")
        return {
            "sample_count": len(self.samples),
            "gpu_baseline_mib": gpu[0] if gpu else None,
            "gpu_peak_mib": max(gpu) if gpu else None,
            "gpu_after_release_mib": gpu[-1] if gpu else None,
            "system_ram_baseline_mib": ram[0] if ram else None,
            "system_ram_peak_mib": max(ram) if ram else None,
            "system_ram_after_release_mib": ram[-1] if ram else None,
        }


def _sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timed(callable_):
    started = time.perf_counter()
    value = callable_()
    return value, round(time.perf_counter() - started, 3)


def _has_all(value, groups):
    lowered = value.casefold()
    return all(any(term.casefold() in lowered for term in group) for group in groups)


def _chinese_ratio(lyrics):
    body = re.sub(r"\[[^\]]+\]", "", lyrics)
    letters = re.findall(r"[A-Za-z\u4e00-\u9fff]", body)
    chinese = re.findall(r"[\u4e00-\u9fff]", body)
    return len(chinese) / max(1, len(letters))


def _music_constraint_checks(caption):
    normalized = re.sub(r"\s+", " ", caption.casefold())
    return {
        "bpm_92": bool(re.search(r"(?<!\d)92\s*bpm\b", normalized)),
        "key_d_major": bool(re.search(r"\bd\s+major\b", normalized)),
        "meter_4_4": bool(re.search(r"(?<!\d)4\s*/\s*4(?!\d)", normalized)),
        "female_lead": bool(
            re.search(r"\bfemale\b.{0,32}\b(?:lead|vocal|singer|voice)\b", normalized)
            or re.search(r"\b(?:lead|vocal|singer|voice)\b.{0,32}\bfemale\b", normalized)
        ),
        "piano": "piano" in normalized,
        "acoustic_guitar": bool(re.search(r"\bacoustic\b.{0,40}\bguitar\b", normalized)),
        "rap_excluded": bool(
            re.search(
                r"(?:\bno\s+rap\b|\bwithout\b.{0,80}\brap\b|\brap[- ]free\b|"
                r"\b(?:exclude|excludes|excluded|excluding)\b.{0,24}\brap\b|"
                r"\brap\b.{0,24}\b(?:absent|excluded|prohibited|forbidden)\b)",
                normalized,
            )
        ),
    }


def run_quality_acceptance():
    status = local_runtime.runtime_status()
    if not all(status.get(key) for key in ("runtime_installed", "model_installed", "mmproj_installed")):
        raise RuntimeError("Local Qwen runtime/model/mmproj is not fully installed: " + json.dumps(status))

    cases = []
    hard_failures = []
    monitor = ResourceMonitor()
    started = time.perf_counter()
    try:
        with monitor:
            settings = local_provider.settings_from_values(
                local_context_size=32768,
                local_max_tokens=1024,
                local_unload_policy=local_runtime.LOCAL_KEEP_WARM,
            )
            repeated = []
            repeat_times = []
            with local_provider.LocalQwenProvider(settings, vision=False) as provider:
                messages = [
                    {"role": "system", "content": "Return exactly three concise Chinese bullet points about stable camera motion."},
                    {"role": "user", "content": "使用固定种子生成。"},
                ]
                for _ in range(3):
                    value, elapsed = _timed(
                        lambda: provider.complete(messages, temperature=0.2, seed=2026081901)
                    )
                    repeated.append(value)
                    repeat_times.append(elapsed)
            repeat_exact = len(set(repeated)) == 1
            cases.append(
                {
                    "id": "same_seed_repeatability",
                    "score": 100 if repeat_exact else 60,
                    "passed": repeat_exact,
                    "elapsed_seconds": repeat_times,
                    "output_sha256": [_sha256_text(value) for value in repeated],
                }
            )
            if not repeat_exact:
                hard_failures.append("same seed did not produce byte-identical output across three runs")

            h3_text, h3_text_time = _timed(
                lambda: h3.enhance_prompt(
                    prompt="A paper bird crosses a quiet library in two shots, then lands beside a glowing map.",
                    task_type="T2VA",
                    duration_seconds=8,
                    shot_count="2",
                    rewrite_mode="strict",
                    output_language="English",
                    official_skill_profile=h3.STRICT_SKILL_PROFILE,
                    constraints="Exactly two shots; no dialogue; preserve the paper bird, library, and glowing map.",
                    seed=2026081902,
                    **LOCAL_COMMON,
                )
            )
            h3_text_checks = {
                "nonempty": bool(h3_text.strip()),
                "official_fields": _has_all(
                    h3_text,
                    [["integrated_multimodal_description:"], ["overall_soundscape:"], ["non_diegetic_music:"]],
                ),
                "constraints": _has_all(h3_text, [["paper bird"], ["library"], ["glowing map"], ["shot 1"], ["shot 2"]]),
            }
            h3_text_score = round(sum(h3_text_checks.values()) / len(h3_text_checks) * 100, 1)
            cases.append(
                {
                    "id": "h3_t2va_contract",
                    "score": h3_text_score,
                    "passed": all(h3_text_checks.values()),
                    "checks": h3_text_checks,
                    "elapsed_seconds": h3_text_time,
                    "output_sha256": _sha256_text(h3_text),
                    "output_characters": len(h3_text),
                }
            )
            if not all(h3_text_checks.values()):
                hard_failures.append("H3 T2VA contract/constraint check failed")

            music_result, music_time = _timed(
                lambda: music3.enhance_music3_prompt(
                    music_idea="原创中文公路民谣，从克制夜行逐步走向明亮坚定的最终副歌。",
                    lyrics_mode=music3.GENERATE_LYRICS_MODE,
                    lyrics_language="中文",
                    target_duration_seconds=150,
                    rewrite_mode="balanced",
                    quality_mode=music3.FULL_QUALITY_MODE,
                    structure_preset=music3.POP_STRUCTURE,
                    constraints_and_exclusions="Exactly 92 BPM in D major, 4/4, female lead, piano and acoustic guitar, no rap.",
                    fixed_bpm=92,
                    key_scale="D major",
                    meter="4/4",
                    seed=2026081903,
                    **{key: value for key, value in LOCAL_COMMON.items() if key != "local_max_tokens"},
                )
            )
            lyrics, caption, payload_text, enhancement_report_text = music_result
            payload = json.loads(payload_text)
            enhancement_report = json.loads(enhancement_report_text)
            lyric_lines = [
                line.strip()
                for line in lyrics.splitlines()
                if line.strip() and not line.strip().startswith("[") and len(line.strip()) >= 6
            ]
            constraint_checks = _music_constraint_checks(caption)
            music_checks = {
                "chinese_lyrics": _chinese_ratio(lyrics) >= 0.85,
                "section_tags": _has_all(lyrics, [["[Verse]"], ["[Chorus]"], ["[Bridge]"], ["[Outro]"]]),
                "official_caption_headings": _has_all(
                    caption,
                    [["### Global Metadata"], ["### Vocal Details"], ["### Arrangement"]],
                ),
                "explicit_constraints": all(constraint_checks.values()),
                "payload_consistency": payload == {"input": lyrics, "instructions": caption},
                "official_reference_used": enhancement_report.get("reference_count", 0) >= 1,
                "local_stages": all(stage.get("source") == "local_model" for stage in enhancement_report.get("stages", [])),
                "lyrics_not_copied_to_caption": not any(line in caption for line in lyric_lines),
            }
            music_score = round(sum(music_checks.values()) / len(music_checks) * 100, 1)
            cases.append(
                {
                    "id": "music3_chinese_lyrics_official_full",
                    "score": music_score,
                    "passed": all(music_checks.values()),
                    "checks": music_checks,
                    "constraint_checks": constraint_checks,
                    "elapsed_seconds": music_time,
                    "lyrics_sha256": _sha256_text(lyrics),
                    "caption_sha256": _sha256_text(caption),
                    "lyrics_characters": len(lyrics),
                    "caption_characters": len(caption),
                    "request_count": enhancement_report.get("request_count"),
                    "reference_count": enhancement_report.get("reference_count"),
                    "warnings": enhancement_report.get("warnings"),
                }
            )
            if not all(music_checks.values()):
                hard_failures.append("Music 3 Chinese lyrics/official Skill check failed")

            with tempfile.TemporaryDirectory(prefix="t8_local_qwen_quality_") as directory:
                video_path = Path(directory) / "visual_timeline.mp4"
                make_complete_video_fixture(video_path)
                common_prompt = (
                    "Inspect the attached image and every ordered timestamped video sample. Transcribe every visible "
                    "alphanumeric code exactly. Describe both image shapes and colors, then preserve the video's early "
                    "and late shapes, colors, movement directions, hard transition, and temporal order."
                )
                visual_kwargs = {
                    **LOCAL_COMMON,
                    "local_video_sample_fps": 2.0,
                }
                h3_visual, h3_visual_time = _timed(
                    lambda: h3.enhance_prompt(
                        prompt=common_prompt,
                        task_type="Ref2VA",
                        duration_seconds=10,
                        rewrite_mode="strict",
                        output_language="English",
                        official_skill_profile=h3.STRICT_SKILL_PROFILE,
                        reference_images={"reference_image_0": make_image_fixture()},
                        reference_videos={"reference_video_0": VideoFromFile(str(video_path))},
                        constraints="Do not omit, alter, translate, or reverse any visible code or temporal phase.",
                        seed=2026081904,
                        **visual_kwargs,
                    )
                )
                h3_visual_failures = evaluate_visual_result(h3_visual)
                h3_visual_score = round(max(0, 100 - len(h3_visual_failures) * 10), 1)
                cases.append(
                    {
                        "id": "h3_ref2va_image_video_evidence",
                        "score": h3_visual_score,
                        "passed": not h3_visual_failures,
                        "failures": h3_visual_failures,
                        "elapsed_seconds": h3_visual_time,
                        "output_sha256": _sha256_text(h3_visual),
                        "output_characters": len(h3_visual),
                        "fixture_codes": [IMAGE_CODE, EARLY_VIDEO_CODE, LATE_VIDEO_CODE],
                    }
                )
                if h3_visual_failures:
                    hard_failures.append("H3 visual evidence check failed: " + "; ".join(h3_visual_failures))

                seedance_visual, seedance_time = _timed(
                    lambda: seedance20.enhance_seedance20_prompt(
                        prompt=common_prompt,
                        task_intent="MultiRef",
                        complexity_mode="复杂分镜式",
                        duration_seconds="10",
                        shot_count="3",
                        rewrite_mode="strict",
                        output_detail="详细",
                        output_language="English",
                        reference_images={"reference_image_0": make_image_fixture()},
                        reference_videos={"reference_video_0": VideoFromFile(str(video_path))},
                        reference_roles="@Image 1 supplies appearance; @Video 1 supplies sampled temporal action and order.",
                        constraints="Do not omit, alter, translate, or reverse any visible code or temporal phase.",
                        seed=2026081905,
                        **visual_kwargs,
                    )
                )
                seedance_failures = evaluate_visual_result(seedance_visual)
                seedance_score = round(max(0, 100 - len(seedance_failures) * 10), 1)
                cases.append(
                    {
                        "id": "seedance20_multiref_image_video_evidence",
                        "score": seedance_score,
                        "passed": not seedance_failures,
                        "failures": seedance_failures,
                        "elapsed_seconds": seedance_time,
                        "output_sha256": _sha256_text(seedance_visual),
                        "output_characters": len(seedance_visual),
                        "fixture_codes": [IMAGE_CODE, EARLY_VIDEO_CODE, LATE_VIDEO_CODE],
                    }
                )
                if seedance_failures:
                    hard_failures.append("Seedance visual evidence check failed: " + "; ".join(seedance_failures))
    finally:
        local_runtime.LOCAL_QWEN_MANAGER.release()

    overall_score = round(sum(case["score"] for case in cases) / max(1, len(cases)), 2)
    passed = not hard_failures and overall_score >= 90 and all(case["passed"] for case in cases)
    return {
        "schema_version": "t8-local-qwen-quality/v1",
        "provider": "Qwen3.8-27B-Q4_K_M.gguf via llama.cpp",
        "runtime": {
            "backend": status.get("backend"),
            "model_size": local_runtime.DEFAULT_MODEL_SIZE,
            "model_sha256": local_runtime.DEFAULT_MODEL_SHA256,
            "mmproj_size": local_runtime.DEFAULT_MMPROJ_SIZE,
            "mmproj_sha256": local_runtime.DEFAULT_MMPROJ_SHA256,
            "llama_cpp_tag": "b10436",
        },
        "score_formula": "Equal-weight mean of deterministic contract, constraint, language, evidence, payload, official-reference and same-seed checks; no subjective score.",
        "minimum_score": 90,
        "overall_score": overall_score,
        "passed": passed,
        "hard_failures": hard_failures,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "resources": monitor.summary(),
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Real local Qwen quality and resource acceptance for all three T8 nodes.")
    parser.add_argument(
        "--confirm-local-large-model",
        action="store_true",
        help="Acknowledge loading the installed ~18GB local model and running multiple long inferences.",
    )
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    if not args.confirm_local_large_model:
        parser.error("Refusing the long local run without --confirm-local-large-model.")
    report = run_quality_acceptance()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
