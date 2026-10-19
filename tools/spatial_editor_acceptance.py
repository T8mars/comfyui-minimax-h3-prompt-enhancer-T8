"""Owned CPU-only Comfy, standalone editor in real Chromium, fake loopback LLM."""
import argparse
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

from marker_queue_acceptance import ROOT,DRAFT,RULE,EVIDENCE


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--browser',type=Path,required=True)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out==ROOT or ROOT in out.parents:parser.error('Evidence must be outside this repository')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('user','input','output','temp'):(out/name).mkdir()
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(1440,960),(233,227,214));draw=ImageDraw.Draw(image)
    draw.rectangle([0,840,1440,960],fill=(194,174,145));draw.rectangle([990,195,1335,840],fill=(50,68,79))
    draw.ellipse([306,150,444,288],fill=(223,177,140));draw.polygon([(300,315),(450,315),(492,654),(255,654)],fill=(185,56,49))
    draw.line([(333,654),(324,813)],fill=(53,65,78),width=39);draw.line([(420,654),(444,813)],fill=(53,65,78),width=39)
    image.save(out/'input/h3-marker-demo-source.png')
    calls=[]
    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':DRAFT}}]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    provider=http.server.ThreadingHTTPServer(('127.0.0.1',0),Provider);provider.daemon_threads=True
    thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    command=[sys.executable,'main.py','--cpu','--listen','127.0.0.1','--port',str(port),'--disable-auto-launch','--disable-all-custom-nodes','--whitelist-custom-nodes',ROOT.name]
    for name in ('user','input','output','temp'):command.extend(['--'+name+'-directory',str(out/name)])
    import requests
    session=requests.Session();session.trust_env=False;process=None
    try:
        with (out/'server.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen(command,cwd=ROOT.parents[1],stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','STRATA_API_KEY':''})
            until=time.monotonic()+120
            while time.monotonic()<until:
                if process.poll() is not None:raise RuntimeError('Owned host exited; inspect server.log')
                try:
                    response=session.get(base+'/object_info',timeout=2)
                    if response.ok:info=response.json();break
                except requests.RequestException:pass
                time.sleep(.25)
            else:raise TimeoutError('Owned host not ready')
            assert 'T8H3SpatialMarkerCanvas' in info
            assert 'MiniMaxH3VisualMarkerPrepareEXPT8' not in info,'No audio or fixture producer may be loaded'
            (out/'object-info.json').write_text(json.dumps(info,ensure_ascii=False),encoding='utf-8')
            result=subprocess.run(['node',str(ROOT/'tools/frontend_browser_cdp.mjs'),str(args.browser),base,str(out/'native-ui.png'),'comfy-spatial',f'http://127.0.0.1:{provider.server_port}/v1'],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=150)
            (out/'native-ui.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            assert result.returncode==0,result.stderr
            assert len(calls)==5,'Manual graph plus four explicit Off/On sample queues, no editor inference'
            messages=calls[0]['messages'];texts='\n'.join(p['text'] for p in messages[1]['content'] if p['type']=='text')
            assert RULE in messages[0]['content'] and texts.count(EVIDENCE)==1 and '"picture":"<Picture 2>"' in texts
            assert sum(p['type']=='image_url' for p in messages[1]['content'])==2
            for call,(active,ordinal,count) in zip(calls[1:],[(False,1,1),(True,1,1),(False,2,2),(True,2,2)]):
                messages=call['messages'];texts='\n'.join(p['text'] for p in messages[1]['content'] if p['type']=='text')
                assert (RULE in messages[0]['content'])==active and texts.count(EVIDENCE)==int(active)
                if active:assert f'"picture":"<Picture {ordinal}>"' in texts
                assert sum(p['type']=='image_url' for p in messages[1]['content'])==count
            (out/'loopback-requests.json').write_text(json.dumps(calls,ensure_ascii=False),encoding='utf-8')
            evidence=dict(passed=True,real_cpu_comfy=True,real_chromium=True,no_audio_plugin=True,model_inference=False,provider_calls=5,standalone_sample_queues=4)
            (out/'evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8');print(json.dumps(evidence))
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
        provider.shutdown();provider.server_close();thread.join(2);session.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
