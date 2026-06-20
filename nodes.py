"""OllamaUnload node: V1 (legacy dict API) and V3 (comfy_api schema) wrappers.

Both wrappers are thin adapters over ollama_unload_core.unload_ollama. On the
0.25.0 loader (nodes.py if/elif at ~2243), a module exporting NODE_CLASS_MAPPINGS
is loaded via the V1 path and comfy_entrypoint is not called, so there is no
double registration. The V3 class is provided import-guarded for builds whose
loader prefers comfy_entrypoint.
"""

from .ollama_unload_core import unload_ollama


# ---- V1 wildcard type (matches any upstream socket) ----
class _AnyType(str):
    def __ne__(self, other):
        return False


ANY = _AnyType("*")

_URL_DEFAULT = "http://127.0.0.1:11434"
_MODEL_TIP = "Exact model name to unload (e.g. gemma4:26b). Empty = unload every loaded model."
_WAIT_TIP = "Block until the model leaves Ollama memory (VRAM actually freed) before continuing."
_TIMEOUT_TIP = "Max seconds to wait for the unload and the resident-memory poll."
_VRAM_TIP = "Also unload ComfyUI's own models and empty the CUDA cache."
_PASS_TIP = "Wire your final prompt/conditioning through here so this node runs BEFORE the sampler."
_STATUS_TIP = "Human-readable result of the unload."


# ---- V1 node ----
class OllamaUnloadV1:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": _URL_DEFAULT}),
                "model": ("STRING", {"default": "", "tooltip": _MODEL_TIP}),
                "wait": ("BOOLEAN", {"default": True, "tooltip": _WAIT_TIP}),
                "timeout": ("INT", {"default": 60, "min": 1, "max": 600, "tooltip": _TIMEOUT_TIP}),
                "free_comfy_vram": ("BOOLEAN", {"default": True, "tooltip": _VRAM_TIP}),
            },
            "optional": {
                "passthrough": (ANY, {"tooltip": _PASS_TIP}),
            },
        }

    RETURN_TYPES = (ANY, "STRING")
    RETURN_NAMES = ("passthrough", "status")
    FUNCTION = "run"
    CATEGORY = "ollama"
    DESCRIPTION = "Unload one or all Ollama models to free VRAM. Wire a prompt through passthrough to force it to run before image sampling."

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")  # always run; never use a cached result

    def run(self, url, model, wait, timeout, free_comfy_vram, passthrough=None):
        status = unload_ollama(url, model, wait, timeout, free_comfy_vram)
        return (passthrough if passthrough is not None else "", status)


NODE_CLASS_MAPPINGS = {"OllamaUnload": OllamaUnloadV1}
NODE_DISPLAY_NAME_MAPPINGS = {"OllamaUnload": "Ollama Unload (free VRAM)"}


# ---- V3 node (import-guarded) ----
try:
    from comfy_api.v0_0_2 import io, ComfyExtension

    class OllamaUnload(io.ComfyNode):
        @classmethod
        def define_schema(cls) -> io.Schema:
            return io.Schema(
                node_id="OllamaUnload",
                display_name="Ollama Unload (free VRAM)",
                category="ollama",
                description="Unload one or all Ollama models to free VRAM. Wire a prompt through passthrough to force it to run before image sampling.",
                inputs=[
                    io.String.Input("url", default=_URL_DEFAULT),
                    io.String.Input("model", default="", tooltip=_MODEL_TIP),
                    io.Boolean.Input("wait", default=True, tooltip=_WAIT_TIP),
                    io.Int.Input("timeout", default=60, min=1, max=600, tooltip=_TIMEOUT_TIP),
                    io.Boolean.Input("free_comfy_vram", default=True, tooltip=_VRAM_TIP),
                    io.AnyType.Input("passthrough", optional=True, tooltip=_PASS_TIP),
                ],
                outputs=[
                    io.AnyType.Output(id="passthrough", display_name="passthrough", tooltip=_PASS_TIP),
                    io.String.Output(id="status", display_name="status", tooltip=_STATUS_TIP),
                ],
            )

        @classmethod
        def fingerprint_inputs(cls, **kwargs):
            return float("nan")  # always run

        @classmethod
        def execute(cls, url, model, wait, timeout, free_comfy_vram, passthrough=None) -> io.NodeOutput:
            status = unload_ollama(url, model, wait, timeout, free_comfy_vram)
            return io.NodeOutput(passthrough if passthrough is not None else "", status)

    class OllamaUnloadExtension(ComfyExtension):
        async def get_node_list(self):
            return [OllamaUnload]

    async def comfy_entrypoint() -> "OllamaUnloadExtension":
        return OllamaUnloadExtension()

except ImportError:
    # Older ComfyUI without comfy_api: V1 mappings above are the only path.
    pass
