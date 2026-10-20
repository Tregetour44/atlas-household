import sys, json, os
sys.path.insert(0, "evaltools"); os.environ["VLS_MODELS"] = "evaltools/models"
import metrics
from faster_whisper import WhisperModel
m = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=2)
for f in sys.argv[1:]:
    y = metrics.load16(f); segs, _ = m.transcribe(y, beam_size=5, language="en", condition_on_previous_text=False)
    print(os.path.basename(f), "|", " ".join(s.text.strip() for s in segs))
