#!/usr/bin/env python3
"""v2: synthesise positives / hard negatives with more voices and accents.

Engines (all synthetic, open licences, checked in TRAINING.md):
  piper   Piper ONNX voices. Multi-speaker models (VCTK, ARU) are edited once
          so the speaker embedding is an input: a clip's voice is one speaker
          or a SLERP mix of two speakers of the same split, as v1 does with
          LibriTTS-R. Single-speaker voices are used as they are.
  kokoro  Kokoro-82M (ONNX). A clip's voice is one Kokoro voice or a linear
          blend of two voices of the same split.

Voices are split per engine in a plan file (JSON: engine, model, voices per
split, mix probability, length-scale base). Templates and their splits come
from tmpl_build.build_templates_v2 (v1 templates keep v1's splits).
Output matches synth.py: 16 kHz WAVs in <out>/<split>/ and <out>/meta.csv.

  python -I synth_onnx.py --plan plans/vctk.json --kind positive --counts 800,100,100 \
      --out /data/v2/pos_vctk_w0 --seed 1 --family-weights au=1,au2=3,...
"""
import argparse
import csv
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tmpl_build import SPLITS, build_templates_v2  # noqa: E402


def write_wav(path, a16):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(a16.tobytes())


def slerp(a, b, t):
    an, bn = a / np.linalg.norm(a), b / np.linalg.norm(b)
    omega = np.arccos(np.clip(np.dot(an, bn), -1, 1))
    if omega < 1e-6:
        return (1 - t) * a + t * b
    return (np.sin((1 - t) * omega) * a + np.sin(t * omega) * b) / np.sin(omega)


class PiperEngine:
    """Piper ONNX. For multi-speaker models the emb_g Gather is replaced by an input."""

    def __init__(self, model):
        import onnx
        import onnxruntime as ort
        self.cfg = json.load(open(model + ".json", encoding="utf-8"))
        self.rate = self.cfg["audio"]["sample_rate"]
        self.id_map = self.cfg["phoneme_id_map"]
        self.spk_map = self.cfg.get("speaker_id_map") or {}
        m = onnx.load(model)
        self.emb = None
        if self.spk_map:
            inits = {i.name: i for i in m.graph.initializer}
            node = next(n for n in m.graph.node if n.op_type == "Gather" and n.input[0] == "emb_g.weight")
            self.emb = onnx.numpy_helper.to_array(inits["emb_g.weight"]).astype(np.float32)
            out = node.output[0]
            m.graph.node.remove(node)
            m.graph.node.append(onnx.helper.make_node("Identity", ["g_vec"], [out]))
            m.graph.input.append(onnx.helper.make_tensor_value_info(
                "g_vec", onnx.TensorProto.FLOAT, [1, self.emb.shape[1]]))
            sid = next(i for i in m.graph.input if i.name == "sid")
            m.graph.input.remove(sid)
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("SYNTH_THREADS", "1"))
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(m.SerializeToString(), so, providers=["CPUExecutionProvider"])

    def ids(self, phonemes):
        # Piper's phonemes_to_ids: BOS, then each phoneme followed by PAD, then EOS.
        out = list(self.id_map["^"]) + list(self.id_map["_"])
        for p in phonemes:
            if p == "ɘ" and p not in self.id_map:
                p = "ə"
            if p in self.id_map:
                out += list(self.id_map[p]) + list(self.id_map["_"])
        return out + list(self.id_map["$"])

    def voice(self, v1, v2, w):
        if self.emb is None:
            return None
        a = self.emb[self.spk_map[v1]]
        return a if v1 == v2 else slerp(a, self.emb[self.spk_map[v2]], w)

    def synth(self, phonemes, voice_vec, length_scale, noise_scale, noise_w):
        ids = np.array([self.ids(phonemes)], dtype=np.int64)
        feeds = {"input": ids, "input_lengths": np.array([ids.shape[1]], dtype=np.int64),
                 "scales": np.array([noise_scale, length_scale, noise_w], dtype=np.float32)}
        if voice_vec is not None:
            feeds["g_vec"] = voice_vec[None, :].astype(np.float32)
        audio = self.sess.run(None, feeds)[0].squeeze()
        return audio, self.rate


class KokoroEngine:
    def __init__(self, model):
        from kokoro_onnx import Kokoro
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("SYNTH_THREADS", "1"))
        so.inter_op_num_threads = 1
        sess = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
        self.k = Kokoro.from_session(sess, os.path.join(os.path.dirname(model), "voices-v1.0.bin"))
        self.voices = np.load(os.path.join(os.path.dirname(model), "voices-v1.0.bin"))

    def voice(self, v1, v2, w):
        a = self.voices[v1]
        return a if v1 == v2 else (1 - w) * a + w * self.voices[v2]

    def synth(self, phonemes, voice_vec, length_scale, noise_scale, noise_w):
        ph = phonemes.replace("ɘ", "ə")
        audio, rate = self.k.create(ph, voice=voice_vec, speed=float(1.0 / length_scale),
                                    is_phonemes=True)
        return audio, rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--kind", choices=["positive", "negative"], required=True)
    ap.add_argument("--counts", required=True, help="clips per split: TRAIN,VALIDATION,TEST")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--family-weights", default=None)
    ap.add_argument("--template-set", choices=["v2", "v2new"], default="v2")
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--probe-texts", default=None,
                    help="'|'-separated texts: a probe set of exactly these phrases (every split's "
                         "count applies), phonemized by v1's hard-negative espeak voices")
    args = ap.parse_args()

    plan = json.load(open(args.plan))
    rng = np.random.default_rng(args.seed)
    eng = (PiperEngine if plan["engine"] == "piper" else KokoroEngine)(plan["model"])
    templates, tsplit = build_templates_v2(args.kind)
    if args.probe_texts:
        from tmpl_build import EspeakPhonemizer, T
        ph = EspeakPhonemizer()
        templates, tsplit = [], {}
        for ti, text in enumerate(args.probe_texts.split("|")):
            for vi, voice in enumerate(T.HARD_NEGATIVE_VOICES):
                p = " ".join("".join(x) for x in ph.phonemize(voice, text))
                tid = f"prw{ti:02d}{vi}"
                templates.append({"template_id": tid, "group": "probe_weak", "family": text,
                                  "text": text, "phonemes": p})
                for s in SPLITS:
                    tsplit.setdefault(s, {})[tid] = s
    if args.template_set == "v2new":
        templates = [t for t in templates if "2_" in t["template_id"]]
    if args.probe_texts:
        by_split = {s: list(templates) for s in SPLITS}
    else:
        by_split = {s: [t for t in templates if tsplit[t["template_id"]] == s] for s in SPLITS}
    fam_w = None
    if args.family_weights:
        fam_w = {k: float(v) for k, v in (x.split("=") for x in args.family_weights.split(","))}

    def pick_template(split):
        pool = by_split[split]
        if not fam_w:
            return pool[rng.integers(len(pool))]
        fams = sorted({t["family"] for t in pool if fam_w.get(t["family"], 0) > 0})
        w = np.array([fam_w[f] for f in fams])
        fam = fams[rng.choice(len(fams), p=w / w.sum())]
        sub = [t for t in pool if t["family"] == fam]
        return sub[rng.integers(len(sub))]

    out = Path(args.out)
    for s in SPLITS:
        (out / s).mkdir(parents=True, exist_ok=True)
    fields = ["file", "split", "kind", "template_id", "group", "family", "text", "phonemes",
              "engine", "speaker_1", "speaker_2", "slerp_weight", "length_scale", "noise_scale",
              "noise_scale_w", "duration_s"]
    meta_f = open(out / "meta.csv", "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(meta_f, fieldnames=fields)
    writer.writeheader()
    counts = dict(zip(SPLITS, (int(x) for x in args.counts.split(","))))
    base = float(plan.get("length_scale_base", 1.0))
    idx, made, t0 = args.start_index, 0, time.time()
    for split in SPLITS:
        voices = plan["voices"].get(split, [])
        if counts[split] and not voices:
            sys.exit(f"plan has no {split} voices")
        for _ in range(counts[split]):
            tmpl = pick_template(split)
            slowest = 1.15 if "," in tmpl["phonemes"] else 1.5
            ls = float(rng.uniform(0.75, slowest))
            ns = float(rng.uniform(0.4, 0.9))
            nw = float(rng.uniform(0.5, 1.0))
            v1 = voices[rng.integers(len(voices))]
            mix = len(voices) > 1 and rng.random() < plan.get("mix_prob", 0.6)
            v2 = voices[rng.integers(len(voices))] if mix else v1
            w = float(rng.uniform(0.0, 1.0)) if v2 != v1 else 0.0
            audio, rate = eng.synth(tmpl["phonemes"], eng.voice(v1, v2, w), ls * base, ns, nw)
            a = np.asarray(audio, dtype=np.float64)
            peak = np.max(np.abs(a)) + 1e-9
            a = a / peak * 0.9 * 32767  # level is randomised later (augmentation gain)
            g = np.gcd(16000, rate)
            a16 = resample_poly(a, 16000 // g, rate // g)
            a16 = np.trim_zeros(np.clip(np.round(a16), -32768, 32767).astype(np.int16))
            name = f"{args.kind[:3]}_{idx:07d}.wav"
            write_wav(out / split / name, a16)
            writer.writerow({
                "file": f"{split}/{name}", "split": split, "kind": args.kind,
                "template_id": tmpl["template_id"], "group": tmpl["group"], "family": tmpl["family"],
                "text": tmpl["text"], "phonemes": tmpl["phonemes"], "engine": plan["name"],
                "speaker_1": v1, "speaker_2": v2, "slerp_weight": round(w, 4),
                "length_scale": round(ls * base, 4), "noise_scale": round(ns, 4),
                "noise_scale_w": round(nw, 4), "duration_s": round(len(a16) / 16000, 4)})
            idx += 1
            made += 1
            if made % 200 == 0:
                meta_f.flush()
                print(f"{plan['name']} {args.kind}: {made} clips, {made / (time.time() - t0):.1f}/s",
                      flush=True)
    meta_f.close()
    print(f"done: {made} clips in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
