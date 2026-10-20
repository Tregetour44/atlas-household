"""Build corpus/manifest.tsv: id, split, family, seed, text.
split = train (teacher corpus for the student) | heldout (whole families, eval only) | dev (step-1 audition, eval only) | sample (owner's four lines, eval only).
Order is shuffled (seed 1) so a partially generated corpus is still balanced across families."""
import glob, os, random, zlib
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "corpus")
lines = lambda p: [l.strip() for l in open(p, encoding="utf-8") if l.strip() and not l.startswith("#")]
rows = []
for split, pattern in [("train", "train/*.txt"), ("heldout", "heldout/*.txt")]:
    for p in sorted(glob.glob(os.path.join(C, pattern))):
        fam = os.path.basename(p)[:-4]
        rows += [(split, fam, t) for t in lines(p)]
rows += [("dev", "dev", t) for t in lines(os.path.join(C, "dev_sentences.txt"))]
rows += [("sample", "sample", t) for t in lines(os.path.join(C, "sample_lines.txt"))]
evals = [r for r in rows if r[0] != "train"]
train = [r for r in rows if r[0] == "train"]
random.Random(1).shuffle(train)
texts = [r[2] for r in rows]
assert len(set(texts)) == len(texts), "duplicate sentence"
heldout_texts = {r[2].lower() for r in evals}
assert not any(r[2].lower() in heldout_texts for r in train)
# Extension families (added after generation had started) are appended after everything else, unshuffled,
# so existing ids and seeds never change.
ext = [("train", os.path.basename(p)[:-4], t) for p in sorted(glob.glob(os.path.join(C, "train_ext", "*.txt"))) for t in lines(p)]
assert not any(r[2] in texts or r[2].lower() in heldout_texts for r in ext), "duplicate / held-out sentence in extension"
train += ext
# Round 2 additions: new training families (shuffled among themselves, seed 2) and new held-out lines, appended last
# so every round-1 id and seed is unchanged.
ext2 = [("train", os.path.basename(p)[:-4], t) for p in sorted(glob.glob(os.path.join(C, "train_ext2", "*.txt"))) for t in lines(p)]
random.Random(2).shuffle(ext2)
held2 = [("heldout", os.path.basename(p)[:-4], t) for p in sorted(glob.glob(os.path.join(C, "heldout_r2", "*.txt"))) for t in lines(p)]
seen = set(texts) | {r[2] for r in ext}
for r in ext2 + held2:
    assert r[2] not in seen, f"duplicate sentence: {r[2]}"
    seen.add(r[2])
held2_l = {r[2].lower() for r in held2}
assert not any(r[2].lower() in held2_l for r in train + ext2)
train += ext2 + held2  # held2 rows keep split "heldout"; they are only placed last for id stability
# Round 2, second batch (written while the first batch was generating): appended after everything, shuffled with seed 3.
ext3 = [("train", os.path.basename(p)[:-4], t) for p in sorted(glob.glob(os.path.join(C, "train_ext3", "*.txt"))) for t in lines(p)]
random.Random(3).shuffle(ext3)
for r in ext3:
    assert r[2] not in seen and r[2].lower() not in held2_l, f"duplicate / held-out sentence: {r[2]}"
    seen.add(r[2])
train += ext3
# Round 2, house add-on (owner-supplied names and reply shapes): training rows shuffled with seed 4, then held-out rows.
ext4 = [("train", os.path.basename(p)[:-4], t) for p in sorted(glob.glob(os.path.join(C, "train_ext4", "*.txt"))) for t in lines(p)]
random.Random(4).shuffle(ext4)
held3 = [("heldout", os.path.basename(p)[:-4], t) for p in sorted(glob.glob(os.path.join(C, "heldout_r3", "*.txt"))) for t in lines(p)]
held3_l = {r[2].lower() for r in held3}
for r in ext4 + held3:
    assert r[2] not in seen, f"duplicate sentence: {r[2]}"
    seen.add(r[2])
assert not any(r[2].lower() in held3_l for r in train + ext4)
train += ext4 + held3
with open(os.path.join(C, "manifest.tsv"), "w", encoding="utf-8") as f:
    f.write("id\tsplit\tfamily\tseed\ttext\n")
    for i, (split, fam, t) in enumerate(evals + train):
        cid = f"{split[:2]}{i:04d}"
        seed = zlib.crc32(cid.encode()) % 2**31  # deterministic per-clip seed; retry k uses seed + k
        f.write(f"{cid}\t{split}\t{fam}\t{seed}\t{t}\n")
print(len(evals), "eval rows,", len(train), "train rows")
