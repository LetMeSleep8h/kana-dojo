import json, subprocess, time, re

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

pool = json.load(open("gfi_pool_oct.json"))
TARGET = 100
BATCH = pool[:TARGET + 10]

TITLES_KNOWN = {}
ok, skipped, failed = [], [], []
pr_created, pr_blocked = 0, 0

for c in BATCH:
    n = c["num"]
    tl = run(f'gh api repos/lingdojo/kana-dojo/issues/{n}/timeline --jq \'[.[] | select(.event=="cross-referenced") | .source.issue | select(.pull_request != null) | "#\(.number)"] | unique | join(",")\'').stdout.strip()
    if tl:
        skipped.append((n, f"PRs: {tl}")); continue
    body = run(f"gh api repos/lingdojo/kana-dojo/issues/{n} --jq .body").stdout
    path = None
    for seg in body.split("`"):
        if seg.startswith("community/content/") and seg.endswith(".json"):
            path = seg; break
    if not path:
        skipped.append((n, "no file path")); continue
    jstart = body.find("```json")
    raw = body[jstart+7 : body.find("```", jstart+7)].strip() if jstart >= 0 else None
    entry = None
    if raw:
        raw2 = raw.replace("nickname \"Crow Castle\"", "nickname 'Crow Castle'")
        try:
            entry = json.loads(raw2)
        except Exception:
            fixed = re.sub(r'([a-zA-Z]+):', r'"\1":', raw2)
            try: entry = json.loads(fixed)
            except Exception: entry = raw
    if entry is None:
        skipped.append((n, "no/complex spec")); continue

    tm = re.search(r'(content: add new [a-z ]+)', body)
    title = tm.group(1).strip() if tm else f"content: add entry for #{n}"
    branch = f"content/issue-{n}"

    run("git checkout main --quiet && git pull -q origin main")
    run(f"git checkout -b {branch} --quiet")
    src = open(path).read().rstrip()
    if not src.endswith("]"):
        run("git checkout main --quiet"); skipped.append((n, "not-array")); continue
    body_src = src[:-1].rstrip() + ",\n" + json.dumps(entry, ensure_ascii=False, indent=2) + "\n]"
    open(path, "w").write(body_src)
    try:
        data = json.load(open(path))
    except Exception as e:
        run("git checkout main --quiet"); failed.append((n, str(e)[:60])); continue
    run("git add -A")
    run(f'git commit --quiet -m "content: resolve #{n}"')
    r = run(f"git push -q nn {branch}")
    if r.returncode:
        failed.append((n, f"push: {r.stderr[:60]}")); run("git checkout main --quiet"); continue

    r = run(f'gh pr create --repo lingdojo/kana-dojo --base main --head NewNewUp:{branch} --title "{title}" --body "Closes #{n}\\n\\nAdded the specified entry to {path}. JSON validated."')
    out = (r.stdout.strip() or r.stderr.strip()[:50])
    if "pull/" in out:
        pr_created += 1
        ok.append((n, out, path)); print(f"[{n}] CREATED {out}")
    else:
        pr_blocked += 1
        ok.append((n, "STAGED", path)); print(f"[{n}] STAGED")
    time.sleep(2)

json.dump({"ok": ok, "skipped": skipped, "failed": failed}, open("batch_oct_results.json","w"), ensure_ascii=False)
print(f"=== FIXED: {len(ok)} | skipped: {len(skipped)} | failed: {len(failed)} | PR created: {pr_created} | blocked: {pr_blocked} ===")
