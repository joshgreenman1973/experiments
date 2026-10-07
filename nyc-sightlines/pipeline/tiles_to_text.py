"""Artifact hosting serves text but not arbitrary binary, so each gzip'd tile ships as base64 in a .txt file.
Usage: python tiles_to_text.py TILES_DIR   (replaces every .bin with a .txt)"""
import sys, os, base64
d = sys.argv[1]
for f in sorted(os.listdir(d)):
    if f.endswith(".bin"):
        p = os.path.join(d, f)
        open(p[:-4] + ".txt", "w").write(base64.b64encode(open(p, "rb").read()).decode())
        os.remove(p)
print(len([f for f in os.listdir(d) if f.endswith(".txt")]), "text tiles")
