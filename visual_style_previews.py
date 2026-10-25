"""Finite display-only diagrams, pinned to generation resource bytes.

This module is never imported by a node/compiler and does not affect fingerprints.
Missing/stale illustrations must not prevent selecting the existing valid style.
"""
from pathlib import Path
try:
    from .visual_styles import _read, IDS, _SHA
except ImportError:
    from visual_styles import _read, IDS, _SHA

ROOT = Path(__file__).resolve().parent / 'resources/visual_style_previews'
DIAGRAMS = frozenset('sequence frame push perspective fixed negative track reflection wide symmetry '
                    'depth pov close lateral staging diagonal detail handheld hold overhead orbit low '
                    'cuts crane center outline layers parallel portrait occlusion attention flat gesture '
                    'gaze sound repeat eye_level beat zoom'.split())
LIGHTS = frozenset('localized rim top hard_side soft_side flat available diffuse'.split())


def illustration_payload(kind, resource, digest):
    """Called only after the existing resource validator has accepted the record."""
    if type(kind) is not str or kind not in {'color', 'creator'}:
        raise ValueError('Unknown illustration kind')
    data, _ = _read(ROOT / 'catalog.json', 128 * 1024)
    if (type(data) is not dict or set(data) != {'schema_version', 'revision', 'entries'}
            or data['schema_version'] != 't8-style-illustrations/v1' or data['revision'] != '1.0.0'
            or type(data['entries']) is not list or len(data['entries']) != 200):
        raise ValueError('Invalid illustration catalog')
    found, seen = None, set()
    for entry in data['entries']:
        if (type(entry) is not dict or set(entry) != {'id', 'color_sha256', 'creator_sha256', 'lighting', 'methods'}
                or type(entry['id']) is not str or entry['id'] not in IDS or entry['id'] in seen
                or any(type(entry[k]) is not str or not _SHA.fullmatch(entry[k]) for k in ('color_sha256', 'creator_sha256'))
                or type(entry['lighting']) is not str or entry['lighting'] not in LIGHTS
                or type(entry['methods']) is not list or len(entry['methods']) != 2
                or any(type(code) is not str or code not in DIAGRAMS for code in entry['methods'])):
            raise ValueError('Invalid illustration entry')
        seen.add(entry['id'])
        if entry['id'] == resource['id']:
            found = entry
    if not found or found[kind + '_sha256'] != digest:
        raise ValueError('Illustration resource revision mismatch')
    if kind == 'creator' and len(resource['methods']) != len(found['methods']):
        raise ValueError('Illustration method mismatch')
    return {'available': True, 'schema_version': data['schema_version'], 'revision': data['revision'],
            'kind': kind, 'id': resource['id'], 'resource_sha256': digest,
            'lighting': found['lighting'] if kind == 'color' else None,
            'methods': found['methods'] if kind == 'creator' else [], 'real_output': False}
