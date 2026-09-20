import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("music_plan_contract_under_test", ROOT / "music_plan_contract.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class MusicPlanContractTests(unittest.TestCase):
    def test_versioned_lyric_plan_round_trip(self):
        plan = module.lyric_plan(
            idea="雨夜归途", language="中文", song_type="叙事型 / Narrative",
            to_whom="给未来的自己", moment="末班车", anchor="车窗雨痕",
            lyrics="[Verse]\n灯火穿过雨幕", structure="Verse → Chorus", source="inferred",
        )
        encoded = module.compact_json(plan)
        parsed = module.parse_plan(encoded, module.LYRIC_PLAN_SCHEMA)
        self.assertEqual(parsed["plan_id"], plan["plan_id"])
        self.assertEqual(parsed["lyrics"], "[Verse]\n灯火穿过雨幕")

    def test_wrong_schema_and_embedded_credential_are_rejected(self):
        with self.assertRaises(module.MusicPlanError):
            module.parse_plan('{"schema_version":"other/v1"}', module.LYRIC_PLAN_SCHEMA)
        fake_key = "sk" + "-" + "1234567890123456"
        leaked = {"schema_version": module.LYRIC_PLAN_SCHEMA, "lyrics": fake_key}
        with self.assertRaises(module.MusicPlanError):
            module.parse_plan(json.dumps(leaked), module.LYRIC_PLAN_SCHEMA)

    def test_text_limit_and_credential_guard(self):
        with self.assertRaises(module.MusicPlanError):
            module.clean_text("x" * 5, limit=4)
        with self.assertRaises(module.MusicPlanError):
            module.clean_text("do not paste " + "sk" + "-" + "1234567890123456 here")


if __name__ == "__main__":
    unittest.main()
