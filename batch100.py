import json, subprocess, time, re, sys

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

pool = json.load(open("gfi_pool.json"))
# 已做过的不重复（我们已提交过 PR 的 issue）
DONE = {31077,31078,31079,31082,31083,31084,31092,31093,31094,31095,31096,31097,31098,31099,31159,31160,31161,31162}
TARGET = 100
BATCH = [c for c in pool if c["num"] not in DONE][:TARGET + 10]  # 多取 10 个容错

TITLES = {}
ok, skipped, failed = [], [], []
pr_created = 0

for c in BATCH:
    n = c["num"]
    # 1. 撞车复查：有链接 PR 就跳过
    tl = run(f'gh api repos/lingdojo/kana-dojo/issues/{n}/timeline --jq \'[.[] | select(.event=="cross-referenced") | .source.issue | select(.pull_request != null) | "#\(.number)"] | unique | join(",")\'').stdout.strip()
    if tl:
        skipped.append((n, f"PRs: {tl}"))
        continue
    # 2. 抓规格
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
        raw2 = raw.replace('nickname "Crow Castle"', "nickname 'Crow Castle'")
        try:
            entry = json.loads(raw2)
        except Exception:
            fixed = re.sub(r'([a-zA-Z]+):', r'"\1":', raw2)
            try: entry = json.loads(fixed)
            except Exception: entry = raw  # 字符串数组条目
    if entry is None:
        skipped.append((n, "no/complex spec")); continue

    title_m = re.search(r'(content: add new [a-z ]+)', body)
    title = title_m.group(1) if title_m else f"content: add entry for #{n}"
    branch = f"content/issue-{n}"

    # 3. 修：分支 + 拼接 + 校验 + 提交 + 推送
    run("git checkout main --quiet && git pull -q origin main")
    run(f"git checkout -b {branch} --quiet")
    src = open(path).read().rstrip()
    if not src.endswith("]"):
        run(f"git checkout main --quiet"); skipped.append((n, "not-array")); continue
    body_src = src[:-1].rstrip()
    body_src += ",\n" + json.dumps(entry, ensure_ascii=False, indent=2) + "\n]"
    open(path, "w").write(body_src)
    try:
        data = json.load(open(path))
    except Exception as e:
        run("git checkout main --quiet"); failed.append((n, f"invalid: {e}")); continue
    run("git add -A")
    run(f'git commit --quiet -m "content: resolve #{n}"')
    r = run(f"git push -q fork {branch}")
    if r.returncode:
        failed.append((n, f"push: {r.stderr[:80]}")); run("git checkout main --quiet"); continue

    # 4. 尝试建 PR（限流则留给重试）
    r = run(f'gh pr create --repo lingdojo/kana-dojo --base main --head LetMeSleep8h:{branch} --title "{title}" --body "Closes #{n}\\n\\nAdded the specified entry to {path}. JSON validated."')
    out = (r.stdout.strip() or r.stderr.strip()[:60])
    if "pull/" in out:
        pr_created += 1
        ok.append((n, out, path))
        print(f"[{n}] CREATED {out}")
    else:
        ok.append((n, "STAGED (pr blocked)", path))
        print(f"[{n}] STAGED | {out[:40]}")
    time.sleep(1.5)

json.dump({"ok": ok, "skipped": skipped, "failed": failed, "pr_created": pr_created}, open("batch100_results.json", "w"), ensure_ascii=False)
print(f"=== FIXED+STAGED: {len(ok)} | skipped: {len(skipped)} | failed: {len(failed)} | PRs created now: {pr_created} ===")
