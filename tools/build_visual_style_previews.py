"""Build display-only diagram identities; never change generation resources."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from visual_style_previews import DIAGRAMS, LIGHTS

PREVIEWS = ROOT / 'resources/visual_style_previews'


def lighting_family(text):
    # Illustrate one explicitly stated family, not a new exact lighting recipe.
    # Match lighting phrases, not substrings such as "另有色彩授权" or "硬表面".
    if any(term in text for term in ('色光', '有色主光', '冷暖光源')):
        return 'localized'
    if any(term in text for term in ('背光', '逆光', '侧背')):
        return 'rim'
    if any(term in text for term in ('顶部', '顶面')):
        return 'top'
    if '选择软光或硬光' in text:
        return 'available'  # Context chooses the light; this scene cannot choose for it.
    if '方向弱' in text and '漫射' in text:
        return 'diffuse'
    if any(term in text for term in ('硬光', '硬侧光', '硬主光', '硬定向光', '硬阴影', '硬边', '软硬过渡',
                                     '强亮暗', '较强', '戏剧性', '深阴影', '低调', '清晰阴影边缘', '明确阴影形状')):
        return 'hard_side'
    if any(term in text for term in ('侧光', '侧向', '柔侧', '窗光', '方向', '定向')):
        return 'soft_side'
    if '平光' in text:
        return 'flat'
    if any(term in text for term in ('已有', '现有', '自然可用', '纪实')):
        return 'available'
    if any(term in text for term in ('柔', '漫', '散', '阴天')):
        return 'diffuse'
    return 'available'


def generate():
    with (PREVIEWS / 'creator_diagrams.tsv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    assert [row['id'] for row in rows] == [f'{n:03d}' for n in range(1, 201)]
    entries = []
    for row in rows:
        ident = row['id']
        paths = [ROOT / f'resources/visual_styles/{kind}/{ident}.json' for kind in ('colors', 'creators')]
        color, creator = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
        codes = [row['method_1'], row['method_2']]
        assert len(creator['methods']) == len(codes) and all(code in DIAGRAMS for code in codes)
        family = lighting_family(color['lighting_notes']['zh'])
        assert family in LIGHTS
        entries.append({'id': ident, 'color_sha256': hashlib.sha256(paths[0].read_bytes()).hexdigest(),
                        'creator_sha256': hashlib.sha256(paths[1].read_bytes()).hexdigest(),
                        'lighting': family, 'methods': codes})
    return {'schema_version': 't8-style-illustrations/v1', 'revision': '1.0.0', 'entries': entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = PREVIEWS / 'catalog.json'
    raw = (json.dumps(generate(), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if args.check:
        assert target.read_bytes() == raw, 'Preview manifest differs from reviewed mappings/resources'
    else:
        target.write_bytes(raw)
    print('Visual illustrations: 200 color + 200 creator, 400 method mappings; no model or source-pack access.')


if __name__ == '__main__':
    main()
