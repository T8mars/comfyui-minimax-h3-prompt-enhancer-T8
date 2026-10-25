"""Finite wording regressions from the second visual-style cross-review.

These tests check explicit non-addition wording, not actual model compliance.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NON_ADDITIONS = {
    "112": [
        "ritual symbols"
    ],
    "114": [
        "installations"
    ],
    "115": [
        "grotesque characters"
    ],
    "116": [
        "medical equipment"
    ],
    "117": [
        "dreams or time loops"
    ],
    "118": [
        "metaphorical events"
    ],
    "120": [
        "political symbols"
    ],
    "121": [
        "landmarks or destruction"
    ],
    "125": [
        "mythic characters or scenery"
    ],
    "128": [
        "time-travel events"
    ],
    "131": [
        "jokes or dialogue"
    ],
    "132": [
        "street conflict"
    ],
    "133": [
        "explosions or equipment",
        "explosive light sources"
    ],
    "136": [
        "equipment or spy identities"
    ],
    "137": [
        "exotic decoration"
    ],
    "138": [
        "horror events"
    ],
    "139": [
        "social identities",
        "class conflict"
    ],
    "140": [
        "dramatic turns"
    ],
    "141": [
        "dream layers"
    ],
    "146": [
        "Gothic architecture"
    ],
    "149": [
        "cultural patterns"
    ],
    "151": [
        "fantasy characters"
    ],
    "154": [
        "family identities"
    ],
    "156": [
        "heroes or universes"
    ],
    "158": [
        "fairy-tale objects"
    ],
    "160": [
        "family or network plots"
    ],
    "165": [
        "identity plots"
    ],
    "166": [
        "period props"
    ],
    "167": [
        "ghosts"
    ],
    "173": [
        "life-changing events"
    ],
    "181": [
        "tea bowls or family relationships"
    ],
    "183": [
        "ghosts"
    ],
    "188": [
        "dialogue or rituals",
        "islands or temples"
    ],
    "190": [
        "supernatural events"
    ],
    "193": [
        "a coming-of-age plot"
    ],
    "195": [
        "secrets"
    ],
    "196": [
        "political symbols or regional settings"
    ],
    "197": [
        "border conflict or music"
    ],
    "198": [
        "political events",
        "social identities"
    ],
    "199": [
        "historical events"
    ],
    "040": [
        "tactical overlays"
    ],
    "073": [
        "period props"
    ],
    "086": [
        "ritual props"
    ],
    "091": [
        "genre events"
    ],
    "096": [
        "operatic identity"
    ],
    "099": [
        "plot turns"
    ]
}


class VisualStyleReleaseReview(unittest.TestCase):
    def test_english_non_addition_clauses_do_not_prohibit_existing_facts(self):
        rows = {}
        for line in (ROOT / "resources/visual_styles/curation.tsv").read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split("|")
            rows[fields[0]] = fields
        for ident, phrases in EXPECTED_NON_ADDITIONS.items():
            fields = rows[ident]
            curated_english = [fields[3], fields[6], fields[8]]
            color = json.loads((ROOT / f"resources/visual_styles/colors/{ident}.json").read_text(encoding="utf-8"))
            creator = json.loads((ROOT / f"resources/visual_styles/creators/{ident}.json").read_text(encoding="utf-8"))
            packaged_english = [m["text_en"] for m in creator["methods"]] + [color["lighting_notes"]["en"]]
            for phrase in phrases:
                with self.subTest(ident=ident, phrase=phrase):
                    expected = "without adding " + phrase + "."
                    old = "without " + phrase + "."
                    self.assertTrue(any(expected in value for value in curated_english))
                    self.assertTrue(any(expected in value for value in packaged_english))
                    self.assertFalse(any(old in value for value in packaged_english))

    def test_mixed_conversion_and_addition_clauses_remain_explicit(self):
        for ident, expected in (
            ("122", "without automatic slow motion or added weapons."),
            ("156", "without forcing comic conversion or adding split screens."),
        ):
            value = json.loads((ROOT / f"resources/visual_styles/creators/{ident}.json").read_text(encoding="utf-8"))
            self.assertTrue(any(expected in method["text_en"] for method in value["methods"]))


if __name__ == "__main__":
    unittest.main()
