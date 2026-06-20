"""ComfyUI_OllamaUnload: free VRAM by unloading Ollama models mid-workflow.

Exports V1 NODE_CLASS_MAPPINGS (authoritative on the 0.25.0 if/elif loader) and
comfy_entrypoint for builds whose loader prefers the V3 schema API.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

try:
    from .nodes import comfy_entrypoint  # noqa: F401
except ImportError:
    pass

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "comfy_entrypoint"]
