"""Shared core logic for the OllamaUnload node.

Pure stdlib (urllib, json, time). No ComfyUI imports here except the optional
comfy.model_management call, which is wrapped so this module imports cleanly
outside ComfyUI for unit testing.

Unload method: POST /api/generate with {"model": m, "keep_alive": 0}. This is
Ollama's documented way to evict a model from memory immediately. Killing the
ollama server process is avoided on purpose: the server respawns and reloads
the model, which is exactly the failure the user hit.
"""

import json
import time
import urllib.request
import urllib.error


def _http_json(url, payload=None, method=None, timeout=10):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method or ("POST" if data is not None else "GET"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body.strip() else {}


def _loaded_models(base, timeout=10):
    """Return the names of models currently resident per /api/ps."""
    ps = _http_json(base + "/api/ps", timeout=timeout)
    names = []
    for m in ps.get("models", []):
        name = m.get("name") or m.get("model")
        if name:
            names.append(name)
    return names


def unload_ollama(url, model="", wait=True, timeout=60, free_comfy_vram=True):
    """Unload one or all Ollama models and optionally free ComfyUI VRAM.

    url: Ollama base URL, e.g. http://127.0.0.1:11434
    model: exact model name to unload; empty string unloads every loaded model.
    wait: block until the target model(s) leave /api/ps (VRAM actually freed).
    timeout: seconds to wait for both the unload call and the resident poll.
    free_comfy_vram: also unload ComfyUI's own models and empty the cache.

    Returns a status string. Raises RuntimeError if Ollama is unreachable or an
    unload call fails, so the workflow fails loudly instead of silently OOMing
    later.
    """
    base = url.rstrip("/")
    call_timeout = min(timeout, 30)
    poll_timeout = min(timeout, 10)

    try:
        loaded = _loaded_models(base, poll_timeout)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise RuntimeError(
            f"OllamaUnload: cannot reach Ollama at {base} (/api/ps): {e}"
        )

    targets = [model.strip()] if model.strip() else list(loaded)
    targets = [t for t in targets if t]
    msgs = []

    for m in targets:
        try:
            _http_json(base + "/api/generate", {"model": m, "keep_alive": 0}, timeout=call_timeout)
            msgs.append(f"unload requested: {m}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise RuntimeError(f"OllamaUnload: unload call failed for {m}: {e}")

    if wait and targets:
        watch = set(targets)
        deadline = time.time() + timeout
        still = watch
        while time.time() < deadline:
            try:
                still = set(_loaded_models(base, poll_timeout)) & watch
            except (urllib.error.URLError, OSError, ValueError):
                still = set()
            if not still:
                break
            time.sleep(0.25)
        if still:
            msgs.append(f"WARNING: still resident after {timeout}s: {sorted(still)}")

    if free_comfy_vram:
        try:
            import comfy.model_management as mm
            mm.unload_all_models()
            mm.soft_empty_cache()
            msgs.append("comfy vram freed")
        except Exception as e:  # comfy not importable in unit context, or API drift
            msgs.append(f"comfy free skipped: {e}")

    return "; ".join(msgs) if msgs else "no models loaded"
