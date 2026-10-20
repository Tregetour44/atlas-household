"""WAV -> loudness-matched MP3, as voice-scout did (EBU R128 loudnorm to -18 LUFS, true peak -1.5 dB, mono, 24 kHz,
96 kbps), but two-pass: measure, apply the exact gain, then a -1.5 dBFS peak limiter, so short clips land on -18
too (single-pass loudnorm left them ~2 LU quiet). Usage: to_mp3.py OUT_DIR [--join NAME] wav...   (--join also writes NAME.mp3: the clips in order
with 0.5 s of silence between them). Needs ffmpeg on PATH."""
import json
import os
import subprocess
import sys
import tempfile


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def loudnorm(src: str, dst: str) -> None:
    target = "I=-18:TP=-1.5:LRA=11"
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = json.loads(p.stderr[p.stderr.rindex("{"):])
    gain = -18.0 - float(m["input_i"])
    ff("-i", src, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.84:level=false,aresample=24000", "-ac", "1", "-ar", "24000",
       dst)


def main() -> None:
    out, args = sys.argv[1], sys.argv[2:]
    join = None
    if args[:1] == ["--join"]:
        join, args = args[1], args[2:]
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ff("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.5", f"{tmp}/gap.wav")
        listing = []
        for i, wav in enumerate(args):
            name = os.path.basename(wav)[:-4]
            norm = f"{tmp}/{i:03d}.wav"
            loudnorm(wav, norm)
            ff("-i", norm, "-codec:a", "libmp3lame", "-b:a", "96k", f"{out}/{name}.mp3")
            listing += ([f"file '{tmp}/gap.wav'"] if listing else []) + [f"file '{norm}'"]
        if join:
            with open(f"{tmp}/list.txt", "w") as f:
                f.write("\n".join(listing) + "\n")
            ff("-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt", "-codec:a", "libmp3lame", "-b:a", "96k",
               f"{out}/{join}.mp3")


if __name__ == "__main__":
    main()
