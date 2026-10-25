"""Owned CPU Comfy and native Chromium; synthetic loopback responses, no inference."""
from __future__ import annotations
import argparse
import copy
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--browser', required=True, type=Path)
    args = parser.parse_args(); out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents: parser.error('Use a new external evidence directory')
    out.mkdir(parents=True, exist_ok=False)
    for name in ('user', 'input', 'output', 'temp'): (out / name).mkdir()
    config = out / 'test-paths.yaml'
    config.write_text('visual_test:\n  custom_nodes: ' + json.dumps(str(ROOT / 'tests/fixtures')) + '\n', encoding='utf-8')
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_strata_provider import status
    from test_directional_skills import native_draft
    import requests
    calls, observations = [], []

    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def answer(self, data):
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            self.answer({'data': [{'id': 'model-test'}]} if self.path == '/v1/models' else status())
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length']))); calls.append(payload)
            text = json.dumps(payload['messages'], ensure_ascii=False)
            reply = native_draft() if 'QUEUE_H3' in text else 'Shot 1: The woman retains the red sleeve and ticket and continues walking in the station.'
            self.answer({'model': 'model-test', 'choices': [{'finish_reason': 'stop', 'message': {'content': reply}}]})

    provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider); provider.daemon_threads = True
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'; provider_base = f'http://127.0.0.1:{provider.server_port}'
    cmd = [sys.executable, 'main.py', '--cpu', '--listen', '127.0.0.1', '--port', str(port), '--disable-auto-launch',
           '--disable-all-custom-nodes', '--whitelist-custom-nodes', ROOT.name, 'visual_style_runtime', '--extra-model-paths-config', str(config)]
    for name in ('user', 'input', 'output', 'temp'): cmd.extend(['--' + name + '-directory', str(out / name)])
    session = requests.Session(); session.trust_env = False; process = None
    def record():
        (out / 'evidence.json').write_text(json.dumps({'owned_cpu_queue': True, 'real_inference': False,
            'pid': process.pid if process else None, 'server_exited': process.poll() is not None if process else None,
            'port': port, 'provider_calls': len(calls), 'tests': observations}, indent=2), encoding='utf-8')
    try:
        with (out / 'server.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(cmd, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), env={**os.environ, 'STRATA_API_KEY': ''})
            until = time.monotonic() + 120
            while time.monotonic() < until:
                if process.poll() is not None: raise RuntimeError('Owned host exited; inspect log')
                try:
                    response = session.get(base + '/object_info', timeout=2)
                    if response.ok: info = response.json(); break
                except requests.RequestException: pass
                time.sleep(.2)
            else: raise TimeoutError('Owned host not ready')
            assert 'T8VisualStyleRuntimeFixture' in info
            (out / 'object-info.json').write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
            def defaults(name):
                return {k: v[1].get('default', v[0][0] if isinstance(v[0], list) else None) for k, v in info[name]['input']['required'].items()}
            def queue(label, graph, error=None):
                response = session.post(base + '/prompt', json={'prompt': graph}, timeout=10)
                assert response.ok, (label, response.text[:2000])
                pid = response.json()['prompt_id']; until = time.monotonic() + 45
                while time.monotonic() < until:
                    history = session.get(base + '/history/' + pid, timeout=3).json().get(pid)
                    if history: break
                    time.sleep(.1)
                else: raise TimeoutError('Unknown queue outcome, do not resubmit')
                (out / (label + '.json')).write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')
                assert history['status']['status_str'] == ('error' if error else 'success'), history['status']
                if error: assert error in json.dumps(history['status'])
                observations.append({'id': label, 'passed': True, 'expected_error': bool(error)})
                record(); print(json.dumps(observations[-1]), flush=True)
                return history
            configs = {}
            for kind, cls, field in (('color', 'T8ColorStyleConfig', 'palette'), ('creator', 'T8CreatorStyleConfig', 'creator')):
                v = defaults(cls); v['mode'] = '开启 / On'; v[field] = (info[cls]['input']['required'][field][1].get('options') or info[cls]['input']['required'][field][0])[1]
                configs[kind] = {'class_type': cls, 'inputs': v}
            shared = defaults('T8LLMProviderConfig'); shared.update(provider='Strata', strata_url=provider_base)
            for tag, cls in (('H3', 'MiniMaxH3PromptEnhancerT8'), ('SD', 'Seedance20PromptEnhancerT8')):
                values = defaults(cls); values.update(prompt='QUEUE_' + tag + ': woman walks holding ticket, keep red sleeve.',
                    output_language='English', duration_seconds=3600 if tag == 'H3' else '3600', shot_count='1',
                    provider_config=['9', 0], recovery_slot=str(uuid.uuid4()))
                graph = {'2': {'class_type': cls, 'inputs': values}, '3': {'class_type': 'T8ShowText', 'inputs': {'text': ['2', 0]}},
                         '9': {'class_type': 'T8LLMProviderConfig', 'inputs': shared}}
                for index, (color, creator) in enumerate(((False, False), (True, False), (False, True), (True, True))):
                    g = copy.deepcopy(graph); g['2']['inputs']['seed'] = index
                    for on, kind, nid in ((color, 'color', '4'), (creator, 'creator', '5')):
                        if on: g[nid] = copy.deepcopy(configs[kind]); g['2']['inputs'][kind + '_style_config'] = [nid, 0]
                    count = len(calls); queue(f'{tag}-arm-{index}', g); assert len(calls) == count + 1
                    rule = calls[-1]['messages'][0]['content']; assert rule.count('T8 OPTIONAL VISUAL PRESENTATION') == int(color or creator)
                    assert ('COLOR REFERENCE' in rule) == color and ('CREATOR PRESENTATION ONLY' in rule) == creator
                    assert '3600' in str(calls[-1])
                # Real V3 helper cache and consumer-only external typed producer.
                count = len(calls); original = queue(tag + '-cache-helper', g); assert len(calls) == count
                session.post(base + '/t8-test-visual-style/revision', timeout=3).raise_for_status()
                queue(tag + '-helper-fingerprint-change', g); assert len(calls) == count + 1
                g['4'] = {'class_type': 'T8VisualStyleRuntimeFixture', 'inputs': {'mode': 'valid'}}
                g.pop('5'); g['2']['inputs']['creator_style_config'] = ['4', 1]
                queue(tag + '-external-typed', g); count = len(calls)
                queue(tag + '-external-cache', g); assert len(calls) == count
                session.post(base + '/t8-test-visual-style/revision', timeout=3).raise_for_status()
                queue(tag + '-external-consumer-fingerprint-change', g); assert len(calls) == count + 1
                g['4']['inputs']['mode'] = 'poison'; g['2']['inputs']['recovery_action'] = 'restore_last'; count = len(calls)
                restored = queue(tag + '-restore-skips-poison', g)
                assert restored['outputs']['3']['text'] == original['outputs']['3']['text'] and len(calls) == count
                g['2']['inputs']['recovery_action'] = 'normal'; g['4']['inputs']['mode'] = 'bad'
                queue(tag + '-bad-config', g, 'Invalid visual style resource or config'); assert len(calls) == count
                g['2']['inputs']['recovery_action'] = 'restore_last'
                queue(tag + '-preserved-checkpoint', g); assert len(calls) == count
            for path in ('catalog', 'color/001', 'creator/181'):
                result = session.get(base + '/t8-prompt-enhancer/visual-styles/' + path, timeout=3); assert result.ok
            assert session.get(base + '/t8-prompt-enhancer/visual-styles/color/999', timeout=3).status_code == 400
            assert session.get(base + '/t8-prompt-enhancer/visual-styles/catalog', headers={'Origin': 'https://example.invalid'}, timeout=3).status_code == 403
            result = subprocess.run(['node', str(ROOT / 'tools/frontend_browser_cdp.mjs'), str(args.browser), base,
                str(out / 'native.png'), 'comfy-visual-styles', provider_base], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=150)
            (out / 'browser.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            assert result.returncode == 0, result.stdout + result.stderr
            observations.append({'id': 'native-browser', 'passed': True}); record()
            (out / 'provider-requests.json').write_text(json.dumps(calls, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        provider.shutdown(); provider.server_close(); session.close()
        record()
    print('PASS owned CPU queues and native browser; synthetic provider only', flush=True)


if __name__ == '__main__': main()
