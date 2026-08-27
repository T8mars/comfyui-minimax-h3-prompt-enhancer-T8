import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "t8_case_importer_test",
    ROOT / "tools" / "import_unofficial_case_library_v2.py",
)
importer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = importer
SPEC.loader.exec_module(importer)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaseImporterTests(unittest.TestCase):
    def test_evidence_variant_can_bind_to_stable_template_id(self):
        primary = {
            "case_id": "case-primary",
            "template_id": "t8-case-stable-template-v1",
            "template_action": "selector",
        }
        evidence = {
            "case_id": "case-evidence",
            "template_id": "t8-case-stable-template-v1",
            "template_action": "evidence_variant",
            "duplicate_of": "t8-case-stable-template-v1",
        }

        importer._validate_evidence_binding(evidence, primary, {"case-evidence": evidence})

    def test_evidence_variant_rejects_another_template_binding(self):
        primary = {
            "case_id": "case-primary",
            "template_id": "t8-case-stable-template-v1",
            "template_action": "selector",
        }
        evidence = {
            "case_id": "case-evidence",
            "template_id": "t8-case-stable-template-v1",
            "template_action": "evidence_variant",
            "duplicate_of": "t8-case-other-template-v1",
        }

        with self.assertRaises(importer.LibraryImportError):
            importer._validate_evidence_binding(evidence, primary, {"case-evidence": evidence})

    def test_direct_final_adapters_import_only_reusable_creative_dna(self):
        with tempfile.TemporaryDirectory() as temporary:
            case_root = Path(temporary)
            creative_path = case_root / "creative-dna.json"
            creative_path.write_text(json.dumps({
                "mechanism": "A fixed visible controller produces one matching full-body response per beat.",
                "invariants": [
                    {"rule": "Controller and responder stay jointly visible."},
                    {"rule": "Every cue receives exactly one same-beat response."},
                ],
                "slots": [
                    {"name": "controller", "description": "A replaceable foreground control instrument."},
                    {"name": "responder", "description": "A replaceable full-body responder."},
                ],
                "failure_modes": [
                    {"failure": "The responder anticipates the cue.", "repair": "Start cue and response together."},
                ],
            }), encoding="utf-8")
            models = {}
            final_prompts = {}
            for target in importer.TARGETS:
                final_prompt = f"private finished example for {target}"
                final_prompts[target] = final_prompt
                adapter = case_root / f"{target}.json"
                adapter.write_text(json.dumps({
                    "case_id": "case-a",
                    "target": target,
                    "direct_final": True,
                    "node_execution": False,
                    "compiled_prompt": final_prompt,
                    "prompt_validation_context": {
                        "prompt_sha256": hashlib.sha256(final_prompt.encode("utf-8")).hexdigest(),
                    },
                    "node": None,
                    "inputs": {},
                    "media_connections": [],
                }), encoding="utf-8")
                models[target] = {
                    "adapter_path": str(adapter),
                    "adapter_sha256": _sha256(adapter),
                }
            record = {
                "case_id": "case-a",
                "case_path": str(case_root),
                "creative_dna_sha256": _sha256(creative_path),
                "models": models,
            }

            creative_dna, hashes = importer._load_creative_dna(record)

            self.assertIn("fixed visible controller", creative_dna)
            self.assertIn("Do not copy from the source:", creative_dna)
            self.assertNotIn(final_prompts["h3"], creative_dna)
            self.assertNotIn(final_prompts["seedance20"], creative_dna)
            self.assertEqual(hashes, {target: models[target]["adapter_sha256"] for target in importer.TARGETS})


if __name__ == "__main__":
    unittest.main()
