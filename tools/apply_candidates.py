#!/usr/bin/env python3
# tools/apply_candidates.py
# Read candidates/*.json and append new items into categories/*.md (one-line entries).
# Default: DRY_RUN mode (will not modify repo). To do real run set DRY_RUN=0 in env.
#
# Requires: PyGithub (for creating PR), git (available in Actions), and GITHUB_TOKEN & GITHUB_REPOSITORY env.

import os, json, datetime, subprocess, pathlib, traceback
from typing import List

DRY_RUN = os.getenv("DRY_RUN", "1").lower() not in ("0", "false", "no")
TOK = os.getenv("GITHUB_TOKEN")
REPO_ENV = os.getenv("GITHUB_REPOSITORY")  # owner/repo
SEEN_FILE = ".data/seen.json"
CANDIDATES_DIR = "candidates"
CATEGORIES_DIR = "categories"
BRANCH_PREFIX = "updates"

if not REPO_ENV:
    raise SystemExit("GITHUB_REPOSITORY env not set")
owner, repo_name = REPO_ENV.split("/")

# mapping from candidate json file base to category md relative path
# ensure keys match your queries keys in fetch_candidates.py
MAPPING = {
    "research_industrial": f"{CATEGORIES_DIR}/research-industrial.md",
    "research_pharma": f"{CATEGORIES_DIR}/research-trading.md",  # adjust if desired
    "research_trading_credit_bond": f"{CATEGORIES_DIR}/research-trading.md",
    "research_credit_cams": f"{CATEGORIES_DIR}/research-credit.md",
    "data_aggregator": f"{CATEGORIES_DIR}/data-aggregator.md",
    "data_indicators_semiconductor": f"{CATEGORIES_DIR}/data-indicators.md",
    "data_knowledge": f"{CATEGORIES_DIR}/data-knowledge.md",
}

def load_seen() -> set:
    p = pathlib.Path(SEEN_FILE)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()

def save_seen(seen: set):
    p = pathlib.Path(SEEN_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(list(seen)), ensure_ascii=False, indent=2), encoding="utf-8")

def format_entry(item: dict) -> str:
    # Format one-line entry. You can customize text here.
    name = item.get("full_name")
    url = item.get("url")
    desc = item.get("desc") or ""
    stars = item.get("stars") or 0
    updated = item.get("updated_at") or ""
    # 来源写成 url 以便你以后批量下载/追踪
    return f"- [{name}]({url}) — {desc} (★{stars}) 来源：{url}。最后更新时间：{updated}"

def append_to_file(path: str, lines: List[str]):
    p = pathlib.Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# 自动更新的分类\n\n", encoding="utf-8")
    # Read existing to avoid simple duplicates
    existing = p.read_text(encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        for ln in lines:
            if ln.strip() and ln not in existing:
                f.write("\n" + ln)

def git(cmd_args, check=True):
    print("git", *cmd_args)
    subprocess.run(["git"] + cmd_args, check=check)

def create_branch_and_commit(files_to_commit: List[str], branch_name: str, commit_message: str):
    # create branch, add files, commit, push
    git(["checkout", "-b", branch_name])
    git(["config", "user.email", "actions@github.com"])
    git(["config", "user.name", "github-actions"])
    git(["add"] + files_to_commit)
    git(["commit", "-m", commit_message])
    git(["push", "--set-upstream", "origin", branch_name])

def create_pr_via_api(branch_name: str, title: str, body: str):
    # create a PR using gh CLI if available, or print instruction
    # gh CLI is convenient; if not installed fallback to printing the intended PR command
    try:
        subprocess.run(["gh", "pr", "create", "--title", title, "--body", body, "--base", "main", "--head", branch_name], check=True)
        print("PR created via gh CLI")
    except Exception as e:
        print("gh CLI not available or failed to create PR. Please create PR manually with:")
        print(f"Branch: {branch_name}")
        print(f"Title: {title}")
        print(f"Body:\n{body}")

def main():
    seen = load_seen()
    changed_files = set()
    new_seen = set()

    if not os.path.isdir(CANDIDATES_DIR):
        print("No candidates directory, nothing to do.")
        return

    now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for fname in os.listdir(CANDIDATES_DIR):
        if not fname.endswith(".json"):
            continue
        key = fname.replace(".json", "")
        cat_file = MAPPING.get(key)
        if not cat_file:
            print(f"No mapping for {key}, skipping.")
            continue
        path = os.path.join(CANDIDATES_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
        # filter out seen
        new_items = [it for it in items if it.get("full_name") not in seen]
        if not new_items:
            print(f"{key}: no new candidates, skip")
            continue

        lines = [format_entry(it) for it in new_items]
        print(f"Will append {len(lines)} lines to {cat_file}:")
        for l in lines[:5]:
            print("  ", l)
        if DRY_RUN:
            print("[DRY RUN] not modifying files.")
        else:
            append_to_file(cat_file, lines)
            changed_files.add(cat_file)
            # mark seen
            for it in new_items:
                new_seen.add(it.get("full_name"))

    if not changed_files:
        print("No file changes to commit.")
        return

    if DRY_RUN:
        print("[DRY RUN] Done. No commits were made. To apply, set DRY_RUN=0 and re-run.")
        return

    # make branch, commit, push, create PR
    branch = f"{BRANCH_PREFIX}/{now}"
    commit_message = f"Auto-update categories with new candidates {now}"
    files_list = sorted(list(changed_files))
    try:
        create_branch_and_commit(files_list, branch, commit_message)
        pr_title = f"[Auto-update] add discovered skills {now}"
        pr_body = "Automated update: appended discovered skills to category files. Please review."
        create_pr_via_api(branch, pr_title, pr_body)
    except Exception:
        print("Error during git/push/PR creation:")
        traceback.print_exc()

    # persist seen
    seen |= new_seen
    save_seen(seen)
    print("Done.")

if __name__ == "__main__":
    main()
