"""Freeze the original provider config and exercise opt-in dispatch boundaries."""
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
GIT_ROOT=Path(os.environ.get("T8_SOURCE_GIT_ROOT",ROOT)).resolve()
BASELINE="4e6a8c4933ae42800e5e023fad6da182df1a72e4"
sys.path.insert(0,str(ROOT.parents[1]));sys.path.insert(0,str(ROOT))
import comfy.cli_args
comfy.cli_args.args.cpu=True
import provider_config as config
import strata_provider as sp
from strata_baseline_projection import project_strata_guard
from test_strata_provider import http_fixture

class StrataIntegrationTests(unittest.TestCase):
    def test_old_config_functions_and_schema_prefix_remain_frozen(self):
        old=ast.parse(subprocess.check_output(["git","show",BASELINE+":provider_config.py"],cwd=GIT_ROOT).decode("utf-8"))
        current=ast.parse((ROOT/"provider_config.py").read_text(encoding="utf-8"))
        for name in ("build_provider_config","merge_provider_config"):
            previous=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
            actual=next(n for n in current.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(project_strata_guard(actual)),ast.dump(previous))
        def schema(tree):
            cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="T8LLMProviderConfig")
            return copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="define_schema"))
        previous,actual=schema(old),schema(current)
        inputs=next(k.value for n in ast.walk(actual) if isinstance(n,ast.Call) and ast.unparse(n.func)=="io.Schema" for k in n.keywords if k.arg=="inputs")
        self.assertEqual(len(inputs.elts),27)
        self.assertTrue(all(n.args[0].value.startswith("strata_") for n in inputs.elts[16:]))
        inputs.elts=inputs.elts[:16]
        self.assertEqual(ast.dump(actual),ast.dump(previous))
        self.assertEqual(config.PROVIDER_OPTIONS[:4],["Seedance NZ","T8 AI Workshop","OpenAI Compatible","Local Qwen"])
        self.assertEqual(config.PROVIDER_OPTIONS[4:], ["Strata"])

    def test_strata_build_merge_never_resolve_old_alias_or_extra_parameters(self):
        with patch.object(config,"get_credential",side_effect=AssertionError("old alias must be ignored")):
            value=config.build_provider_config(provider="Strata",credential_alias="old-cloud",extra_parameters_json="invalid JSON",custom_model="old",strata_max_tokens=0)
            result=config.merge_provider_config({"api_mode":"old-mode","api_key":"old-key"},value,api_mode_map={})
        self.assertEqual(result["api_mode"],sp.STRATA_API_MODE)
        self.assertEqual(result["provider_request_options"],{"strata_settings":sp.StrataSettings().public_values()})
        self.assertNotIn("credential_alias",value)

    def test_decorator_never_touches_service_for_original_or_restore(self):
        @sp.strata_execution
        def execute(api_mode="old",provider_config=None,recovery_action="normal"):
            return "old-output"
        with patch.object(sp,"StrataRun",side_effect=AssertionError("no run expected")):
            self.assertEqual(execute(),"old-output")
            self.assertEqual(execute(api_mode=sp.STRATA_API_MODE,recovery_action="restore_last"),"old-output")
            self.assertEqual(execute(api_mode=sp.STRATA_API_MODE,provider_config={"provider":"Local Qwen"}),"old-output")

    def test_native_bad_contract_and_server_changed_identity_no_complete(self):
        for content in ([{"type":"strata_video","contract_version":1,"mode":"frames","frames":[],"metadata":{}}],
                        [{"type":"image_url","image_url":None}]):
            with http_fixture() as (url,seen):
                run=sp.StrataRun({"url":url})
                try:
                    with self.assertRaises(sp.StrataProviderError):run.complete([{"role":"user","content":content}],temperature=.5)
                    self.assertFalse(any(x[0]=="POST" for x in seen))
                finally:run.close()

    def test_frame_source_contract_is_inline_and_strict_clock(self):
        frame={"source":"data:image/png;base64,eA==","timestamp_s":0.,"source_timestamp_s":0.,"index":0}
        part={"type":"strata_video","contract_version":1,"mode":"frames","frames":[frame,dict(frame)],"metadata":{"duration_s":1.,"time_origin_s":0.}}
        with http_fixture() as (url,seen):
            run=sp.StrataRun({"url":url})
            try:
                with self.assertRaisesRegex(sp.StrataProviderError,"increase"):
                    run.complete([{"role":"user","content":[part]}],temperature=.5)
                self.assertEqual(run.requests,0)
            finally:run.close()

    def test_yue2_strata_keeps_node_owned_json_and_abc_repair_boundary(self):
        tree=ast.parse((ROOT/"yue2.py").read_text(encoding="utf-8"))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="YuE2Runner")
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="_complete")
        branch=next(n for n in ast.walk(method) if isinstance(n,ast.If) and ast.unparse(n.test)=="is_strata_mode(self.values['api_mode'])")
        calls=[n for n in ast.walk(ast.Module(body=branch.body,type_ignores=[])) if isinstance(n,ast.Call) and ast.unparse(n.func)=="require_strata_run().complete"]
        self.assertEqual(len(calls),1)
        self.assertNotIn("response_format",{k.arg for k in calls[0].keywords})
        self.assertIn("return _json_object(text)",ast.unparse(method))

if __name__=="__main__":unittest.main()
