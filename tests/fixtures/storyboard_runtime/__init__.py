"""Explicitly loaded only by the owned isolated acceptance server."""
from comfy_api.latest import ComfyExtension, io


class StoryboardRuntimeFixture(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="T8StoryboardRuntimeFixture", category="test-only",
                         inputs=[io.Boolean.Input("poison", default=False)],
                         outputs=[io.Custom("T8_STORYBOARD_DIRECTOR_CONFIG").Output()])

    @classmethod
    def execute(cls, poison=False):
        if poison:
            raise RuntimeError("STORYBOARD_POISON_EXECUTED")
        return io.NodeOutput({"schema_version": "invalid-test-config"})


class FixtureExtension(ComfyExtension):
    async def get_node_list(self):
        return [StoryboardRuntimeFixture]


async def comfy_entrypoint():
    return FixtureExtension()
