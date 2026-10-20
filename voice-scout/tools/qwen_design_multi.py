import sys, time, json, torch, soundfile as sf
from qwen_tts import Qwen3TTSModel
torch.set_num_threads(4)
descs = json.load(open(sys.argv[1])); outdir = sys.argv[2]; lines = [l.rstrip('\n').split('\t') for l in open(sys.argv[3])]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1234
m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cpu", dtype=torch.float32)
for name, ins in descs.items():
    for lid, text in lines:
        torch.manual_seed(seed)
        t=time.time(); wavs, sr = m.generate_voice_design(text=text, language="English", instruct=ins); dt=time.time()-t
        sf.write(f"{outdir}/{name}-{lid}.wav", wavs[0], sr)
        print(json.dumps({"voice":name,"id":lid,"secs":round(dt,2),"dur":round(len(wavs[0])/sr,2),"rtf":round(dt/(len(wavs[0])/sr),2)}), flush=True)
