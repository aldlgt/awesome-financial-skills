#!/usr/bin/env python3
# 简单示例：使用 GitHub API 搜索候选项并写入 candidates/<category>.json
# 运行环境需安装 PyGithub：pip install PyGithub

import os, json
from github import Github

TOK = os.getenv("GITHUB_TOKEN")
if not TOK:
    raise SystemExit("请在环境变量 GITHUB_TOKEN 中设置 token（在 Actions 中使用 secrets.GITHUB_TOKEN）")

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

for cat, q in queries.items():
    try:
        results = g.search_repositories(q, sort="updated", order="desc")
    except Exception as e:
        print(f"Search error for {cat}: {e}")
        continue
    items = []
    for repo in results[:50]:
        items.append({
            "full_name": repo.full_name,
            "url": repo.html_url,
            "desc": repo.description,
            "stars": repo.stargazers_count,
            "updated_at": repo.updated_at.isoformat(),
        })
    out = f"candidates/{cat}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"{cat}: saved {len(items)} to {out}")