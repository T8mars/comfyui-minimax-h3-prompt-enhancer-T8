from __future__ import annotations

from comfy_api.latest import io


class T8PromptText(io.ComfyNode):
    """A dependency-free multiline STRING source for bundled workflows."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8PromptText",
            display_name="T8 Prompt Text",
            category="T8/Utilities",
            description="Enter multiline text and expose it as a standard STRING output. No API or model is called.",
            inputs=[
                io.String.Input(
                    "text",
                    display_name="文本 / Prompt",
                    multiline=True,
                    default="",
                    dynamic_prompts=True,
                ),
            ],
            outputs=[io.String.Output(display_name="text")],
        )

    @classmethod
    def execute(cls, text="") -> io.NodeOutput:
        return io.NodeOutput(str(text or ""))


class T8ShowText(io.ComfyNode):
    """An output node that previews a STRING and passes it through unchanged."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8ShowText",
            display_name="T8 Show Text",
            category="T8/Utilities",
            description="Display an incoming STRING inside the node and pass it through unchanged.",
            is_output_node=True,
            inputs=[
                io.String.Input(
                    "text",
                    display_name="待显示文本",
                    multiline=True,
                    default="",
                    force_input=True,
                ),
            ],
            outputs=[io.String.Output(display_name="text")],
        )

    @classmethod
    def execute(cls, text="") -> io.NodeOutput:
        value = str(text or "")
        return io.NodeOutput(value, ui={"text": [value]})


__all__ = ["T8PromptText", "T8ShowText"]
