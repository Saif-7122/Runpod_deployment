"""Free local GPU models (run on the RunPod 4090). Loaded lazily, one family at a time, so they share VRAM.

  Voice   : chatterbox (MIT)  | indic_parler (Apache 2.0, Indian-English accent) | kokoro (Apache 2.0)
  Vision  : Qwen2.5-VL-7B-Instruct (Apache 2.0) - clip review + draft-video judge
  Speech  : faster-whisper large-v3 (MIT) - transcripts of clips with their own audio

Licences and credits: LICENSES.md
"""
import gc
import threading
from pathlib import Path

from common import log

GPU_LOCK = threading.RLock()          # one model family on the GPU at a time
_loaded = {"name": None, "obj": None}


def _device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _swap(name, loader):
    """Keep only one model family in VRAM: unload the previous one before loading the next."""
    if _loaded["name"] == name:
        return _loaded["obj"]
    if _loaded["obj"] is not None:
        log("gpu", f"unloading {_loaded['name']}")
        _loaded["obj"] = None
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
    log("gpu", f"loading {name} on {_device()}")
    _loaded.update(name=name, obj=loader())
    return _loaded["obj"]


# ------------------------------------------------------------------ voice

def _load_chatterbox():
    from chatterbox.tts import ChatterboxTTS
    return ChatterboxTTS.from_pretrained(device=_device())


def _load_indic_parler():
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer
    name = "ai4bharat/indic-parler-tts"
    model = ParlerTTSForConditionalGeneration.from_pretrained(name).to(_device())
    tok = AutoTokenizer.from_pretrained(name)
    desc_tok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
    return model, tok, desc_tok


def _load_kokoro(lang="b"):
    from kokoro import KPipeline
    return KPipeline(lang_code=lang)


def synthesize_local(cfg, text, out_wav):
    """Write one sentence of speech to out_wav (mono WAV). Provider from config tts.provider."""
    import numpy as np
    import soundfile as sf
    t = cfg["tts"]
    provider = t["provider"]
    with GPU_LOCK:
        if provider == "chatterbox":
            c = t.get("chatterbox", {})
            m = _swap("chatterbox", _load_chatterbox)
            ref = c.get("reference_wav") or None          # optional: a voice you have consent to clone
            wav = m.generate(text, audio_prompt_path=ref, exaggeration=c.get("exaggeration", 0.55),
                             cfg_weight=c.get("cfg_weight", 0.4))
            sf.write(str(out_wav), wav.squeeze().cpu().numpy(), m.sr)
        elif provider == "indic_parler":
            p = t.get("indic_parler", {})
            model, tok, desc_tok = _swap("indic_parler", _load_indic_parler)
            dev = _device()
            desc = desc_tok(p.get("description"), return_tensors="pt").to(dev)
            prompt = tok(text, return_tensors="pt").to(dev)
            gen = model.generate(input_ids=desc.input_ids, attention_mask=desc.attention_mask,
                                 prompt_input_ids=prompt.input_ids, prompt_attention_mask=prompt.attention_mask)
            sf.write(str(out_wav), gen.cpu().numpy().squeeze(), model.config.sampling_rate)
        elif provider == "kokoro":
            k = t.get("kokoro", {})
            pipe = _swap("kokoro", lambda: _load_kokoro(k.get("lang", "b")))
            parts = [audio for _, _, audio in pipe(text, voice=k.get("voice", "bf_emma"), speed=k.get("speed", 1.05))]
            sf.write(str(out_wav), np.concatenate([np.asarray(a) for a in parts]), 24000)
        else:
            raise ValueError(f"unknown local tts provider {provider}")


# ------------------------------------------------------------------ vision (Qwen2.5-VL)

def _load_qwen(name):
    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(name, torch_dtype=torch.bfloat16, device_map=_device())
    proc = AutoProcessor.from_pretrained(name, min_pixels=128 * 28 * 28, max_pixels=320 * 28 * 28)
    return model, proc


def vlm_json(cfg, system, frames, prompt, max_new_tokens=3000):
    """Ask the local vision model about a list of (label, jpeg_path) frames; returns parsed JSON."""
    from PIL import Image
    from common import extract_json
    name = cfg["local_models"].get("vlm", "Qwen/Qwen2.5-VL-7B-Instruct")
    content = []
    for label, path in frames:
        content.append({"type": "text", "text": label})
        content.append({"type": "image", "image": Image.open(path).convert("RGB")})
    content.append({"type": "text", "text": prompt + "\nReply with JSON only."})
    messages = [{"role": "system", "content": [{"type": "text", "text": system}]},
                {"role": "user", "content": content}]
    with GPU_LOCK:
        model, proc = _swap("qwen_vl", lambda: _load_qwen(name))
        from qwen_vl_utils import process_vision_info
        text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images, videos = process_vision_info(messages)
        inputs = proc(text=[text], images=images, videos=videos, padding=True, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        reply = proc.batch_decode(out[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
    return extract_json(reply)


# ------------------------------------------------------------------ text LLM (scripts + judge), replaces Claude

def _load_llm(name):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4")
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name, quantization_config=q, device_map=_device())
    return model, tok


def _load_llama_cpp(lm):
    import os
    import sys
    if sys.platform == "win32":                     # llama.cpp's CUDA build reuses the CUDA DLLs shipped with torch
        import torch
        os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama
    path = lm.get("llm_gguf_path") or hf_hub_download(lm["llm_gguf_repo"], lm["llm_gguf_file"])
    return Llama(model_path=path, n_gpu_layers=-1, n_ctx=lm.get("llm_ctx", 16384), flash_attn=True,
                 type_k=8, type_v=8, verbose=False)        # q8 KV cache: fits long prompts on a 4 GB GPU


def llm_json(cfg, system, user, max_new_tokens=None, schema=None):
    """Local Qwen3 (Apache 2.0) returning parsed JSON. Free; slower and less sharp than Claude.
    Backend llama_cpp (GGUF, fast on small GPUs, JSON-constrained) or transformers (4-bit)."""
    from common import extract_json
    lm = cfg["local_models"]
    name = lm.get("llm", "Qwen/Qwen3-14B")
    if isinstance(user, list):                      # text blocks only (no images for the text model)
        user = "\n".join(b.get("text", "") for b in user if isinstance(b, dict) and b.get("type") == "text")
    if lm.get("llm_backend") == "llama_cpp":
        with GPU_LOCK:
            llm = _swap("llm_gguf", lambda: _load_llama_cpp(lm))
            r = llm.create_chat_completion(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user + "\n\nReply with JSON only. /no_think"}],
                max_tokens=max_new_tokens or lm.get("llm_max_new_tokens", 6000), temperature=0.8, top_p=0.95,
                seed=__import__("random").randint(1, 2**31 - 1),
                response_format={"type": "json_object", **({"schema": schema} if schema else {})})
        reply = r["choices"][0]["message"]["content"]
        log("llm", f"{r['usage']['prompt_tokens']} prompt + {r['usage']['completion_tokens']} output tokens")
        if "</think>" in reply:
            reply = reply.split("</think>", 1)[1]
        return extract_json(reply)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user + "\n\nReply with JSON only."}]
    with GPU_LOCK:
        model, tok = _swap("llm", lambda: _load_llm(name))
        try:
            text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                           enable_thinking=lm.get("llm_thinking", False))
        except TypeError:                           # tokenizers without the Qwen3 thinking switch
            text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok([text], return_tensors="pt").to(model.device)
        ids = inputs.input_ids
        # Chunked prefill: feed the long prompt in pieces into the KV cache so attention never builds a
        # (prompt x prompt) matrix at once (Windows / small GPUs have no memory-efficient attention kernel).
        import torch
        from transformers import DynamicCache
        cache, chunk = DynamicCache(), lm.get("llm_prefill_chunk", 1024)
        with torch.no_grad():
            for s in range(0, ids.shape[1] - 1, chunk):
                e = min(s + chunk, ids.shape[1] - 1)
                model(input_ids=ids[:, s:e], past_key_values=cache, use_cache=True, logits_to_keep=1)
        log("llm", f"prompt {ids.shape[1]} tokens prefilled")
        out = model.generate(input_ids=ids, attention_mask=inputs.attention_mask, past_key_values=cache,
                             max_new_tokens=max_new_tokens or lm.get("llm_max_new_tokens", 7000),
                             do_sample=True, temperature=0.8, top_p=0.95)
        reply = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
    if "</think>" in reply:
        reply = reply.split("</think>", 1)[1]
    return extract_json(reply)


# ------------------------------------------------------------------ speech-to-text (Whisper)

def _load_whisper(size):
    from faster_whisper import WhisperModel
    dev = _device()
    return WhisperModel(size, device=dev, compute_type="float16" if dev == "cuda" else "int8")


def transcribe_lines(cfg, wav_path):
    """[{in, out, text}] sentence-level lines with timestamps (used for clips that carry their own speech)."""
    with GPU_LOCK:
        m = _swap("whisper", lambda: _load_whisper(cfg["local_models"].get("whisper", "large-v3")))
        segs, _ = m.transcribe(str(wav_path), vad_filter=True, language=None)
        return [{"in": round(s.start, 2), "out": round(s.end, 2), "text": s.text.strip()} for s in segs if s.text.strip()]
