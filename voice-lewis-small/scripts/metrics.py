"""Objective measures shared by the corpus filter and the student evaluation.
- ASR: faster-whisper small.en (int8), second opinion medium.en; text normalised with Whisper's EnglishTextNormalizer
  (vendored, Apache-2.0) so "eighty percent" and "80%" compare equal.
- Speaker similarity: SpeechBrain ECAPA-TDNN (spkrec-ecapa-voxceleb), cosine.
- Naturalness: UTMOS22 strong (SpeechMOS v1.2.0).
- Artefacts: clipping, long internal pauses, audio outside Whisper's word span, speaking rate."""
import json, os, re, sys
import numpy as np, librosa, torch

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("VLS_MODELS", "/tmp/claude-0/work/models")
sys.path.insert(0, os.path.join(HERE, "third_party"))
from english_normalizer import EnglishTextNormalizer  # noqa: E402

_norm = EnglishTextNormalizer(json.load(open(os.path.join(HERE, "third_party", "whisper_english_spelling.json"))))
_PRE = [(r"°\s*c\b", " degrees"), (r"°", " degrees"), (r"\bkwh\b", "kilowatt hours"), (r"\bkw\b", "kilowatts"),
        (r"\bkm/h\b", "kilometres an hour"), (r"\bkm\b", "kilometres"), (r"\bmm\b", "millimetres"),
        (r"\bper cent\b", "percent"), (r"\bok\b", "okay"), (r"\bo'clock\b", ""), (r"\bmum\b", "mother")]
CRITICAL = set("on off open opened closed close shut locked unlocked lock unlock not no don't isn't can't won't up down "
               "high low cancelled minus empty full late early before after".split())


def normalise(s):
    s = s.lower()
    for a, b in _PRE:
        s = re.sub(a, b, s)
    s = _norm(s)
    s = re.sub(r"\b(\d+) (\d{2})\b", r"\1:\2", s)  # "six 42" (time) vs "6:42"
    return s.replace(":00", "").split()


def wer(ref, hyp):
    import jiwer
    r, h = normalise(ref), normalise(hyp)
    if not r:
        return 0.0 if not h else 1.0
    return jiwer.wer(" ".join(r), " ".join(h) if h else "<empty>")


def critical_ok(ref, hyp):
    """Every number and critical word in the text must appear in the transcript the same number of times."""
    r, h = normalise(ref), normalise(hyp)
    crit = lambda toks: sorted(t for t in toks if re.search(r"\d", t) or t in CRITICAL)
    return crit(r) == crit(h), crit(r), crit(h)


def load16(path):
    y, _ = librosa.load(path, sr=16000, mono=True)
    return y


class Evaluator:
    def __init__(self, want=("asr", "spk", "mos"), threads=4):
        torch.set_num_threads(threads)
        self.want = set(want)
        if "spk" in self.want:
            from speechbrain.inference.speaker import EncoderClassifier
            d = os.path.join(MODELS, "ecapa")
            self.ecapa = EncoderClassifier.from_hparams(source=d, savedir=d, run_opts={"device": "cpu"})
        if "mos" in self.want:
            torch.hub.set_dir(os.path.join(MODELS, "hub"))
            self.mos = torch.hub.load(os.path.join(MODELS, "SpeechMOS"), "utmos22_strong", source="local", trust_repo=True)
        if "asr" in self.want:
            from faster_whisper import WhisperModel
            self.asr_small = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=threads)
            self._asr_med = None

    def embed(self, y):
        with torch.no_grad():
            e = self.ecapa.encode_batch(torch.tensor(y).unsqueeze(0)).squeeze()
        return (e / e.norm()).numpy()

    def utmos(self, y):
        with torch.no_grad():
            return float(self.mos(torch.tensor(y).unsqueeze(0), 16000))

    def transcribe(self, y, model="small"):
        if model == "medium":
            if self._asr_med is None:
                from faster_whisper import WhisperModel
                self._asr_med = WhisperModel("medium.en", device="cpu", compute_type="int8")
            m = self._asr_med
        else:
            m = self.asr_small
        segs, _ = m.transcribe(y, beam_size=5, word_timestamps=True, language="en", condition_on_previous_text=False)
        segs = list(segs)
        words = [w for s in segs for w in (s.words or [])]
        text = " ".join(s.text.strip() for s in segs)
        span = (words[0].start, words[-1].end) if words else (0.0, 0.0)
        return text, span


def artefacts(y, sr, span):
    """Simple signal checks on the 16 kHz waveform; span = Whisper (first word start, last word end)."""
    dur = len(y) / sr
    hop = int(0.01 * sr)
    rms = librosa.feature.rms(y=y, frame_length=4 * hop, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-8)
    thr = max(db.max() - 40, -60)
    voiced = db > thr
    idx = np.flatnonzero(voiced)
    lead = idx[0] * 0.01 if len(idx) else dur
    trail = dur - (idx[-1] + 1) * 0.01 if len(idx) else dur
    # longest silent run strictly inside the voiced region
    longest, run = 0, 0
    for v in voiced[idx[0]: idx[-1] + 1] if len(idx) else []:
        run = 0 if v else run + 1
        longest = max(longest, run)
    # energy outside the words Whisper heard (catches trailing babble / breaths / hallucinated sound)
    a, b = span
    fr = lambda t: int(t / 0.01)
    after = voiced[fr(b) + 25:] if b else voiced  # allow 250 ms tail after last word
    before = voiced[: max(fr(a) - 25, 0)]
    return dict(dur=round(dur, 2), clip_frac=float(np.mean(np.abs(y) > 0.99)), lead_sil=round(lead, 2),
                trail_sil=round(trail, 2), max_pause=round(longest * 0.01, 2),
                extra_after=round(float(after.sum()) * 0.01, 2), extra_before=round(float(before.sum()) * 0.01, 2),
                voiced_s=round(float(voiced.sum()) * 0.01, 2))
