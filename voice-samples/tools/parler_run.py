import sys, torch
from transformers import AutoTokenizer
from parler_tts import ParlerTTSForConditionalGeneration
from common import run
torch.set_num_threads(4)
repo, model_tag = sys.argv[1], sys.argv[2]
DESC = {
 "storyteller": "A man with a refined British accent speaks slowly and warmly in a gently melancholic, storytelling tone, very clear audio.",
 "dry-narrator": "A middle-aged man with a deep, smooth British accent speaks at a slow, unhurried pace with a warm, dry and slightly wry tone. The recording is very high quality, close-sounding and clear, with no background noise.",
}
tags = sys.argv[3].split(",")
model = ParlerTTSForConditionalGeneration.from_pretrained(repo).eval()
tok = AutoTokenizer.from_pretrained(repo)
sr = model.config.sampling_rate
for tag in tags:
    d = tok(DESC[tag], return_tensors="pt")
    def synth(text):
        torch.manual_seed(1234)
        p = tok(text, return_tensors="pt")
        with torch.inference_mode():
            a = model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
                               prompt_input_ids=p.input_ids, prompt_attention_mask=p.attention_mask)
        return a.cpu().numpy().squeeze(), sr
    run(model_tag, tag, synth, note=DESC[tag])
