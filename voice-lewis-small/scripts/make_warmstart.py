"""Resume-from-here helper (the full 846 MB Lightning checkpoint is too big for the repo).
  pack:   make_warmstart.py pack  <full_student.ckpt> <out_generator_fp16.pt>
          -> generator weights only (model_g.*), fp16, ~47 MB, plus global_step for the record.
  merge:  make_warmstart.py merge <generator_fp16.pt> <base_piper.ckpt> <out_warmstart.ckpt>
          -> a checkpoint for `--model.warmstart_ckpt`: student generator + the public base's discriminator.
The optimiser state is not kept, so a continued run starts with a fresh optimiser (as the first run did)."""
import sys, torch

mode = sys.argv[1]
if mode == "pack":
    ck = torch.load(sys.argv[2], map_location="cpu", weights_only=False)
    g = {k: v.half() if v.is_floating_point() else v for k, v in ck["state_dict"].items() if k.startswith("model_g.")}
    torch.save({"state_dict": g, "global_step": ck["global_step"], "epoch": ck["epoch"]}, sys.argv[3])
elif mode == "merge":
    g = torch.load(sys.argv[2], map_location="cpu", weights_only=True)
    base = torch.load(sys.argv[3], map_location="cpu", weights_only=False)
    sd = {k: v for k, v in base["state_dict"].items() if not k.startswith("model_g.")}
    sd.update({k: v.float() if v.is_floating_point() else v for k, v in g["state_dict"].items()})
    base["state_dict"] = sd
    for k in ("optimizer_states", "lr_schedulers", "loops", "callbacks"):
        base.pop(k, None)
    torch.save(base, sys.argv[4])
else:
    raise SystemExit(__doc__)
