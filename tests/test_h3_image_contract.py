"""Offline contract/source tests. These do not measure model or image quality."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import h3_image_contract as c


def result(caption="A white ceramic cup.", ratio="4:3", task=c.T2I):
    return json.dumps({"expanded_caption": caption,
                       "aspect_ratio" if task == c.T2I else "target_aspect_ratio": ratio}, ensure_ascii=False)


def references(count=2):
    rows, parts = [], []
    for index in range(count):
        width, height = 301 + index * 2, 199 + index * 2
        import math
        divisor = math.gcd(width, height)
        label = f"<Picture {index + 1}>"
        rows.append({"label": label, "source_slot": index * 2, "width": width, "height": height,
                     "aspect_ratio": f"{width // divisor}:{height // divisor}"})
        parts.extend([{"type": "text", "text": f"The next attached image is {label}."},
                      {"type": "image_url", "image_url": {"url": f"data:image/png;base64,aW1hZ2U{index}"}}])
    return rows, parts


class H3ImageSourcesTests(unittest.TestCase):
    def test_all_raw_files_and_official_manifest_agree(self):
        source = c.sources()
        self.assertEqual(source["source_commit"], c.SOURCE_COMMIT)
        self.assertEqual(source["model_source_commit"], c.MODEL_SOURCE_COMMIT)
        official = json.loads((c.VENDOR / "prompt/manifest.json").read_bytes())
        for task in official.values():
            for name, info in task["files"].items():
                self.assertEqual(source["files"][name]["sha256"], info["sha256"])
                self.assertEqual(hashlib.sha256((c.VENDOR / name).read_bytes()).hexdigest(), info["sha256"])
        self.assertIn("Community License Agreement", (c.VENDOR / "NOTICE").read_text(encoding="utf-8"))

    def test_source_tamper_and_newline_conversion_rejected_at_use(self):
        for replacement in (b"changed", None):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as folder:
                target = Path(folder) / "vendor"
                shutil.copytree(c.VENDOR, target)
                file = target / "prompt/t2i/system_prompt.txt"
                data = file.read_bytes()
                file.write_bytes(data.replace(b"\n", b"\r\n") if replacement is None else replacement)
                with patch.object(c, "VENDOR", target), self.assertRaises(c.H3ImageContractError) as failure:
                    c.sources()
                self.assertEqual(failure.exception.code, "source_integrity")

    def test_import_does_not_read_source_or_require_vendor(self):
        spec = importlib.util.spec_from_file_location("h3_image_contract_import_test", ROOT / "h3_image_contract.py")
        module = importlib.util.module_from_spec(spec)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("eager source read")):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder, patch.object(c, "VENDOR", Path(folder)):
            with self.assertRaises(c.H3ImageContractError) as failure:
                c.sources()
            self.assertEqual(failure.exception.code, "source_unavailable")

    def test_manifest_tamper_cannot_authorize_changed_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "vendor"
            shutil.copytree(c.VENDOR, target)
            (target / "source.json").write_text("{}", encoding="utf-8")
            with patch.object(c, "VENDOR", target), self.assertRaises(c.H3ImageContractError) as failure:
                c.sources()
            self.assertEqual(failure.exception.code, "source_integrity")


class H3ImageMessagesTests(unittest.TestCase):
    def test_t2i_original_template_and_literal_braces_are_preserved(self):
        prompt = '海报标题“慢一点，刚刚好”，标签 {A} 和 "B"。'
        messages = c.build_messages(prompt, c.T2I, "4:3", 0, "慢一点，刚刚好", [])
        source = (c.VENDOR / "prompt/t2i/task_prompt.txt").read_bytes().decode("utf-8")
        self.assertTrue(messages[1]["content"].startswith(source.format(prompt)))
        self.assertEqual(messages[0]["content"], (c.VENDOR / "prompt/t2i/system_prompt.txt").read_bytes().decode("utf-8"))
        self.assertNotIn("approximately 0", messages[1]["content"])
        self.assertIn("4:3", messages[1]["content"])

    def test_edit_one_message_exact_prefix_and_all_pairs(self):
        for count in (1, 2, 16):
            with self.subTest(count=count):
                mapping, parts = references(count)
                before = copy.deepcopy(parts)
                messages = c.build_messages('只改图1，保留"x"\n下一项', c.EDIT, "auto", 1200, "SALE\r\nSALE", mapping, parts)
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0]["role"], "user")
                content = messages[0]["content"]
                self.assertEqual(content[0]["text"], (c.VENDOR / "prompt/edit/task_prompt.txt").read_bytes().decode("utf-8"))
                for index, row in enumerate(mapping):
                    self.assertEqual(content[2 + 2 * index]["text"], f"Reference Media:\n- {row['label']} [aspect_ratio {row['aspect_ratio']}]")
                    self.assertEqual(content[3 + 2 * index], parts[1 + 2 * index])
                self.assertIn("User Aspect Ratio Selection:\nadaptive", content[-1]["text"])
                self.assertIn('"只改图1，保留\\"x\\"\\n下一项"', content[-1]["text"])
                self.assertIn("approximately 1200", content[-1]["text"])
                self.assertEqual(parts, before)

    def test_edit_budget_messages_keep_all_metadata_without_image_parts(self):
        mapping, _ = references(16)
        content = c.build_messages("change", c.EDIT, "1001:999", 0, "", mapping)[0]["content"]
        self.assertTrue(all(item["type"] == "text" for item in content))
        self.assertEqual(sum(item["text"].startswith("Reference Media:") for item in content), 16)
        self.assertIn("1001:999", content[-1]["text"])

    def test_no_silent_mismatched_or_reordered_image_pairs(self):
        mapping, parts = references()
        mutations = [parts[:-1], parts[2:] + parts[:2], parts + parts[:2],
                     [parts[1], parts[0], *parts[2:]],
                     [{"type": "text", "text": "arbitrary label"}, *parts[1:]]]
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(c.H3ImageContractError) as failure:
                c.build_messages("change", c.EDIT, "auto", 0, "", mapping, changed)
            self.assertEqual(failure.exception.code, "media_pair_mismatch")

    def test_task_media_mismatch_is_rejected(self):
        mapping, parts = references()
        with self.assertRaises(c.H3ImageContractError) as failure:
            c.build_messages("brief", c.T2I, "auto", 0, "", mapping, parts)
        self.assertEqual(failure.exception.code, "unexpected_reference")
        with self.assertRaises(c.H3ImageContractError) as failure:
            c.build_messages("brief", c.EDIT, "auto", 0, "", [])
        self.assertEqual(failure.exception.code, "no_reference")

    def test_source_ratio_cannot_describe_resized_image(self):
        mapping, parts = references()
        mapping[0]["aspect_ratio"] = "1:1"
        with self.assertRaises(c.H3ImageContractError) as failure:
            c.build_messages("change", c.EDIT, "auto", 0, "", mapping, parts)
        self.assertEqual(failure.exception.code, "invalid_image_map")


class H3ImageParseTests(unittest.TestCase):
    def test_original_caption_space_quotes_unicode_and_tags_survive(self):
        caption = '  A sign reads \'慢一点，刚刚好\', "A", \'<think>keep</think>\' and \'<think>\', with \\n printed literally.  '
        for prefix, suffix in (("", ""), ("<think>private</think>\n", ""), ("```json\n", "\n```")):
            raw = prefix + result(caption) + suffix
            output, _, official, _ = c.parse_result(raw, c.T2I, locked_text="慢一点，刚刚好\n<think>keep</think>\n<think>")
            self.assertEqual(output, caption)
            self.assertEqual(json.loads(official)["expanded_caption"], caption)

    def test_reject_mixed_truncated_duplicate_nonstandard_and_wrong_fields(self):
        bad = ["explanation " + result(), result() + " explanation", result() + result(), result()[:-1],
               '{"expanded_caption":"A", "expanded_caption":"B", "aspect_ratio":"1:1"}',
               '{"expanded_caption":"A", "aspect_ratio":NaN}',
               '{"expanded_caption":"A", "aspect_ratio":"1:1", "extra":Infinity}',
               result().replace('"A white ceramic cup."', "null"), '[]',
               '{"expanded_caption":"A", "target_aspect_ratio":"1:1"}',
               result("")]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(c.H3ImageContractError):
                c.parse_result(raw, c.T2I)

    def test_actual_breaks_nul_and_lone_surrogates_rejected_but_literal_slash_n_valid(self):
        for char in ("\r", "\n", "\u0085", "\u2028", "\u2029", "\x00", "\ud800"):
            with self.subTest(char=repr(char)), self.assertRaises(c.H3ImageContractError):
                c.parse_result(result("Before" + char + "After"), c.T2I)
        self.assertEqual(c.parse_result(result("Before\\nAfter"), c.T2I)[0], "Before\\nAfter")

    def test_locked_text_order_repeats_and_whitespace_are_exact(self):
        c.parse_result(result("SALE then SALE."), c.T2I, locked_text="SALE\r\n\r\nSALE")
        cases = [("SALE", "SALE\nSALE"), ("B and A", "A\nB"), ("SALE", " SALE "), ("A B", "A\nB\nA")]
        for caption, locked in cases:
            with self.subTest(caption=caption, locked=locked), self.assertRaises(c.H3ImageContractError) as failure:
                c.parse_result(result(caption), c.T2I, locked_text=locked)
            self.assertTrue(failure.exception.code.startswith("missing_locked_line_"))

    def test_explicit_ratio_exact_and_task_specific(self):
        c.parse_result(result(ratio="1001:999", task=c.EDIT), c.EDIT, "1001:999")
        for raw, task, ratio in [(result(ratio="1001:999"), c.T2I, "auto"),
                                 (result(ratio="2:2", task=c.EDIT), c.EDIT, "1:1"),
                                 (result(ratio="4:3"), c.T2I, "16:9"),
                                 (result(ratio="0:1", task=c.EDIT), c.EDIT, "auto")]:
            with self.subTest(raw=raw), self.assertRaises(c.H3ImageContractError):
                c.parse_result(raw, task, ratio)

    def test_soft_target_counts_caption_only_and_does_not_pad_or_cut(self):
        caption = "A single white cup."
        output, _, _, details = c.parse_result(result(caption), c.T2I, target_words=20000)
        self.assertEqual(output, caption)
        self.assertEqual(details["caption_words"], 4)
        self.assertEqual(details["word_count_delta"], 4 - 20000)
        self.assertFalse(details["semantics_verified"])
        self.assertEqual(details["downstream_token_check"], "unverified")

    def test_subject_semantics_and_descriptive_language_are_not_regex_gates(self):
        caption = "新画面只显示文字 '<Picture 99>' 和 '<Subject 12>'。"
        self.assertEqual(c.parse_result(result(caption, task=c.EDIT), c.EDIT)[0], caption)

    def test_schema_uses_correct_key_and_explicit_ratio(self):
        for task, key in ((c.T2I, "aspect_ratio"), (c.EDIT, "target_aspect_ratio")):
            data = c.response_format(task, "4:3")["json_schema"]["schema"]
            self.assertEqual(set(data["required"]), {"expanded_caption", key})
            self.assertFalse(data["additionalProperties"])
            self.assertEqual(data["properties"][key]["enum"], ["4:3"])

    def test_invalid_controls_fail_without_coercion(self):
        for target in (-1, True, 0.5, "1000", c.MAX_TARGET_WORDS + 1):
            with self.subTest(target=target), self.assertRaises(c.H3ImageContractError):
                c.validate_controls(c.T2I, "auto", target, "", 1)
        c.validate_controls(c.T2I, "auto", c.MAX_TARGET_WORDS, "", 1)
        for ratio in ("adaptive", " 4:3", "4:3 ", "0:3", "4.5:3"):
            with self.subTest(ratio=ratio), self.assertRaises(c.H3ImageContractError):
                c.validate_controls(c.EDIT, ratio, 0, "", 0)


if __name__ == "__main__":
    unittest.main()
