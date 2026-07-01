#!/usr/bin/env python3
"""Bootstrap: download Drishti's offline speech + intent + LLM assets.

Fetches everything Drishti needs to run without internet:
  1. transformers.js runtime + ONNX WASM     ~10 MB  → js/vendor/
  2. Xenova/whisper-base.en (quantized)      ~90 MB  → models/Xenova/whisper-base.en/
  3. Xenova/all-MiniLM-L6-v2 (quantized)     ~22 MB  → models/Xenova/all-MiniLM-L6-v2/
  4. Llama-3.2-1B-Instruct MLC (q4f16_1)    ~800 MB  → models/mlc-ai/Llama-3.2-1B-Instruct-q4f16_1-MLC/
  5. WebLLM runtime                          ~2 MB   → js/vendor/

Total ≈ 920 MB, one-time. Idempotent — re-running skips files already on disk.

Run:
    python download_drishti_models.py

Requires nothing but Python 3.8+ (stdlib only, no pip installs).
"""

from __future__ import annotations
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
VENDOR = ROOT / "js" / "vendor"

TRANSFORMERS_VER = "2.17.2"
WEBLLM_VER = "0.2.79"

JS_ASSETS: list[tuple[str, Path]] = [
    (f"https://cdn.jsdelivr.net/npm/@xenova/transformers@{TRANSFORMERS_VER}/dist/transformers.min.js",
     VENDOR / "transformers.min.js"),
    (f"https://cdn.jsdelivr.net/npm/@xenova/transformers@{TRANSFORMERS_VER}/dist/ort-wasm-simd.wasm",
     VENDOR / "ort-wasm-simd.wasm"),
    (f"https://cdn.jsdelivr.net/npm/@xenova/transformers@{TRANSFORMERS_VER}/dist/ort-wasm-simd-threaded.wasm",
     VENDOR / "ort-wasm-simd-threaded.wasm"),
    (f"https://cdn.jsdelivr.net/npm/@xenova/transformers@{TRANSFORMERS_VER}/dist/ort-wasm.wasm",
     VENDOR / "ort-wasm.wasm"),
    (f"https://cdn.jsdelivr.net/npm/@xenova/transformers@{TRANSFORMERS_VER}/dist/ort-wasm-threaded.wasm",
     VENDOR / "ort-wasm-threaded.wasm"),
    (f"https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@{WEBLLM_VER}/lib/index.js",
     VENDOR / "web-llm.js"),
]

def hf_files(repo: str, files: Iterable[str]) -> list[tuple[str, Path]]:
    """Build (url, dest) pairs for a HuggingFace repo — no HF API calls."""
    base = f"https://huggingface.co/{repo}/resolve/main"
    return [(f"{base}/{f}", MODELS / repo / f) for f in files]

WHISPER_FILES = hf_files("Xenova/whisper-base.en", [
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "preprocessor_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
    "normalizer.json",
    "onnx/encoder_model_quantized.onnx",
    "onnx/decoder_model_merged_quantized.onnx",
])

MINILM_FILES = hf_files("Xenova/all-MiniLM-L6-v2", [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
    "onnx/model_quantized.onnx",
])

# WebLLM's Llama-3.2-1B MLC bundle uses many shards. The ndarray-cache.json
# manifest lists them all; we fetch that first, then every shard it references.
LLM_REPO = "mlc-ai/Llama-3.2-1B-Instruct-q4f16_1-MLC"
LLM_STATIC_FILES = [
    "mlc-chat-config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "ndarray-cache.json",
    "tokenizer.model",
]

# Files that some model repos omit (e.g., .en whisper has no vocab.json). If
# a fetch 404s on one of these, treat as optional and continue.
OPTIONAL_SUFFIXES = ("added_tokens.json", "normalizer.json", "tokenizer.model", "vocab.json")


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:6.1f} {unit}"
        n /= 1024
    return f"{n:6.1f} TB"


def download(url: str, dst: Path, optional: bool = False) -> bool:
    rel = dst.relative_to(ROOT)
    if dst.exists() and dst.stat().st_size > 0:
        print(f"  ✓ {rel}  ({human(dst.stat().st_size).strip()})  [cached]")
        return True

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "drishti-bootstrap/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            last_pct = -1
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = (done * 100) // total
                        if pct != last_pct:
                            print(f"\r    {rel}  {pct:3d}%  ({human(done)}/{human(total)})",
                                  end="", flush=True)
                            last_pct = pct
        tmp.rename(dst)
        print(f"\r  ✓ {rel}  ({human(dst.stat().st_size).strip()})              ")
        return True
    except urllib.error.HTTPError as e:
        if tmp.exists():
            tmp.unlink()
        # HuggingFace returns 401 for missing paths in public repos (not 404).
        # Treat 401 the same as 404 when the file is marked optional.
        if optional and e.code in (401, 403, 404):
            print(f"  · {rel}  [optional, not in repo — skipped]")
            return True
        print(f"\n  ✗ {rel}  HTTP {e.code}: {url}", file=sys.stderr)
        return False
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        if tmp.exists():
            tmp.unlink()
        print(f"\n  ✗ {rel}  {e}", file=sys.stderr)
        return False


def fetch_group(title: str, items: list[tuple[str, Path]]) -> bool:
    print(f"\n{title}")
    ok = True
    for url, dst in items:
        optional = dst.name in OPTIONAL_SUFFIXES
        if not download(url, dst, optional=optional):
            ok = False
    return ok


def fetch_llm_shards() -> bool:
    print("\n[4/4] Llama-3.2-1B-Instruct MLC (~800 MB) — shard manifest first")
    # Get the manifest.
    static = [(f"https://huggingface.co/{LLM_REPO}/resolve/main/{f}",
               MODELS / LLM_REPO / f) for f in LLM_STATIC_FILES]
    for url, dst in static:
        optional = dst.name in OPTIONAL_SUFFIXES
        if not download(url, dst, optional=optional):
            print(f"  Cannot proceed without {dst.name}. Skipping LLM.", file=sys.stderr)
            return False

    manifest_path = MODELS / LLM_REPO / "ndarray-cache.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as e:
        print(f"  Cannot parse {manifest_path}: {e}", file=sys.stderr)
        return False

    shard_names = sorted({rec["dataPath"] for rec in manifest.get("records", [])})
    print(f"  Manifest lists {len(shard_names)} shard(s)")
    shard_items = [(f"https://huggingface.co/{LLM_REPO}/resolve/main/{s}",
                    MODELS / LLM_REPO / s) for s in shard_names]

    ok = True
    for url, dst in shard_items:
        if not download(url, dst):
            ok = False

    # WebLLM's compiled WebGPU library (~5 MB). The correct URL is baked into
    # web-llm.js's prebuiltAppConfig: modelLibURLPrefix + modelVersion + name.
    # For web-llm 0.2.79 that resolves to raw.githubusercontent (NOT huggingface,
    # which is why the earlier huggingface.co attempt 401'd).
    LIB_REPO = "mlc-ai/binary-mlc-llm-libs"
    LIB_NAME = "Llama-3.2-1B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm"
    LIB_CANDIDATES = [
        f"https://raw.githubusercontent.com/{LIB_REPO}/main/web-llm-models/v0_2_48/{LIB_NAME}",
        f"https://huggingface.co/{LIB_REPO}/resolve/main/web-llm-models/v0_2_48/{LIB_NAME}",
    ]
    lib_dst = VENDOR / LIB_NAME
    if lib_dst.exists() and lib_dst.stat().st_size > 0:
        print(f"  ✓ {lib_dst.relative_to(ROOT)}  ({human(lib_dst.stat().st_size).strip()})  [cached]")
    else:
        lib_ok = False
        for url in LIB_CANDIDATES:
            if download(url, lib_dst, optional=True):
                if lib_dst.exists() and lib_dst.stat().st_size > 0:
                    lib_ok = True
                    break
        if not lib_ok:
            print("  · WebGPU library not fetched here — that's OK: the browser will")
            print("    fetch it from WebLLM's default URL on first (online) load and")
            print("    cache it. After that, airplane mode works.")
    return ok


def main() -> int:
    print("Drishti — bootstrap offline models")
    print(f"  Repo root : {ROOT}")
    print(f"  Vendor dir: {VENDOR.relative_to(ROOT)}")
    print(f"  Models dir: {MODELS.relative_to(ROOT)}")

    all_ok = True
    all_ok &= fetch_group("[1/4] JS runtimes (transformers.js + WebLLM, ~12 MB)", JS_ASSETS)
    all_ok &= fetch_group("[2/4] whisper-base.en quantized (~90 MB)", WHISPER_FILES)
    all_ok &= fetch_group("[3/4] all-MiniLM-L6-v2 quantized (~22 MB)", MINILM_FILES)
    all_ok &= fetch_llm_shards()

    print()
    if all_ok:
        print("Done. Everything is on disk.")
        print("Serve locally:")
        print("  python -m http.server 3020")
        print("Open: http://localhost:3020")
        return 0
    print("Some downloads failed — see errors above. Re-run to retry (idempotent).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
