"""Owned acceptance server only; real producer loaded read-only when explicitly set."""
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comfy_api.latest import ComfyExtension, io
from marker_producer_loader import load_producer
from visual_marker_fixture import material
import torch


class MarkerRuntimeFixture(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="T8MarkerRuntimeFixture", category="test-only",
            inputs=[io.Combo.Input("case", options=["valid", "poison", "bad_record", "wrong_image"], default="valid"),
                    io.Int.Input("variant", default=0), io.Int.Input("selector", default=1)],
            outputs=[io.Custom("T8_H3_VISUAL_MARKER_PLAN").Output(), io.Image.Output(), io.Int.Output()])

    @classmethod
    def execute(cls, case="valid", variant=0, selector=1):
        if case == "poison": raise RuntimeError("MARKER_POISON_EXECUTED")
        path = os.environ.get("T8_MARKER_PRODUCER_ROOT")
        if path:
            p = load_producer(path)
            _, plan, _ = p.prepare_markers(torch.full((1, 32, 48, 3), min(variant, 8)/10), p.DEFAULT_MARKERS)
        else:
            plan = material()
        image = plan.marked_image.clone()
        if case == "bad_record":
            from types import SimpleNamespace
            plan = SimpleNamespace(**{**vars(plan), "record_json": "{}"})
        if case == "wrong_image": image[0, 0, 0, 0] = .95
        return io.NodeOutput(plan, image, int(selector))


class FixtureExtension(ComfyExtension):
    async def get_node_list(self):
        nodes = [MarkerRuntimeFixture]
        if os.environ.get("T8_MARKER_PRODUCER_ROOT"):
            import importlib
            producer = load_producer(os.environ["T8_MARKER_PRODUCER_ROOT"])
            # Register only the existing pure Prepare class, never the audio plugin entrypoint.
            module = importlib.import_module(producer.__package__ + ".nodes_visual_marker")
            nodes.append(module.MiniMaxH3VisualMarkerPrepareEXPT8)
        return nodes


async def comfy_entrypoint(): return FixtureExtension()
