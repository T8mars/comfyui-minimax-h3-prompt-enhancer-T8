"""Standalone CPU editor; no sibling imports, models or external network."""
import asyncio
import base64
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from test_h3_visual_marker import h3, vm, media

editor=importlib.import_module(h3.__package__+'.h3_spatial_editor')
routes=importlib.import_module(h3.__package__+'.h3_spatial_editor_routes')
SPEC={'markers':[
    dict(marker_id='a',kind='actor',role_id='A',color='cyan',description='the person',xyxy=[.1,.1,.4,.9]),
    dict(marker_id='b',kind='target',color='yellow',description='the door',xyxy=[.65,.2,.95,.95])],
    'relations':[dict(actor_marker_id='a',target_marker_id='b',action='walk through and keep moving')]}


class SpatialEditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.folder=patch('folder_paths.get_input_directory',return_value=str(self.root));self.folder.start();self.addCleanup(self.folder.stop)
        Image.new('RGB',(48,32),(17,89,230)).save(self.root/'source.png')
        self.raw=json.dumps(SPEC)

    def test_source_node_and_adapter_without_audio(self):
        result=editor.T8H3SpatialMarkerCanvas.execute('source.png',markers_json=self.raw).result
        marked,plan,source,raw,report=result
        self.assertEqual(raw,self.raw);self.assertEqual(tuple(marked.shape),(1,32,48,3))
        self.assertEqual(len(vars(plan)),3)
        config=vm.build_visual_marker_config(vm.ON,0,plan)
        pixels,evidence=vm.bind_visual_marker(config,media(plan),'Ref2VA')
        self.assertEqual(evidence.picture,1)
        self.assertTrue(np.array_equal(pixels[0]['value'],marked[0].numpy()))
        self.assertFalse(json.loads(report)['semantic_verified'])
        self.assertEqual(json.loads(report)['model_calls'],0)
        self.assertTrue(np.array_equal(source.numpy(),editor.load_source('source.png')))
        self.assertFalse(np.shares_memory(source.numpy(),marked.numpy()))

    def test_exact_border_and_source_unchanged(self):
        source=editor.load_source('source.png');before=source.copy()
        marked,plan,record,_=editor.prepare_spatial_image(source,self.raw,line_width=2)
        self.assertTrue(np.array_equal(source,before))
        for marker,box in zip(record['spec']['markers'],record['pixel_rectangles']):
            l,t,r,b=box['source_pixel_xyxy'];expected=np.array([int(marker['color_rgb'][i:i+2],16)/255 for i in (1,3,5)],dtype=np.float32)
            self.assertTrue(np.array_equal(marked[0,t,l].numpy(),expected))
            self.assertTrue(np.array_equal(marked[0,b-1,r-1].numpy(),expected))
        self.assertTrue(np.array_equal(marked[0,12,10].numpy(),source[0,12,10]))
        vm._record(plan.record_json)

    def test_preview_pixel_parity_and_stale_binding(self):
        source=routes.preview_payload({'image':'source.png'})
        preview=routes.preview_payload(dict(image='source.png',mode='render_rectangles',markers_json=self.raw,line_width=3))
        self.assertEqual(source['source_sha256'],preview['source_sha256'])
        marked,*_=editor.prepare_spatial_image(editor.load_source('source.png'),self.raw,expected_source_sha256=source['source_sha256'])
        self.assertEqual(base64.b64decode(preview['png'].split(',')[1]),editor.image_png(marked))
        Image.new('RGB',(48,32),(31,89,230)).save(self.root/'source.png')
        with self.assertRaisesRegex(ValueError,'Source changed'):
            editor.T8H3SpatialMarkerCanvas.execute('source.png',markers_json=self.raw,expected_source_sha256=source['source_sha256'])

    def test_input_sandbox_and_bad_source(self):
        for name in ('../escape.png','sub/../../escape.png','/absolute.png','C:/file.png','\\\\server\\share.png','absent.png',''):
            with self.subTest(name=name),self.assertRaises(ValueError):editor.load_source(name)
        self.root.joinpath('bad.png').write_bytes(b'not-an-image')
        with self.assertRaises(ValueError):editor.load_source('bad.png')
        (self.root/'sub').mkdir();Image.new('RGB',(3,5)).save(self.root/'sub/valid.png')
        self.assertEqual(editor.load_source('sub/valid.png').shape,(1,5,3,3))
        Image.new('RGB',(2049,2048)).save(self.root/'huge.png')
        with self.assertRaisesRegex(ValueError,'4MP'):editor.load_source('huge.png')

    def test_handed_marked_never_repaints(self):
        spec=json.loads(self.raw)
        for marker in spec['markers']:marker.pop('xyxy')
        source=editor.load_source('source.png')
        marked,plan,record,codes=editor.prepare_spatial_image(source,json.dumps(spec),mode='provided_marked')
        self.assertTrue(np.array_equal(marked.numpy(),source));self.assertIsNone(plan.clean_image)
        self.assertIsNone(record['line_width']);self.assertIn('hand_drawn_unobserved',codes)

    def test_invalid_drafts_and_finite_bounds(self):
        bad=['{}','{"markers":[],"relations":[]}',self.raw.replace('"cyan"','"notacolor"'),self.raw.replace('0.1','NaN'),self.raw.replace('"actor_marker_id": "a"','"actor_marker_id": "missing"'),self.raw.replace('"markers":','"markers": [], "markers":',1)]
        for raw in bad:
            with self.subTest(raw=raw[:60]),self.assertRaises(ValueError):editor.prepare_spatial_image(editor.load_source('source.png'),raw)
        for stroke in (True,0,33,1.2):
            with self.assertRaises(ValueError):editor.prepare_spatial_image(editor.load_source('source.png'),self.raw,line_width=stroke)
        with self.assertRaises(ValueError):editor.prepare_spatial_image(editor.load_source('source.png'),self.raw,expected_source_sha256='wrong')

    def test_validation_defers_links_runtime_checks_and_fingerprints_content(self):
        cls=editor.T8H3SpatialMarkerCanvas
        self.assertIs(cls.validate_inputs(),True)
        self.assertIsNot(cls.validate_inputs(image='missing'),True)
        self.assertIsNot(cls.validate_inputs(markers_json=editor.EMPTY_SPEC),True)
        a=cls.fingerprint_inputs(image='source.png')
        Image.new('RGB',(48,32),(50,50,50)).save(self.root/'source.png')
        self.assertNotEqual(a,cls.fingerprint_inputs(image='source.png'))
        schema=cls.define_schema()
        self.assertEqual([x.id for x in schema.inputs],['image','mode','markers_json','line_width','expected_source_sha256'])
        self.assertTrue(schema.inputs[0].as_dict()['image_upload'])

    def test_prior_33_nodes_source_and_schemas_untouched(self):
        import subprocess, ast
        from visual_style_baseline_projection import project_style_ast
        from test_directional_skills import ROOT,GIT_ROOT
        # MOSS now has a separately audited opt-in authoring append; its prior
        # schema/request/bounded contracts are frozen in test_moss_authoring.
        for name in ('nodes.py','h3_visual_marker.py','seedance20.py','music3.py','yue2.py','qwen_image21.py','web/js/minimax_h3_prompt_enhancer.js'):
            old=subprocess.check_output(['git','show','25cc889b8d5d9edb9366995a6f0e5d09ceabae1f:'+name],cwd=GIT_ROOT)
            if name in ('nodes.py', 'seedance20.py'):
                self.assertEqual(ast.dump(project_style_ast((ROOT/name).read_text(encoding='utf-8'))), ast.dump(ast.parse(old)), name)
            else:
                self.assertEqual((ROOT/name).read_bytes().replace(b'\r\n',b'\n'),old.replace(b'\r\n',b'\n'),name)
        import sys
        nodes=asyncio.run(asyncio.run(sys.modules[h3.__package__].comfy_entrypoint()).get_node_list())
        self.assertEqual(len(nodes),38);self.assertEqual(nodes[32],vm.T8H3VisualMarkerConfig)
        self.assertEqual(nodes[33],editor.T8H3SpatialMarkerCanvas)
        self.assertEqual([n.define_schema().node_id for n in nodes[34:36]],['MOSSAuthoringDirectorT8','MOSSAuthoringPageT8'])


class PreviewRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_origin_body_limit_and_failure_are_bounded(self):
        import types
        from aiohttp import web
        from aiohttp.test_utils import TestClient,TestServer
        table=web.RouteTableDef();fake=types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=table)))
        with patch.dict('sys.modules',server=fake),patch.object(routes,'_REGISTERED',False):
            self.assertTrue(routes.register_spatial_editor_routes());self.assertTrue(routes.register_spatial_editor_routes())
        app=web.Application();app.add_routes(table)
        async with TestClient(TestServer(app)) as client:
            endpoint='/t8-prompt-enhancer/h3-spatial-editor/preview'
            response=await client.post(endpoint,json={'image':'secret'},headers={'Origin':'https://evil.invalid'})
            self.assertEqual(response.status,403)
            response=await client.post(endpoint,data=b'x'*(routes.MAX_BODY+1))
            self.assertEqual(response.status,413)
            response=await client.post(endpoint,json={'image':'../secret'})
            self.assertEqual(response.status,400);self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertNotIn('secret',await response.text())


if __name__=='__main__':unittest.main()
