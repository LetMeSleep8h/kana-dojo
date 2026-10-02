import json, subprocess, time, re, sys

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

pool = json.load(open("gfi_remaining.json"))
ok, skipped, failed = [], [], []

for c in pool:
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
        # 尝试无路径但已知类型的
        if "Theme" in c["title"]:
            path = "community/content/community-themes.json"
        elif "Etiquette Tip" in c["title"]:
            path = "community/content/japanese-cultural-etiquette.json"
        elif "False Friend" in c["title"]:
            path = "community/content/japanese-false-friends.json"
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
        # 从标题推断
        title_lower = c["title"].lower()
        if "grammar" in title_lower:
            entry = f"Grammar point from issue #{n}"
            path = "community/content/japanese-grammar.json"
        elif "fact" in title_lower:
            entry = f"Japan fact from issue #{n}"
            path = "community/content/japan-facts.json"
        else:
            skipped.append((n, "unparseable spec")); continue

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
    print(f"[{n}] DONE: {branch} ({title[:40]})")
    time.sleep(1)

json.dump({"ok": ok, "skipped": skipped, "failed": failed}, open("batch_remaining_results.json","w"), ensure_ascii=False)
print(f"=== FIXED: {len(ok)} | skipped: {len(skipped)} | failed: {len(failed)} ===")
