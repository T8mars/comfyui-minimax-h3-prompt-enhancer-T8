"""Native H3/Seedance quality adapters; never initialize a model or provider."""
from __future__ import annotations

import json
from contextlib import contextmanager
try:
    from .h3_quality import (QUALITY_OFF, check_h3, check_seedance, run_quality,
                             repair_protocol, accept_correction, body_for, LITERAL_RE,
                             correction_messages)
    from .h3_prompt_relay import compile_relay_response
    from .directional_skills import DIRECTOR_OFF, is_drama_skill
except ImportError:
    from h3_quality import (QUALITY_OFF, check_h3, check_seedance, run_quality,
                            repair_protocol, accept_correction, body_for, LITERAL_RE,
                            correction_messages)
    from h3_prompt_relay import compile_relay_response
    from directional_skills import DIRECTOR_OFF, is_drama_skill


@contextmanager
def retained_draft_provider(provider, state, *, enabled=False, progress=None):
    """A cleanup error must not erase a successfully created draft.

    __enter__ and body errors still propagate. Never claim resources were freed
    when __exit__ failed; record a separate safe cleanup status instead.
    """
    active = provider.__enter__()
    try:
        yield active
    except BaseException as error:
        try:
            suppress = provider.__exit__(type(error), error, error.__traceback__)
        except Exception:
            # Cleanup is secondary to the failed generation, not its cause.
            raise error
        if not suppress:
            raise
    else:
        try:
            provider.__exit__(None, None, None)
        except Exception:
            if not enabled or not state.get("draft"):
                raise
            if progress:
                progress("local_cleanup_failed", quality_metadata={"result": "cleanup_failed_draft_kept"})


def h3_quality_result(draft, *, mode, messages, complete, task_type, duration,
                      shot_count, language, source, media_labels=None, relay_config=None,
                      progress=None, budget_used=False, director_skill=DIRECTOR_OFF):
    if mode == QUALITY_OFF:
        return draft, {}
    options = dict(task_type=task_type, duration=duration, shot_count=shot_count,
                   language=language, source=source, media_labels=media_labels)
    drama = is_drama_skill(director_skill)
    def correction(original, text, report):
        return correction_messages(original, text, report, **({"requested_dialogue": True} if drama else {}))
    if not relay_config:
        return run_quality(draft, mode=mode, messages=messages, complete=complete,
                           check=lambda text: check_h3(text, **options),
                           repair=lambda text: repair_protocol(text, task_type=task_type, duration=duration),
                           **({"build_correction": correction} if drama else {}),
                           **({"accept": lambda old, new, before, after: accept_correction(old, new, before, after, protect_generated_vocals=True)} if drama else {}),
                           progress=progress, budget_used=budget_used)

    def compile_text(text):
        return compile_relay_response(text, duration, relay_config["event_count"],
                                      relay_config["time_ranges"], task_type, language)

    def check(text):
        try:
            compiled = compile_text(text)
        except (ValueError, TypeError):
            return {"issues": [{"code": "relay_invalid_authoring", "message": "Relay 编排未通过原有编译器。"}],
                    "unchecked": ["relay_compilation", "physical_plausibility", "rendered_video_quality"]}
        report = check_h3(compiled["enhanced_prompt"], **options)
        data = json.loads(text)
        # Each execution surface is independently checked for descriptive
        # language. Native/JSON repetitions are never counted as duplicate speech.
        for surface in [data["global_prompt"], *[e["prompt"] + " " + e["end_state"] for e in data["events"]]]:
            extra = check_seedance(surface, language=language)
            if any(i["code"] == "h3_descriptive_language" for i in extra["issues"]):
                report["issues"].append({"code": "h3_descriptive_language", "message": "Relay 执行文本说明语言不符。"})
        report["issues"] = list({i["code"]: i for i in report["issues"]}.values())
        report["unchecked"].append("relay_semantic_equivalence")
        return report

    def repair(text):
        compile_text(text)  # Do not salvage a malformed authoring envelope here.
        data = json.loads(text)
        native, changes = repair_protocol(data["native_prompt"], task_type=task_type, duration=duration)
        if not changes:
            return text, []
        data["native_prompt"] = native
        return json.dumps(data, ensure_ascii=False), changes

    def literals(text):
        data = json.loads(text)
        return [m.group() for m in LITERAL_RE.finditer(body_for(data["native_prompt"]))], data["global_prompt"], data["events"]

    def accept(old, new, before, after):
        try:
            compile_text(new)
            a, b = json.loads(old), json.loads(new)
        except (ValueError, TypeError):
            return False
        if len(a["events"]) != len(b["events"]):
            return False
        for first, second in zip(a["events"], b["events"]):
            if first["weight"] != second["weight"]:
                return False
            for key in ("prompt", "end_state"):
                if [m.group() for m in LITERAL_RE.finditer(first[key])] != [m.group() for m in LITERAL_RE.finditer(second[key])]:
                    return False
        return accept_correction(a["native_prompt"], b["native_prompt"], before, after,
                                 **({"protect_generated_vocals": True} if drama else {}))

    def build(messages, text, report):
        corrected = correction(messages, text, report)
        corrected[-1]["content"] += (
            " Return ONLY the complete original Relay authoring JSON envelope with global_prompt, events and native_prompt. "
            "Retain event count, weights, exact event speech, end-state facts and requested ranges. "
            "Apply native H3 protocol fixes only inside native_prompt, never to the Relay execution syntax."
        )
        return corrected

    return run_quality(draft, mode=mode, messages=messages, complete=complete,
                       check=check, repair=repair, accept=accept, literals=literals,
                       build_correction=build, progress=progress, budget_used=budget_used)


def seedance_quality_result(draft, *, mode, messages, complete, language, source,
                            shot_count=0, progress=None, director_skill=DIRECTOR_OFF):
    return run_quality(draft, mode=mode, messages=messages, complete=complete,
                       check=lambda text: check_seedance(text, language=language, source=source, shot_count=shot_count),
                       **({"build_correction": lambda original, text, report: correction_messages(original, text, report, requested_dialogue=True)}
                          if is_drama_skill(director_skill) else {}),
                       **({"accept": lambda old, new, before, after: accept_correction(old, new, before, after, protect_generated_vocals=True)}
                          if is_drama_skill(director_skill) else {}),
                       progress=progress)
