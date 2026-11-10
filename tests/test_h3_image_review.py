"""Independent cross-review regressions for queue/save lifecycle boundaries."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from test_moss_image import moss

ROOT = Path(__file__).resolve().parents[1]
h = importlib.import_module(moss.__package__ + ".h3_image")


class H3ImageCrossReviewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend lifecycle regression")
    def test_restore_action_is_transient_but_live_queue_action_is_preserved(self):
        script = r"""
import fs from 'node:fs';
import {configure, serialize, NAMES} from './web/js/h3_image_ui.mjs';
const wf=JSON.parse(fs.readFileSync('./example_workflows/h3_image_t2i_example.json','utf8'));
const saved=wf.nodes.find(n=>n.type==='MiniMaxH3ImagePromptEnhancerT8');
const mk=()=>({widgets:NAMES.map((name,i)=>({name,value:saved.widgets_values[i]})),properties:{},inputs:[]});
const active=mk(); active.widgets.find(w=>w.name==='recovery_action').value='restore_last';
const data={}; serialize(active,data);
const fresh=mk(); configure(fresh,data,undefined,[]);
console.log(JSON.stringify({saved:data.widgets_values_named.recovery_action,
 loaded:fresh.widgets.find(w=>w.name==='recovery_action').value,
 live:active.widgets.find(w=>w.name==='recovery_action').value}));
"""
        run = subprocess.run([shutil.which("node"), "--input-type=module", "-"], input=script, text=True,
                             encoding="utf-8", cwd=ROOT, capture_output=True, check=True)
        values = json.loads(run.stdout)
        self.assertEqual(values, {"saved": "normal", "loaded": "normal", "live": "restore_last"})

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend lifecycle regression")
    def test_clone_configured_before_graph_gets_unique_recovery_slot_at_queue(self):
        script = r"""
import fs from 'node:fs';
import {configure, serialize, NAMES} from './web/js/h3_image_ui.mjs';
import {ensureUniqueSlot, RECOVERY_SLOT_PROPERTY} from './web/js/completion_recovery_core.mjs';
const wf=JSON.parse(fs.readFileSync('./example_workflows/h3_image_t2i_example.json','utf8'));
const saved=wf.nodes.find(n=>n.type==='MiniMaxH3ImagePromptEnhancerT8');
const mk=()=>({widgets:NAMES.map((name,i)=>({name,value:saved.widgets_values[i]})),properties:{},inputs:[]});
const original=mk(); original.widgets.find(w=>w.name==='recovery_slot').value='t8-test-clone-slot';
original.properties[RECOVERY_SLOT_PROPERTY]='t8-test-clone-slot';
const data={}; serialize(original,data);
const clone=mk(); clone.t8EnsureRecoverySlot=()=>ensureUniqueSlot(clone,clone.widgets.find(w=>w.name==='recovery_slot'));
configure(clone,data,function(value){this.properties={...value.properties};},[]);
const graph={_nodes:[original,clone]}; original.graph=graph; clone.graph=graph;
const queued={}; serialize(clone,queued);
console.log(JSON.stringify({original:original.widgets.find(w=>w.name==='recovery_slot').value,
 clone:queued.widgets_values_named.recovery_slot, property:queued.properties[RECOVERY_SLOT_PROPERTY]}));
"""
        run = subprocess.run([shutil.which("node"), "--input-type=module", "-"], input=script, text=True,
                             encoding="utf-8", cwd=ROOT, capture_output=True, check=True)
        values = json.loads(run.stdout)
        self.assertNotEqual(values["original"], values["clone"])
        self.assertEqual(values["property"], values["clone"])

    def test_explicit_cloud_token_budget_rejects_nonpositive_or_noninteger_before_upload(self):
        config_module = importlib.import_module(h.__package__ + ".provider_config")
        config = config_module.build_provider_config(provider="OpenAI Compatible",
            openai_base_url="http://127.0.0.1:12345/v1", custom_model="review-test")
        for key in ("max_tokens", "max_completion_tokens"):
            for value in (True, False, 0, -1, 123.5, "2048", None):
                with self.subTest(key=key, value=value):
                    candidate = copy.deepcopy(config)
                    candidate["provider_request_options"]["extra_parameters"][key] = value
                    with patch.object(h, "_generate") as generate, self.assertRaises(h.H3ImageError):
                        h.MiniMaxH3ImagePromptEnhancer.execute(prompt="A cup.", api_key="test-placeholder", provider_config=candidate)
                    generate.assert_not_called()

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend lifecycle regression")
    def test_recovery_slots_are_unique_across_root_and_both_subgraph_representations(self):
        script = r"""
import {ensureAcrossGraphs} from './web/js/h3_image_ui.mjs';
import {RECOVERY_SLOT_PROPERTY} from './web/js/completion_recovery_core.mjs';
const make=slot=>({widgets:[{name:'recovery_slot',value:slot}],properties:{[RECOVERY_SLOT_PROPERTY]:slot}});
const rows=[];
for(const kind of ['map','container']) {
 const original=make('t8-cross-graph-clone'), clone=make('t8-cross-graph-clone');
 const child={_nodes:[clone]}, root={_nodes:[original]};
 if(kind==='map') {root.subgraphs=new Map([['child',child]]); child.subgraphs=new Map([['cycle',root]]);}
 else {root._nodes.push({subgraph:child});child._nodes.push({subgraph:root});}
 original.graph=root;clone.graph=child;
 ensureAcrossGraphs(clone,root);
 const first=clone.widgets[0].value;
 ensureAcrossGraphs(clone,root);
 const unrelated=make('t8-cross-graph-clone');unrelated.graph={_nodes:[unrelated]};
 ensureAcrossGraphs(unrelated,root);
 rows.push({kind,original:original.widgets[0].value,first,again:clone.widgets[0].value,
  property:clone.properties[RECOVERY_SLOT_PROPERTY],unrelated:unrelated.widgets[0].value});
}
console.log(JSON.stringify(rows));
"""
        run = subprocess.run([shutil.which("node"), "--input-type=module", "-"], input=script, text=True,
                             encoding="utf-8", cwd=ROOT, capture_output=True, check=True, timeout=10)
        for row in json.loads(run.stdout):
            with self.subTest(kind=row["kind"]):
                self.assertEqual(row["original"], "t8-cross-graph-clone")
                self.assertNotEqual(row["first"], row["original"])
                self.assertEqual(row["again"], row["first"])
                self.assertEqual(row["property"], row["first"])
                self.assertEqual(row["unrelated"], "t8-cross-graph-clone")


if __name__ == "__main__":
    unittest.main()
