"""Unit tests for the OllamaUnload shared core.

Pure logic, no ComfyUI and no running Ollama required: HTTP is mocked.
Run: python -m unittest test_ollama_unload -v
"""

import unittest
import ollama_unload_core as core


class FakeOllama:
    """Replaces core._http_json with an in-memory Ollama."""

    def __init__(self, loaded):
        self.loaded = list(loaded)
        self.unload_calls = []

    def __call__(self, url, payload=None, method=None, timeout=10):
        if url.endswith("/api/ps"):
            return {"models": [{"name": n} for n in self.loaded]}
        if url.endswith("/api/generate"):
            model = payload["model"]
            assert payload.get("keep_alive") == 0, "unload must send keep_alive=0"
            self.unload_calls.append(model)
            self.loaded = [m for m in self.loaded if m != model]
            return {"done": True}
        return {}


class TestUnloadCore(unittest.TestCase):
    def setUp(self):
        self._orig = core._http_json

    def tearDown(self):
        core._http_json = self._orig

    def test_unload_specific_model(self):
        fake = FakeOllama(["gemma4:26b", "nomic-embed"])
        core._http_json = fake
        status = core.unload_ollama("http://x:11434/", model="gemma4:26b",
                                    wait=True, timeout=5, free_comfy_vram=False)
        self.assertIn("unload requested: gemma4:26b", status)
        self.assertNotIn("WARNING", status)
        self.assertEqual(fake.loaded, ["nomic-embed"])
        self.assertEqual(fake.unload_calls, ["gemma4:26b"])

    def test_empty_model_unloads_all(self):
        fake = FakeOllama(["gemma4:26b", "nomic-embed"])
        core._http_json = fake
        status = core.unload_ollama("http://x:11434", model="",
                                    wait=True, timeout=5, free_comfy_vram=False)
        self.assertEqual(fake.loaded, [])
        self.assertEqual(sorted(fake.unload_calls), ["gemma4:26b", "nomic-embed"])
        self.assertNotIn("WARNING", status)

    def test_nothing_loaded(self):
        core._http_json = FakeOllama([])
        status = core.unload_ollama("http://x:11434", model="",
                                    wait=True, timeout=5, free_comfy_vram=False)
        self.assertEqual(status, "no models loaded")

    def test_unreachable_raises(self):
        def boom(*a, **k):
            raise OSError("connection refused")
        core._http_json = boom
        with self.assertRaises(RuntimeError) as ctx:
            core.unload_ollama("http://x:11434", model="",
                               wait=True, timeout=2, free_comfy_vram=False)
        self.assertIn("cannot reach Ollama", str(ctx.exception))

    def test_url_trailing_slash_normalized(self):
        fake = FakeOllama(["gemma4:26b"])
        core._http_json = fake
        core.unload_ollama("http://x:11434///", model="gemma4:26b",
                           wait=False, timeout=2, free_comfy_vram=False)
        self.assertEqual(fake.unload_calls, ["gemma4:26b"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
