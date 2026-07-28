#!/usr/bin/env python3
# create_candidate_prs.py (robust)
# 根据 candidates/*.json 创建 proposal 文件并打开 candidate PR。
# 运行环境需安装 PyGithub：pip install PyGithub

import os
import json
import datetime
import time
import pathlib
import traceback
from github import Github

DRY_RUN = os.getenv("DRY_RUN", "1").lower() not in ("0", "false", "no")  # 默认 DRY_RUN true for safety
SEEN_FILE = ".data/seen.json"
CANDIDATES_DIR = "candidates"
PROPOSALS_DIR = "proposals"

TOK = os.getenv("GITHUB_TOKEN")
REPO_ENV = os.getenv("GITHUB_REPOSITORY")  # 格式 owner/repo
if not TOK:
    raise SystemExit("请在环境变量 GITHUB_TOKEN 中设置 token")
if not REPO_ENV:
    raise SystemExit("GITHUB_REPOSITORY 环境变量未设置（在 Actions 中自动存在）")

# init github client (try new auth style)
try:
    import github
    Auth = getattr(github, "Auth", None)
    if Auth is not None and hasattr(Auth, "Token"):
        g = Github(auth=Auth.Token(TOK))
    else:
        g = Github(TOK)
except Exception:
    g = Github(TOK)

owner, repo_name = REPO_ENV.split("/")
repo = g.get_repo(f"{owner}/{repo_name}")

def load_seen():
    p = pathlib.Path(SEEN_FILE)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()

def save_seen(seen):
    p = pathlib.Path(SEEN_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(list(seen)), ensure_ascii=False, indent=2), encoding="utf-8")

seen = load_seen()

if not os.path.isdir(CANDIDATES_DIR):
    print('No candidates directory, exit (not an error)')
    raise SystemExit(0)

now = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

def make_proposal_md(cat, items):
    header = f"# Candidate proposal for {cat}\n\nGenerated: {now} UTC\n\n"
    lines = [header]
    for it in items:
        lines.append(f"- [{it.get('full_name')}]({it.get('url')}) — {it.get('desc') or ''} (★ {it.get('stars')})\n")
    return "\n".join(lines)

for fname in os.listdir(CANDIDATES_DIR):
    if not fname.endswith('.json'):
        continue
    cat = fname.replace('.json','')
    path = os.path.join(CANDIDATES_DIR, fname)
    with open(path, 'r', encoding='utf-8') as f:
        try:
            items = json.load(f)
        except Exception as e:
            print(f"Failed to parse {path}: {e}")
            continue
    # filter out already-seen repos
    new_items = [it for it in items if it.get('full_name') not in seen]
    if not new_items:
        print(f"{cat}: no new candidates, skip")
        continue

    branch = f"candidates/{cat}-{now}"
    base_branch = repo.default_branch

    content = make_proposal_md(cat, new_items)
    proposal_path = f"{PROPOSALS_DIR}/{cat}-{now}.md"

    if DRY_RUN:
        print(f"[DRY RUN] Would create branch {branch} with proposal {proposal_path} containing {len(new_items)} items")
        # mark as seen for dry-run? No — keep unseen for real run
        continue

    # create branch
    try:
        sb = repo.get_branch(base_branch)
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=sb.commit.sha)
        print(f"Created branch {branch} from {base_branch}")
    except Exception as e:
        print(f"Could not create branch {branch}: {e}")
        traceback.print_exc()
        continue

    # create proposal file
    try:
        repo.create_file(proposal_path, f"Add proposal {cat} {now}", content, branch=branch)
        print(f"Created proposal file {proposal_path} on branch {branch}")
    except Exception as e:
        print(f"Could not create file {proposal_path}: {e}")
        traceback.print_exc()
        # try to cleanup branch?
        continue

    # create PR
    try:
        pr = repo.create_pull(title=f"[Candidate] {cat} - {now}",
                              body=f"Automated candidate proposal for {cat}. Please review.",
                              head=branch, base=base_branch)
        print(f"Created PR: {pr.html_url}")
        # add label (create if missing)
        label_name = "candidate"
        try:
            pr.add_to_labels(label_name)
        except Exception:
            try:
                repo.create_label(label_name, "f9d0c4", "Candidate discovered by automation")
                pr.add_to_labels(label_name)
            except Exception as e:
                print("Label create/add failed:", e)
        # mark seen for all items in this proposal
        for it in new_items:
            seen.add(it.get("full_name"))
        save_seen(seen)
        # small sleep to avoid API bursts
        time.sleep(1)
    except Exception as e:
        print(f"Could not create PR for branch {branch}: {e}")
        traceback.print_exc()
        continue
