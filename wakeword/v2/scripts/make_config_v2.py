#!/usr/bin/env python3
"""v2 training config: v1's make_config.py (candidate B's settings) plus the
simulated-room scene negatives (TV, music, kitchen, babble without the wake
phrase). Steps 20k @ 1e-3, 12k @ 5e-4, 8k @ 2e-4; window 6720 ms (378
frames, as v1 candidate B) in the first, aborted run; 2580 ms (240 frames) in
the run that was kept: positives are rendered 4.0 s (400 frames), so a
378-frame window always began inside the audio frontend's start-up transient
(about 1-1.5 s), and the model learned that as a cue. A 240-frame window ends
0.2 s after the phrase and starts at least 151 frames (1.5 s) into the clip.

  python -I make_config_v2.py OUT.yaml TRAIN_DIR FEAT_ROOT NEG_ROOT INLOOP_DIR [CLIP_MS]
"""
import subprocess
import sys
import os

import yaml

out, train_dir, feat, neg, inloop = sys.argv[1:6]
clip_ms = sys.argv[6] if len(sys.argv) > 6 else "2580"
v1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "make_config.py")
subprocess.check_call([sys.executable, "-I", v1, "--out", out, "--train-dir", train_dir,
                       "--pos", f"{feat}/pos", "--hardneg", f"{feat}/neg", "--neg-root", neg,
                       "--ambient-dir", inloop, "--steps", "20000", "12000", "8000",
                       "--lr", "0.001", "0.0005", "0.0002", "--clip-ms", clip_ms,
                       "--hardneg-weight", "4", "--hardneg-penalty", "2",
                       "--time-mask", "5", "--freq-mask", "5", "--eval-interval", "1000"])
cfg = yaml.safe_load(open(out))
cfg["features"].insert(2, {"features_dir": f"{feat}/scene", "sampling_weight": 3.0,
                           "penalty_weight": 1.0, "truth": False,
                           "truncation_strategy": "random", "type": "mmap"})
yaml.safe_dump(cfg, open(out, "w"), sort_keys=False)
print(open(out).read())
