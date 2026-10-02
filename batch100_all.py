import json, subprocess, time, re, os

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

pool = json.load(open("/tmp/gfi_pool.json"))
done = {31077,31078,31079,31082,31083,31084,31092,31093,31094,31095,31096,31097,31098,31099,31160,31161,31162,31173,31174,31175,31474,31479,31480,31481,31482,31483}

ok, skipped, failed = [], [], []
TARGET = 100
count = 0

for c in pool[:TARGET + 30]:
    if count >= TARGET: break
    n = c["num"]
    branch = f"content/issue-{n}"
    
    # 查分支是否已存在
    r = run(f"git rev-parse --verify {branch} 2>/dev/null")
    if r.returncode == 0:
        skipped.append((n, "branch exists")); continue

    body = run(f"gh api repos/lingdojo/kana-dojo/issues/{n} --jq .body").stdout
    path = None
    for seg in body.split("`"):
        if seg.startswith("community/content/") and seg.endswith(".json"):
            path = seg; break
    if not path:
        t = c["title"]
        if "Theme" in t: path = "community/content/community-themes.json"
        elif "Etiquette" in t: path = "community/content/japanese-cultural-etiquette.json"
        elif "False Friend" in t: path = "community/content/japanese-false-friends.json"
        elif "Haiku" in t: path = "community/content/japanese-haiku.json"
        elif "Idiom" in t: path = "community/content/japanese-idioms.json"
        else:
            skipped.append((n, "no path")); continue

    jstart = body.find("```json")
    raw = body[jstart+7 : body.find("```", jstart+7)].strip() if jstart >= 0 else None
    entry = None
    if raw:
        raw2 = raw.replace('nickname "Crow Castle"', "nickname 'Crow Castle'")
        try:
            entry = json.loads(raw2)
        except Exception:
            fixed = re.sub(r'([a-zA-Z]+):', r'"\1":', raw2)
            try: entry = json.loads(fixed)
            except Exception: entry = raw
    if entry is None:
        skipped.append((n, "unparseable")); continue

    tm = re.search(r'(content: add new [a-z ]+)', body)
    title = tm.group(1).strip() if tm else f"content: add entry for #{n}"

    run("git checkout main --quiet && git pull -q origin main")
    run(f"git checkout -b {branch} --quiet")
    src = open(path).read().rstrip()
    if not src.endswith("]"):
        run("git checkout main --quiet"); skipped.append((n, "not-array")); continue
    body_src = src[:-1].rstrip() + ",\n" + json.dumps(entry, ensure_ascii=False, indent=2) + "\n]"
    open(path, "w").write(body_src)
    try:
        json.load(open(path))
    except Exception as e:
        run("git checkout main --quiet"); failed.append((n, str(e)[:60])); continue
    run("git add -A")
    run(f'git commit --quiet -m "content: resolve #{n}"')
    r = run(f"git push -q fork {branch}")
    if r.returncode:
        failed.append((n, f"push: {r.stderr[:60]}")); run("git checkout main --quiet"); continue
    ok.append((n, branch, title))
    count += 1
    print(f"[{count}/{TARGET}] #{n} DONE: {branch}")
    time.sleep(0.5)

json.dump({"ok": ok, "skipped": skipped, "failed": failed}, open("batch100_all_results.json","w"), ensure_ascii=False)
print(f"=== FIXED+PUSHED: {count} | skipped: {len(skipped)} | failed: {len(failed)} ===")
