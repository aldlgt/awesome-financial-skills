#!/usr/bin/env python3
# 根据 candidates/*.json 为每个非空分类在仓库中创建 proposal 文件并打开 candidate PR。
# 运行环境需安装 PyGithub：pip install PyGithub

import os, json, datetime
from github import Github

TOK = os.getenv("GITHUB_TOKEN")
REPO_ENV = os.getenv("GITHUB_REPOSITORY")  # 格式 owner/repo
if not TOK:
    raise SystemExit("请在环境变量 GITHUB_TOKEN 中设置 token")
if not REPO_ENV:
    raise SystemExit("GITHUB_REPOSITORY 环境变量未设置（在 Actions 中自动存在）")

g = Github(TOK)
owner, repo_name = REPO_ENV.split("/")
repo = g.get_repo(f"{owner}/{repo_name}")

candidates_dir = 'candidates'
if not os.path.isdir(candidates_dir):
    print('No candidates directory, exit')
    raise SystemExit(0)

now = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
def make_proposal_md(cat, items):
    header = f"# Candidate proposal for {cat}\n\nGenerated: {now} UTC\n\n"
    lines = [header]
    for it in items:
        lines.append(f"- [{it.get('full_name')}]({it.get('url')}) — {it.get('desc') or ''} (★ {it.get('stars')})\n")
    return "\n".join(lines)

for fname in os.listdir(candidates_dir):
    if not fname.endswith('.json'):
        continue
    cat = fname.replace('.json','')
    path = os.path.join(candidates_dir, fname)
    with open(path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    if not items:
        print(f"{cat}: no candidates, skip")
        continue
    branch = f"candidates/{cat}-{now}"
    base_branch = repo.default_branch
    try:
        sb = repo.get_branch(base_branch)
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=sb.commit.sha)
        print(f"Created branch {branch} from {base_branch}")
    except Exception as e:
        print(f"Could not create branch {branch}: {e}")
        continue

    proposal_path = f"proposals/{cat}-{now}.md"
    content = make_proposal_md(cat, items)
    try:
        repo.create_file(proposal_path, f"Add proposal {cat} {now}", content, branch=branch)
        print(f"Created proposal file {proposal_path} on branch {branch}")
    except Exception as e:
        print(f"Could not create file {proposal_path}: {e}")
        continue

    try:
        pr = repo.create_pull(title=f"[Candidate] {cat} - {now}", body=f"Automated candidate proposal for {cat}. Please review.", head=branch, base=base_branch)
        print(f"Created PR: {pr.html_url}")
    except Exception as e:
        print(f"Could not create PR for branch {branch}: {e}")
