import sys, time, json, torch, soundfile as sf
from qwen_tts import Qwen3TTSModel
torch.set_num_threads(int(sys.argv[4]) if len(sys.argv)>4 else 4)
instruct = sys.argv[1]; outpfx = sys.argv[2]; lines = [l.rstrip('\n').split('\t') for l in open(sys.argv[3])]
m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cpu", dtype=torch.float32)
for lid, text in lines:
    torch.manual_seed(1234)
    t=time.time(); wavs, sr = m.generate_voice_design(text=text, language="English", instruct=instruct); dt=time.time()-t
    sf.write(f"{outpfx}-{lid}.wav", wavs[0], sr)
    print(json.dumps({"id":lid,"secs":round(dt,2),"dur":round(len(wavs[0])/sr,2),"rtf":round(dt/(len(wavs[0])/sr),2)}), flush=True)
