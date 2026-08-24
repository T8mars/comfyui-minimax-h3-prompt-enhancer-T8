from comfy_api.latest import ComfyExtension, io

from .nodes import MiniMaxH3PromptEnhancer
from .music3 import MiniMaxMusic3PromptEnhancer
from .seedance20 import Seedance20PromptEnhancer
from .case_library_routes import register_routes
from .local_qwen_routes import register_local_qwen_routes
from .diagnostics_routes import register_diagnostics_routes
from .provider_config import T8LLMProviderConfig
from .credential_routes import register_credential_routes
from .prompt_inspector import T8PromptInspector


WEB_DIRECTORY = "./web/js"
register_routes()
register_local_qwen_routes()
register_diagnostics_routes()
register_credential_routes()


class T8PromptEnhancerExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            MiniMaxH3PromptEnhancer,
            Seedance20PromptEnhancer,
            MiniMaxMusic3PromptEnhancer,
            T8LLMProviderConfig,
            T8PromptInspector,
        ]


async def comfy_entrypoint() -> T8PromptEnhancerExtension:
    return T8PromptEnhancerExtension()


__all__ = [
    "WEB_DIRECTORY",
    "T8PromptEnhancerExtension",
    "MiniMaxMusic3PromptEnhancer",
    "T8LLMProviderConfig",
    "T8PromptInspector",
    "comfy_entrypoint",
]
