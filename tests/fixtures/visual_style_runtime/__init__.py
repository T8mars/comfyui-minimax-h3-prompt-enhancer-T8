"""Only installed by the owned loopback acceptance host, never distributed."""
import importlib
import sys
from comfy_api.latest import ComfyExtension, io


def core():
    module = next(m for name, m in list(sys.modules.items()) if name.endswith('.visual_styles') and hasattr(m, 'consumer_fingerprint'))
    return module


class VisualStyleFixture(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='T8VisualStyleRuntimeFixture', category='test-only',
            inputs=[io.Combo.Input('mode', options=['valid', 'bad', 'poison'], default='valid')],
            outputs=[io.Custom('T8_COLOR_STYLE_CONFIG').Output(), io.Custom('T8_CREATOR_STYLE_CONFIG').Output()])

    @classmethod
    def execute(cls, mode='valid'):
        if mode == 'poison': raise RuntimeError('VISUAL_STYLE_POISON_EXECUTED')
        if mode == 'bad': return io.NodeOutput({'bad': 'fixture'}, {'bad': 'fixture'})
        styles = core()
        return io.NodeOutput(styles.build_style_config('color', styles.ON, '001'), styles.build_style_config('creator', styles.ON, '181'))


class Extension(ComfyExtension):
    async def get_node_list(self):
        return [VisualStyleFixture]


async def comfy_entrypoint():
    from aiohttp import web
    from server import PromptServer
    state = {'revision': 0, 'original': None}

    @PromptServer.instance.routes.post('/t8-test-visual-style/revision')
    async def revision(request):
        # This test-only route is reachable solely on a newly owned 127.0.0.1 host.
        if request.remote not in ('127.0.0.1', '::1'): return web.Response(status=403)
        styles = core()
        if state['original'] is None:
            state['original'] = styles.load_catalog
            def simulated_catalog():
                catalog, digest = state['original']()
                return catalog, digest if state['revision'] == 0 else f"{state['revision']:064x}"
            styles.load_catalog = simulated_catalog
        state['revision'] += 1
        return web.json_response({'revision': state['revision'], 'test_only': True})

    return Extension()
