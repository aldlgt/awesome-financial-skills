#!/usr/bin/env python3
# tools/fetch_candidates.py
# Read search_params.json from repo root, construct a GitHub Search query,
# fetch repositories (safe iteration, dedupe) and write candidates/all_candidates.json.
#
# Env:
#  - GITHUB_TOKEN (recommended, Actions provides secrets.GITHUB_TOKEN)
#  - MAX_RESULTS (optional override of max_results in JSON)
#
# Output:
#  - candidates/all_candidates.json  (list of repo metadata objects)

import os
import json
import time
import traceback
from pathlib import Path

# Try to import PyGithub with new auth style if available
try:
    import github
    Auth = getattr(github, "Auth", None)
    from github import Github
except Exception:
    # fallback: try plain import
    from github import Github
    Auth = None

SEARCH_FILE = Path("search_params.json")
OUT_DIR = Path("candidates")
OUT_FILE = OUT_DIR / "all_candidates.json"

# Default fallback params
DEFAULT_PARAMS = {
    "keywords": ["semiconductor", "innovation"],
    "date_from": None,
    "date_to": None,
    "stars": 10,
    "max_results": 200
}

def load_search_params():
    if SEARCH_FILE.exists():
        try:
            cfg = json.loads(SEARCH_FILE.read_text(encoding="utf-8"))
            # validate minimal shape
            return {**DEFAULT_PARAMS, **cfg}
        except Exception as e:
            print("Failed to parse search_params.json:", e)
            traceback.print_exc()
            return DEFAULT_PARAMS.copy()
    return DEFAULT_PARAMS.copy()

def build_query(params):
    kws = params.get("keywords") or []
    # sanitize and quote multi-word keywords
    parts = []
    for k in kws:
        k = k.strip()
        if not k:
            continue
        if " " in k or '"' in k:
            # ensure quotes around phrase
            parts.append('"' + k.replace('"', '') + '"')
        else:
            parts.append(k)
    if not parts:
        base = ""
    else:
        base = " OR ".join(parts)
    q_parts = []
    if base:
        q_parts.append(f"({base}) in:readme,description")
    # stars
    stars = params.get("stars")
    if isinstance(stars, int) and stars > 0:
        q_parts.append(f"stars:>={stars}")
    # pushed range
    df = params.get("date_from")
    dt = params.get("date_to")
    if df and dt:
        # use range form: pushed:YYYY-MM-DD..YYYY-MM-DD
        q_parts.append(f"pushed:{df}..{dt}")
    # combine
    q = " ".join(q_parts).strip()
    if not q:
        q = ""  # conservative fallback: empty search (should be avoided)
    return q

def get_github_client(token):
    if not token:
        raise SystemExit("GITHUB_TOKEN is required in environment")
    try:
        # try new auth style if available
        if Auth is not None and hasattr(Auth, "Token"):
            return Github(auth=Auth.Token(token))
    except Exception:
        pass
    return Github(token)

def safe_repo_info(repo):
    # extract safe serializable fields
    return {
        "full_name": getattr(repo, "full_name", None),
        "url": getattr(repo, "html_url", None),
        "desc": getattr(repo, "description", None),
        "stars": getattr(repo, "stargazers_count", None),
        "updated_at": getattr(repo, "updated_at", None).isoformat() if getattr(repo, "updated_at", None) else None,
        "language": getattr(repo, "language", None),
        "fork": getattr(repo, "fork", False),
        "archived": getattr(repo, "archived", False)
    }

def main():
    params = load_search_params()
    # allow env override for max_results
    try:
        max_results = int(os.getenv("MAX_RESULTS", str(params.get("max_results", 200))))
    except Exception:
        max_results = params.get("max_results", 200)

    q = build_query(params)
    if not q:
        print("Constructed empty query from params — aborting.")
        return

    print("Search query:", q)
    print("Max results:", max_results)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("WARNING: GITHUB_TOKEN not set. Actions usually supplies secrets.GITHUB_TOKEN.")
    g = get_github_client(token)

    # perform search
    try:
        results = g.search_repositories(q, sort="updated", order="desc")
    except Exception as e:
        print("Search call failed:", e)
        traceback.print_exc()
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    seen = set()
    count = 0
    for repo in results:
        # stop when reached max
        if count >= max_results:
            break
        try:
            # skip forks/archived quickly
            if getattr(repo, "fork", False) or getattr(repo, "archived", False):
                continue
            info = safe_repo_info(repo)
            key = info.get("full_name") or info.get("url")
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(info)
            count += 1
        except Exception as e:
            print("Error processing repo:", e)
            traceback.print_exc()
            continue

    # write output
    try:
        with OUT_FILE.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"WROTE {len(items)} items to {OUT_FILE}")
    except Exception as e:
        print("Failed to write output:", e)
        traceback.print_exc()

if __name__ == "__main__":
    main()
