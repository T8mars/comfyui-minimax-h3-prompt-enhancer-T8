"""Display-only coverage and trust boundary; no image or model inference."""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_directional_skills import h3

styles = importlib.import_module(h3.__package__ + '.visual_styles')
previews = importlib.import_module(h3.__package__ + '.visual_style_previews')
routes = importlib.import_module(h3.__package__ + '.visual_style_routes')
ROOT = Path(__file__).resolve().parents[1]


class VisualStylePreviewTests(unittest.TestCase):
    def test_all_400_previews_match_packaged_resources_and_are_not_outputs(self):
        counts = set()
        for number in range(1, 201):
            for kind in ('color', 'creator'):
                resource, _, digest = styles.load_resource(kind, f'{number:03d}')
                result = previews.illustration_payload(kind, resource, digest)
                self.assertTrue(result['available'])
                self.assertFalse(result['real_output'])
                self.assertEqual(result['resource_sha256'], digest)
                self.assertEqual(result['id'], resource['id'])
                if kind == 'creator':
                    self.assertEqual(len(result['methods']), len(resource['methods']))
                    counts.update(result['methods'])
                else:
                    self.assertIn(result['lighting'], previews.LIGHTS)
        self.assertEqual(counts, previews.DIAGRAMS)

    def test_reproducible_preview_manifest_without_original_pack(self):
        completed = subprocess.run([sys.executable, str(ROOT / 'tools/build_visual_style_previews.py'), '--check'],
                                   capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_bad_preview_manifest_is_bounded_and_does_not_block_style_selection(self):
        original = json.loads((previews.ROOT / 'catalog.json').read_text(encoding='utf-8'))
        variants = []
        for key, value in [('id', []), ('lighting', []), ('methods', ['bogus', 'push']),
                           ('methods', ['push']), ('methods', [[], 'push']), ('creator_sha256', '0' * 64)]:
            data = copy.deepcopy(original); data['entries'][0][key] = value; variants.append(data)
        data = copy.deepcopy(original); data['entries'][1] = data['entries'][0]; variants.append(data)
        data = copy.deepcopy(original); data['revision'] = '2.0.0'; variants.append(data)
        variants.extend([[], {'entries': []}])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for data in variants:
                with self.subTest(data=str(data)[:90]):
                    (path / 'catalog.json').write_text(json.dumps(data), encoding='utf-8')
                    with patch.object(previews, 'ROOT', path):
                        detail = routes.detail_payload('creator', '001')
                        self.assertFalse(detail['illustration']['available'])
                        self.assertEqual(detail['resource']['id'], '001')
                        self.assertEqual(detail['model_calls'], 0)
            (path / 'catalog.json').unlink()
            with patch.object(previews, 'ROOT', path):
                self.assertFalse(routes.detail_payload('color', '001')['illustration']['available'])

    def test_viewing_preview_never_changes_config_fingerprint_or_prompt_resource(self):
        for kind in ('color', 'creator'):
            before = styles.build_style_config(kind, styles.ON, '022')
            fingerprint = styles.helper_fingerprint(kind, styles.ON, '022')
            raw = (styles.ROOT / ('colors' if kind == 'color' else 'creators') / '022.json').read_bytes()
            result = routes.detail_payload(kind, '022')
            self.assertTrue(result['illustration']['available'])
            self.assertEqual(before, styles.build_style_config(kind, styles.ON, '022'))
            self.assertEqual(fingerprint, styles.helper_fingerprint(kind, styles.ON, '022'))
            self.assertEqual(raw, (styles.ROOT / ('colors' if kind == 'color' else 'creators') / '022.json').read_bytes())

    def test_curated_mapping_and_light_family_representative_semantics(self):
        expected = {'001': ['sequence', 'frame'], '022': ['reflection', 'lateral'],
                    '038': ['wide', 'parallel'], '155': ['push', 'handheld'],
                    '181': ['low', 'negative'], '189': ['zoom', 'repeat']}
        for ident, codes in expected.items():
            self.assertEqual(routes.detail_payload('creator', ident)['illustration']['methods'], codes)
        self.assertEqual(routes.detail_payload('color', '022')['illustration']['lighting'], 'localized')
        self.assertEqual(routes.detail_payload('color', '001')['illustration']['lighting'], 'hard_side')
        # Material hardness and conditional color permission do not describe lighting.
        for ident, family in {'003': 'diffuse', '015': 'available', '031': 'soft_side', '092': 'soft_side'}.items():
            self.assertEqual(routes.detail_payload('color', ident)['illustration']['lighting'], family)


if __name__ == '__main__':
    unittest.main()
