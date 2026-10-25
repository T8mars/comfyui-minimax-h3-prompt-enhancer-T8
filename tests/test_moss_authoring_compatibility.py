"""Freeze the 1.36 node prefix and existing examples, with only MOSS opt-in edits."""
from visual_style_baseline_projection import project_style_ast
import ast
import asyncio
from pathlib import Path
import subprocess
import sys
import unittest

from test_directional_skills import GIT_ROOT, ROOT, h3

BASELINE = "e299574ec30df483411ffb9c79dd7138d19d57a6"


def frozen(name):
    return subprocess.check_output(["git", "show", BASELINE + ":" + name], cwd=GIT_ROOT)


class AuthoringCompatibility(unittest.TestCase):
    def test_old_registration_is_exact_prefix_and_other_node_sources_are_frozen(self):
        package = sys.modules[h3.__package__]
        old_ast = ast.parse(frozen("__init__.py"))
        old_class = next(node for node in old_ast.body if isinstance(node, ast.ClassDef) and node.name == "T8PromptEnhancerExtension")
        namespace = dict(vars(package))
        exec(compile(ast.Module(body=[old_class], type_ignores=[]), "frozen-registration", "exec"), namespace)
        previous = asyncio.run(namespace["T8PromptEnhancerExtension"]().get_node_list())
        current = asyncio.run(asyncio.run(package.comfy_entrypoint()).get_node_list())
        self.assertEqual(len(previous), 34)
        self.assertEqual(current[:34], previous)
        self.assertEqual([cls.define_schema().node_id for cls in current[34:36]], ["MOSSAuthoringDirectorT8", "MOSSAuthoringPageT8"])
        for cls in previous:
            module = sys.modules[cls.__module__]
            path = Path(module.__file__).resolve()
            name = path.relative_to(ROOT).as_posix()
            if name == "moss_image.py": continue  # explicit schema/message gates in test_moss_authoring
            if name in ("nodes.py", "seedance20.py"):
                self.assertEqual(ast.dump(project_style_ast(path.read_text(encoding="utf-8"))), ast.dump(ast.parse(frozen(name))), name)
            else:
                self.assertEqual(path.read_bytes().replace(b"\r\n", b"\n"), frozen(name).replace(b"\r\n", b"\n"), name)

    def test_every_published_workflow_keeps_its_original_bytes(self):
        names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASELINE, "example_workflows"], cwd=GIT_ROOT).decode().splitlines()
        for name in names:
            if name.endswith(".json"):
                # Existing git text policy may check out CRLF. Preserve the
                # actual JSON bytes modulo that pre-existing newline policy.
                self.assertEqual((ROOT / name).read_bytes().replace(b"\r\n", b"\n"), frozen(name).replace(b"\r\n", b"\n"), name)
        for filename in ("verify.yml", "publish_action.yml"):
            self.assertIn(BASELINE, (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8"))


if __name__ == "__main__": unittest.main()
