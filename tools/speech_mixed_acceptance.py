"""Explicit synthetic bilingual CPU-ASR acceptance, never a user-service lifecycle action."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import speech_real_acceptance as acceptance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-real", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strata-source", type=Path, default=Path("E:/Strata"))
    parser.add_argument("--asr-model-dir", type=Path, default=Path("E:/Strata-asr-models/Confucius4-R2T2-GGUF"))
    args = parser.parse_args()
    out = acceptance.output_directory(args.output, args.strata_source)
    out.mkdir(parents=True, exist_ok=False)
    root_literal = str(out).replace("'", "''")
    # Local installed SAPI voices create known synthetic source, not a fake ASR.
    code = """$root='%s'
$voice=New-Object -ComObject SAPI.SpVoice
$parts=@(@('Huihui','red-circle.wav','红色圆圈向右移动。'),@('Zira','blue-background.wav','The background turns blue.'))
foreach($part in $parts){
 $token=@($voice.GetVoices() | Where-Object {$_.GetDescription() -match $part[0]})[0]
 if(-not $token){throw 'Required installed synthetic voice missing'}
 $voice.Voice=$token
 $stream=New-Object -ComObject SAPI.SpFileStream
 $stream.Open((Join-Path $root $part[1]),3,$false)
 $voice.AudioOutputStream=$stream
 [void]$voice.Speak($part[2])
 $stream.Close()
}
""" % root_literal
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", code], check=True, timeout=30)
    import numpy as np
    import requests
    import torch
    first, second = [acceptance.pcm48_stereo(out / name) for name in ("red-circle.wav", "blue-background.wav")]
    pcm = np.concatenate([first, np.zeros((2, 24000), np.float32), second], axis=1)
    modules = acceptance.load_plugin()
    session = requests.Session(); session.trust_env = False
    def identity():
        response = session.get("http://127.0.0.1:8081/v1/status", timeout=10)
        response.raise_for_status()
        return acceptance.service_identity(response.json())
    before = identity(); started = time.monotonic()
    with acceptance.OwnedASR(args.strata_source, out / "owned-asr", args.asr_model_dir, None) as owned, acceptance.Workers(out / "owned-asr") as workers:
        config = {"schema_version": "t8-llm-provider-config/v1", "provider": "Strata", "strata_settings": {"url": owned.url}}
        result = modules["speech_reference"].T8SpeechReference.execute(mode="Enabled", source_mode="AUDIO", language="Auto",
            audio={"waveform": torch.from_numpy(pcm[None].copy()), "sample_rate": 48000}, provider_config=config).result
        workers.wait_empty()
        text = acceptance.normalized(result[1]).casefold()
        matches = [acceptance.normalized(word).casefold() in text for word in ("红色圆圈向右移动", "The background turns blue")]
        after = identity(); acceptance.assert_residency(before, after)
        evidence = dict(synthetic_source=True, native_cpu_asr=True, seconds=round(time.monotonic()-started, 3),
            expected=["红色圆圈向右移动。", "The background turns blue."], verbatim_phrases=matches,
            passed=all(matches), reference=result[0], srt=result[3], requests=owned.requests,
            owned_workers_after=workers.current(), user_service_before=before, user_service_after=after,
            plugin_source_sha256={p.name: acceptance.sha256(p) for p in acceptance.ROOT.glob("*.py")},
            fixture_sha256={name: acceptance.sha256(out / name) for name in ("red-circle.wav", "blue-background.wav")})
    acceptance.save(out / "mixed-asr-results.json", evidence)
    print(json.dumps({key: evidence[key] for key in ("passed", "seconds", "verbatim_phrases", "owned_workers_after")}, ensure_ascii=False))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
