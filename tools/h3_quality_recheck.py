"""Recheck saved real drafts with the current bounded quality implementation.

This is a separate repair experiment, NOT a fresh end-to-end generation A/B.
Original generations, initial messages and file hashes remain in the source.
Only selected failed On drafts may invoke one real correction each, serially.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch

from h3_quality_acceptance import ROOT, response_metrics, load_package, digest
from h3_quality import check_h3, QUALITY_CHECK, QUALITY_REPAIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-corrections", type=int, default=4, choices=range(0, 13))
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("Evidence must be outside the repository.")
    source_bytes = args.source.read_bytes()
    source = json.loads(source_bytes)
    key = getpass.getpass("API key (hidden; not saved): ") if args.max_corrections else ""
    h3, _sd, _runtime = load_package()
    from importlib import import_module
    pipeline = import_module(h3.__package__ + ".quality_pipeline")
    if key:
        key, chat, _upload, provider = h3._provider_config(h3.SEEDANCE_API_MODE, key, "")
    else:
        chat, provider = h3.CHAT_COMPLETIONS_URL, "Seedance"
    records = []
    requests = []
    original_post = h3.requests.Session.post
    count = 0

    def observed_post(self, *values, **kwargs):
        observation = {"request_parameters": {k: kwargs["json"][k] for k in
            ("model", "stream", "temperature", "max_tokens", "max_completion_tokens", "seed") if k in kwargs["json"]}}
        requests[-1]["http_attempts"].append(observation)
        try:
            response = original_post(self, *values, **kwargs)
        except Exception as error:
            observation["error_type"] = type(error).__name__
            raise
        observation["status"] = response.status_code
        original_lines = response.iter_lines
        def lines(*args, **opts):
            for raw in original_lines(*args, **opts):
                text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                if text.strip().startswith("data:"):
                    try:
                        response_metrics(json.loads(text.strip()[5:].strip()), observation)
                    except ValueError:
                        pass
                yield raw
        response.iter_lines = lines
        return response

    evidence = {"schema": "t8-real-draft-recheck/v1", "source_file_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "source_generation_sha256": source["source_sha256"],
                "source_sha256": digest({p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                    ("nodes.py", "seedance20.py", "h3_quality.py", "quality_pipeline.py", "h3_prompt_relay.py")}),
                "scope": "Separate repair experiment on saved real initial drafts, no new initial generation; not mixed with generation A/B.",
                "tests": records}
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with patch.object(h3.requests.Session, "post", observed_post), h3.requests.Session() as session:
            for old in source["tests"]:
                if old["outcome"] != "success":
                    continue
                requests.clear()
                case = old["input"]
                draft = old["requests"][0]["output"]
                labels = ["<Picture 1>", "<Picture 2>"] if case["images"] == "pair" else ["<Picture 1>"] if case["images"] == "last" else []
                check_options = dict(task_type=case["task"], duration=case["seconds"], shot_count=int(case["shots"]),
                                     language="中文", source=case["prompt"], media_labels=labels)
                before = check_h3(draft, **check_options)
                def complete(messages):
                    nonlocal count
                    if count >= args.max_corrections:
                        raise RuntimeError("Explicit experiment correction cap reached")
                    count += 1
                    request = {"messages": messages, "message_sha256": digest(messages), "http_attempts": []}
                    requests.append(request)
                    start = time.monotonic()
                    try:
                        response = h3._request_completion(session, key, messages, "balanced", chat,
                                                          provider, h3.MODEL_ID, temperature_override=0.1)
                        request.update(output=response, output_sha256=digest(response))
                        return response
                    except Exception as error:
                        request["error_type"] = type(error).__name__
                        raise
                    finally:
                        request["elapsed_seconds"] = round(time.monotonic()-start, 3)
                start = time.monotonic()
                result, metrics = pipeline.h3_quality_result(draft,
                    mode=QUALITY_REPAIR if old["on"] else QUALITY_CHECK,
                    messages=old["requests"][0]["messages"], complete=complete, **check_options)
                record = {"case_id":old["case_id"], "repeat":old["repeat"], "on":old["on"],
                          "source_initial_sha256": old["requests"][0]["output_sha256"],
                          "before":before, "after":check_h3(result, **check_options), "quality_metadata":metrics,
                          "output":result, "output_sha256":digest(result), "requests":list(requests),
                          "logical_calls":len(requests), "elapsed_seconds":round(time.monotonic()-start, 3)}
                if key and key in json.dumps(record, ensure_ascii=False):
                    raise SystemExit("Secret safety check failed; nothing saved.")
                records.append(record)
                (destination/"recheck.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
                print(json.dumps({k:record[k] for k in ("case_id","repeat","on","logical_calls")}),flush=True)
                if any(r.get("error_type") for r in requests):
                    raise SystemExit("Stopped after actual transport failure; complete draft is retained.")
    finally:
        key = ""


if __name__ == "__main__":
    main()
