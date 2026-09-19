"""Build an external candidate Registry ZIP and CPU-load it without live repo fallback.

Not a Registry publication or a running ComfyUI queue test. No model inference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from verify_repository import ROOT, tracked_files, verify_registry_package_hygiene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == ROOT or ROOT in output.parents:
        raise SystemExit("Artifact evidence must be outside the repository.")
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "candidate-registry.zip"
    if destination.exists():
        raise SystemExit("Do not overwrite package evidence; select another directory.")
    # This pre-existing private, untracked document is not part of this change
    # and must not enter a candidate publish artifact.
    files = [p for p in tracked_files() if p.relative_to(ROOT).as_posix() != "docs/AGENT_HANDOFF_H3_PROMPT_RELAY.md"]
    hygiene = verify_registry_package_hygiene(files)
    names = [p.relative_to(ROOT).as_posix() for p in files]
    ignored = subprocess.run(["git", "-c", "core.excludesFile=.comfyignore", "check-ignore", "--no-index", "--stdin", "-z"],
                             cwd=ROOT, input=b"\0".join(n.encode() for n in names) + b"\0", capture_output=True, check=False)
    if ignored.returncode not in (0, 1):
        raise SystemExit("Could not evaluate package exclusions.")
    excluded = {n.decode() for n in ignored.stdout.split(b"\0") if n}
    shipped = [p for p in files if p.relative_to(ROOT).as_posix() not in excluded]
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in shipped:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with tempfile.TemporaryDirectory(prefix="t8-registry-drama-") as temporary:
        install = Path(temporary) / "node"
        with zipfile.ZipFile(destination) as archive:
            if archive.testzip() is not None:
                raise SystemExit("CRC validation failed.")
            members = archive.namelist()
            assert sum(n.endswith(".gif") for n in members) == 8
            assert not any(n.startswith("web/js/assets/t8-case-previews/") and n.endswith(".gif") for n in members)
            assert not any(n.endswith(".gguf") or n == "roadmap.md" for n in members)
            archive.extractall(install)
        code = r'''
import asyncio, importlib.util, json, pathlib, sys
sys.argv = ["registry-drama-smoke", "--cpu"]
sys.path.insert(0, sys.argv_comfy)
p = pathlib.Path(sys.argv_install)
spec = importlib.util.spec_from_file_location("registry_drama_smoke", p / "__init__.py", submodule_search_locations=[str(p)])
package = importlib.util.module_from_spec(spec); sys.modules[spec.name] = package; spec.loader.exec_module(package)
extension = asyncio.run(package.comfy_entrypoint()); node_list = asyncio.run(extension.get_node_list())
schemas = [n.define_schema() for n in node_list]
assert len(schemas) == 25
assert [s.node_id for s in schemas[:3]] == ["MiniMaxH3PromptEnhancerT8", "Seedance20PromptEnhancerT8", "MiniMaxMusic3PromptEnhancerT8"]
assert len(schemas[0].outputs) == 6 and len(schemas[1].outputs) == 1
module = sys.modules[spec.name + ".directional_skills"]
assert len(module.DIRECTOR_OPTIONS) == 7 and module.DIRECTOR_LABELS[module.DIRECTOR_OPTIONS[0]] == "none"
for skill in ("drama_scene", "situational_drama"):
    assert module.prepare_director_skill(skill, 2) == (skill, 2)
    assert module.director_metadata(skill, language="中文", mode="Seedance 2.0", shot_count=2)["authoring_revision"] == "1.0.0"
for name, loaded in list(sys.modules.items()):
    if name.startswith(spec.name) and getattr(loaded, "__file__", None):
        assert pathlib.Path(loaded.__file__).is_relative_to(p), name
print(json.dumps({"node_count":len(schemas), "node_ids":[s.node_id for s in schemas], "native_outputs":True, "new_skills":True, "live_repo_fallback":False}))
'''
        bootstrap = "import sys; sys.argv_comfy=" + repr(str(ROOT.parents[1])) + "; sys.argv_install=" + repr(str(install)) + ";" + code
        result = subprocess.run([sys.executable, "-c", bootstrap], cwd=temporary, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60, check=False,
                                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        if result.returncode:
            raise SystemExit("Isolated CPU archive load failed:\n" + result.stderr[-4500:])
        observation = json.loads(result.stdout.strip().splitlines()[-1])
    evidence = {**hygiene, **observation, "crc": "passed", "official_gifs": 8, "t8_gifs": 0,
                "archive_bytes": destination.stat().st_size, "archive_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
    (output / "candidate-registry-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
