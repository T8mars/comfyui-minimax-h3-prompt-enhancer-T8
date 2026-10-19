"""Own a CPU-only Comfy host and exercise native text preview restoration in Chrome."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--browser', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out == ROOT or ROOT in out.parents:
        parser.error('Evidence must be outside this repository')
    out.mkdir(parents=True, exist_ok=False)
    for name in ('user', 'input', 'output', 'temp'):
        (out / name).mkdir()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    command = [sys.executable, 'main.py', '--cpu', '--listen', '127.0.0.1', '--port', str(port),
               '--disable-auto-launch', '--disable-all-custom-nodes', '--whitelist-custom-nodes', ROOT.name]
    for name in ('user', 'input', 'output', 'temp'):
        command.extend(['--' + name + '-directory', str(out / name)])
    import requests
    session = requests.Session()
    session.trust_env = False
    process = None
    try:
        with (out / 'server.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=ROOT.parents[1], stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            until = time.monotonic() + 120
            while time.monotonic() < until:
                if process.poll() is not None:
                    raise RuntimeError('Owned host exited; inspect server.log')
                try:
                    if session.get(base + '/object_info', timeout=2).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.25)
            else:
                raise TimeoutError('Owned host not ready')
            result = subprocess.run(['node', str(ROOT / 'tools/frontend_browser_cdp.mjs'), str(args.browser),
                                     base, str(out / 'native-ui.png'), 'comfy-text'], cwd=ROOT,
                                    capture_output=True, text=True, encoding='utf-8', timeout=150)
            (out / 'native-ui.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            assert result.returncode == 0, result.stderr
            history = session.get(base + '/history', timeout=5).json()
            assert len(history) == 1, 'Only the two CPU STRING nodes execute, once'
            item = next(iter(history.values()))
            assert item['status']['status_str'] == 'success'
            classes = {node['class_type'] for node in item['prompt'][2].values()}
            assert classes == {'T8PromptText', 'T8ShowText'}, classes
            evidence = dict(passed=True, real_cpu_comfy=True, real_chromium=True, native_queue_count=1,
                            model_inference=False, paid_calls=0)
            (out / 'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            print(json.dumps(evidence))
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        session.close()


if __name__ == '__main__':
    main()
