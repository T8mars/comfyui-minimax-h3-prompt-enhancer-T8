"""Two independent, local-only visual presentation configuration nodes."""
from comfy_api.latest import io
try:
    from . import visual_styles as styles
except ImportError:
    import visual_styles as styles

ColorStyleIO = io.Custom("T8_COLOR_STYLE_CONFIG")
CreatorStyleIO = io.Custom("T8_CREATOR_STYLE_CONFIG")


class T8ColorStyleConfig(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8ColorStyleConfig", display_name="T8 Color Style Config（色彩风格配置）",
            category="T8/Utilities",
            description="独立200色卡参考，接入H3/Seedance；默认关闭，不修改图片，不新增模型请求。 / Optional color reference; not a LUT.",
            inputs=[
                io.Combo.Input("mode", display_name="模式 / Mode", options=styles.MODES, default=styles.OFF, socketless=True),
                io.Combo.Input("palette", display_name="色彩风格 / Palette", options=styles.style_options(), default=styles.NONE, socketless=True),
                io.Combo.Input("scope", display_name="作用范围 / Scope", options=styles.SCOPES, default=styles.COLOR_ONLY, socketless=True),
            ], outputs=[ColorStyleIO.Output(display_name="color_style_config")],
        )

    @classmethod
    def validate_inputs(cls, mode=styles.OFF, palette=styles.NONE, scope=styles.COLOR_ONLY):
        try:
            styles.build_style_config("color", mode, palette, scope)
            return True
        except ValueError as error:
            return str(error)

    @classmethod
    def fingerprint_inputs(cls, mode=styles.OFF, palette=styles.NONE, scope=styles.COLOR_ONLY):
        return styles.helper_fingerprint("color", mode, palette, scope)

    @classmethod
    def execute(cls, mode=styles.OFF, palette=styles.NONE, scope=styles.COLOR_ONLY):
        return io.NodeOutput(styles.build_style_config("color", mode, palette, scope))


class T8CreatorStyleConfig(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="T8CreatorStyleConfig", display_name="T8 Creator Style Config（导演风格参考）",
            category="T8/Utilities",
            description="独立导演/摄影/美术拍法参考，接入H3/Seedance；不自动套颜色、不新增剧情或模型请求。 / Presentation reference, not a screenplay generator.",
            inputs=[
                io.Combo.Input("mode", display_name="模式 / Mode", options=styles.MODES, default=styles.OFF, socketless=True),
                io.Combo.Input("creator", display_name="导演/创作者 / Creator", options=styles.style_options(), default=styles.NONE, socketless=True),
            ], outputs=[CreatorStyleIO.Output(display_name="creator_style_config")],
        )

    @classmethod
    def validate_inputs(cls, mode=styles.OFF, creator=styles.NONE):
        try:
            styles.build_style_config("creator", mode, creator)
            return True
        except ValueError as error:
            return str(error)

    @classmethod
    def fingerprint_inputs(cls, mode=styles.OFF, creator=styles.NONE):
        return styles.helper_fingerprint("creator", mode, creator)

    @classmethod
    def execute(cls, mode=styles.OFF, creator=styles.NONE):
        return io.NodeOutput(styles.build_style_config("creator", mode, creator))
