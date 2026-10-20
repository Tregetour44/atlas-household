import sys, json, time, numpy as np, onnxruntime as ort, collections, os, glob
SCR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vocab=json.load(open(f"{SCR}/dl/pt/config.json"))["vocab"]; pack=np.load(f"{SCR}/work/en_GB-fablemix.npy")
ps="ˌɪts twˈɛntiθɹˌiː dɪɡɹˈiːz ˌWtsˈId, ðə bˈatəɹiz at sˈɪkstiˌAt pəsˈɛnt, and ðə dˈɪʃwˌɒʃə fˈɪnɪʃɪz at kwˈɔːtə pˈɑːst nˈIn."
ids=np.array([[0]+[vocab[c] for c in ps if c in vocab]+[0]],np.int64)
so=ort.SessionOptions(); so.intra_op_num_threads=4; so.inter_op_num_threads=1; so.enable_profiling=True; so.profile_file_prefix=f"{SCR}/out/prof"
s=ort.InferenceSession(sys.argv[1], so, providers=["CPUExecutionProvider"])
feed={"input_ids":ids,"style":pack[len(ps)-1],"speed":np.array([0.95],np.float32)}
for i in range(3): t=time.perf_counter(); s.run(None,feed); print("run", round(time.perf_counter()-t,3))
p=s.end_profiling(); d=json.load(open(p)); agg=collections.Counter()
for e in d:
    if e.get("cat")=="Node" and e["name"].endswith("_kernel_time"): agg[e["args"]["op_name"]]+=e["dur"]
tot=sum(agg.values()); print("total kernel ms/3runs", tot/1000); [print(k, round(v/tot*100,1)) for k,v in agg.most_common(10)]
os.remove(p)
