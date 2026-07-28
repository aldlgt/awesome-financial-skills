#!/usr/bin/env python3
# fetch_candidates.py (robust)
# 使用 PyGithub 搜索候选仓库并写入 candidates/<category>.json
# 依赖: PyGithub
# 先在本地用: pip install PyGithub
import os
import json
import time
import traceback

from github import Github

TOK = os.getenv("GITHUB_TOKEN")
if not TOK:
    raise SystemExit("请在环境变量 GITHUB_TOKEN 中设置 token（在 Actions 中使用 secrets.GITHUB_TOKEN）")

# Prefer the new auth API if available, otherwise fallback
try:
    # PyGithub v2+ exposes github.Auth (this may raise if older version)
    import github
    Auth = getattr(github, "Auth", None)
    if Auth is not None and hasattr(Auth, "Token"):
        g = Github(auth=Auth.Token(TOK))
    else:
        g = Github(TOK)
except Exception:
    # fallback
    g = Github(TOK)

queries = {
    "research_industrial": 'semiconductor "国内替代" in:readme,description',
    "research_pharma": '创新药 OR "新药" in:readme,description',
    "research_trading_credit_bond": 'credit bond pricing OR "信用债" in:readme,description',
    "research_credit_cams": 'CAMS OR "主体信用" in:readme,description',
    "data_aggregator": 'research aggregator OR "投研聚合" in:readme,description',
    "data_indicators_semiconductor": 'semiconductor "行业指标" in:readme,description',
    "data_knowledge": 'knowledge base OR "知识检索" in:readme,description',
}

os.makedirs("candidates", exist_ok=True)

MAX_PER_CAT = 50
RETRY_SECONDS = 3
MAX_RETRIES = 3

for cat, q in queries.items():
    tries = 0
    while True:
        try:
            results = g.search_repositories(q, sort="updated", order="desc")
            break
        except Exception as e:
            tries += 1
            print(f"Search error for {cat} (attempt {tries}): {e}")
            traceback.print_exc()
            if tries >= MAX_RETRIES:
                print(f"Giving up query {cat} after {tries} tries")
                results = []
                break
            time.sleep(RETRY_SECONDS * tries)

    items = []
    count = 0
    # iterate safely, avoid slicing on PaginatedList which can cause index errors
    try:
        for repo in results:
            if count >= MAX_PER_CAT:
                break
            try:
                # skip forks/archived quickly
                if getattr(repo, "fork", False) or getattr(repo, "archived", False):
                    continue
                items.append({
                    "full_name": repo.full_name,
                    "url": repo.html_url,
                    "desc": repo.description,
                    "stars": repo.stargazers_count,
                    "updated_at": getattr(repo, "updated_at", None).isoformat() if getattr(repo, "updated_at", None) else None,
                })
                count += 1
            except Exception as e:
                print("Error extracting repo info:", e)
                traceback.print_exc()
                continue
    except Exception as e:
        print(f"Iterating results failed for {cat}: {e}")
        traceback.print_exc()

    out = f"candidates/{cat}.json"
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"{cat}: saved {len(items)} to {out}")
    except Exception as e:
        print(f"Could not write {out}: {e}")
        traceback.print_exc()
