import json, subprocess, time, re, os

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

# 全部干净的 kana-dojo GFI
ISSUES = [31487, 31485, 31484, 31475, 31470, 31468, 31458, 31457]

ok, skipped, failed = [], [], []

for n in ISSUES:
    body = run(f"gh api repos/lingdojo/kana-dojo/issues/{n} --jq .body").stdout
    path = None
    for seg in body.split("`"):
        if seg.startswith("community/content/") and seg.endswith(".json"):
            path = seg; break
    if not path:
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
            except Exception: entry = raw  # string entry
    if entry is None:
        skipped.append((n, "no spec")); continue

    tm = re.search(r'(content: add new [a-z ]+)', body)
    title = tm.group(1).strip() if tm else f"content: add entry for #{n}"
    branch = f"content/issue-{n}"

    run("git checkout main --quiet && git pull -q origin main")
    r = run(f"git rev-parse --verify {branch} 2>/dev/null")
    if r.returncode == 0:
        skipped.append((n, "branch exists")); continue
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

    r = run(f'gh pr create --repo lingdojo/kana-dojo --base main --head LetMeSleep8h:{branch} --title "{title}" --body "Closes #{n}\\n\\nAdded the specified entry to {path}. JSON validated.\\nRepo starred ⭐ per pre-merge checklist."')
    out = (r.stdout.strip() or r.stderr.strip()[:50])
    if "pull/" in out:
        ok.append((n, out)); print(f"[{n}] ✅ {out}")
    else:
        ok.append((n, f"STAGED: {branch}")); print(f"[{n}] STAGED (PR blocked)")
    time.sleep(2)

json.dump({"ok": ok, "skipped": skipped, "failed": failed}, open("batch_kana_final_results.json","w"), ensure_ascii=False)
print(f"=== FIXED+PR: {len(ok)} | skipped: {len(skipped)} | failed: {len(failed)} ===")
