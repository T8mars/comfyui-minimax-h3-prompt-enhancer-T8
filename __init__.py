from comfy_api.latest import ComfyExtension, io

from .nodes import MiniMaxH3PromptEnhancer
from .seedance20 import Seedance20PromptEnhancer


WEB_DIRECTORY = "./web/js"


class T8PromptEnhancerExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [MiniMaxH3PromptEnhancer, Seedance20PromptEnhancer]


async def comfy_entrypoint() -> T8PromptEnhancerExtension:
    return T8PromptEnhancerExtension()


__all__ = ["WEB_DIRECTORY", "T8PromptEnhancerExtension", "comfy_entrypoint"]
