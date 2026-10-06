import json, subprocess, time, re, os
os.chdir("/Users/pengzeyu/.zcode/workspace/default/contributor-work/kana-dojo")
POOL = "/Users/pengzeyu/.zcode/workspace/default/contributor-work/kana-dojo/gfi_pool.json"
def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)
pool = json.load(open(POOL))
print(f"pool loaded: {len(pool)} issues")
for c in pool[:3]:
    print(f"  #{c['num']}")
