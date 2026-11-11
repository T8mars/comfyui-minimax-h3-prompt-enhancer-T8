"""Recheck Comfy memory after another workflow ran while a GGUF stayed warm."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import comfy
from test_local_qwen import runtime, python_runtime


class WarmMemoryTests(unittest.TestCase):
    def exercise(self, implementation, *, automatic):
        events = []
        memory = {"free": 512 * 1024**2}

        def free_memory():
            events.append("check")
            return memory["free"]

        def unload():
            events.append("unload-comfy")
            memory["free"] = 32 * 1024**3

        host = SimpleNamespace(get_free_memory=free_memory, unload_all_models=unload,
            soft_empty_cache=lambda: events.append("empty-cache"),
            throw_exception_if_processing_interrupted=lambda: None)

        class FakeRuntime:
            is_running = False
            def __init__(self, **kwargs): pass
            def start(self):
                self.is_running = True
                events.append("start-gguf")
            def stop(self): self.is_running = False
            def chat(self, **kwargs):
                events.append("chat")
                return "result", {}

        spec = implementation.PythonRuntimeSpec(version="test-memory")
        discovery = (patch.object(implementation, "available_runtime_specs", return_value=([spec], []))
            if implementation is runtime else patch.object(implementation, "select_runtime_spec", return_value=spec))
        manager = implementation.LocalQwenManager()
        policy = implementation.LOCAL_RELEASE_COMFY_AUTO if automatic else implementation.LOCAL_KEEP_COMFY_MODELS
        with patch.object(comfy, "model_management", host, create=True), patch.dict(sys.modules, {"comfy.model_management": host}), \
                patch.object(implementation, "LlamaPythonRuntime", FakeRuntime), discovery:
            try:
                args = dict(model=Path("memory-test.gguf"), mmproj=None, context_size=4096, comfy_memory_policy=policy)
                first = manager.begin_run(**args)
                self.assertEqual(manager.complete(first)[0], "result")
                manager.end_run(implementation.LOCAL_KEEP_WARM)
                # A separate video workflow now occupies memory. Keep the GGUF key unchanged.
                memory["free"] = 512 * 1024**2
                events.append("video")
                second = manager.begin_run(**args)
                self.assertEqual(manager.complete(second)[0], "result")
                manager.end_run(implementation.LOCAL_KEEP_WARM)
                self.assertIs(first, second)
                self.assertEqual(events.count("start-gguf"), 1, "Do not reload the warm GGUF")
                if automatic:
                    self.assertEqual(events.count("unload-comfy"), 2, events)
                    self.assertEqual(events[events.index("video") + 1:], ["check", "unload-comfy", "empty-cache", "chat"])
                else:
                    self.assertNotIn("check", events)
                    self.assertNotIn("unload-comfy", events)
            finally:
                manager.release()

    def test_automatic_policy_rechecks_memory_before_warm_generation_in_both_distributions(self):
        for implementation in (runtime, python_runtime):
            with self.subTest(implementation=implementation.__name__):
                self.exercise(implementation, automatic=True)

    def test_keep_comfy_policy_preserves_models_on_both_cold_and_warm_runs(self):
        for implementation in (runtime, python_runtime):
            with self.subTest(implementation=implementation.__name__):
                self.exercise(implementation, automatic=False)


if __name__ == "__main__":
    unittest.main()
