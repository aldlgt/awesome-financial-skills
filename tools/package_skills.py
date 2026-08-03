#!/usr/bin/env python3
# tools/package_skills.py
# Download candidate repos as zipball and save to artifacts/skills/<owner_repo>.zip
# Config via env:
#  - GITHUB_TOKEN (required for private repo access; Actions provides it for public)
#  - MAX_DOWNLOADS (max number of repos to download, default 50)
#  - CANDIDATES_JSON (path, default candidates/all_candidates.json)
#  - SKIP_EXISTING (1 to skip if file exists)
#
# After finished, artifacts are under artifacts/skills/ (upload with upload-artifact)

import os, json, requests, pathlib, time, sys, traceback

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("SECRET_TOKEN")
MAX_DOWNLOADS = int(os.getenv("MAX_DOWNLOADS") or "50")
CANDIDATES_JSON = os.getenv("CANDIDATES_JSON") or "candidates/all_candidates.json"
SKIP_EXISTING = os.getenv("SKIP_EXISTING", "1") not in ("0", "false", "no")
OUT_DIR = pathlib.Path("artifacts/skills")
OUT_DIR.mkdir(parents=True, exist_ok=True)
HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

def read_candidates(path):
    if not os.path.exists(path):
        print("No candidates json at", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                print("candidates file not a list:", path)
                return []
    except Exception as e:
        print("Failed to read candidates:", e)
        traceback.print_exc()
        return []

def safe_filename(full_name):
    return full_name.replace("/", "_")

def download_zipball(full_name, dest_path, max_retries=3):
    # Use the API endpoint that returns a redirect to the archive
    url = f"https://api.github.com/repos/{full_name}/zipball"
    for attempt in range(1, max_retries+1):
        try:
            r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=60)
            if r.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(r.content)
                return True
            elif r.status_code in (301,302, 307,308):
                # follow redirect (requests already did if allow_redirects True)
                continue
            else:
                print(f"Failed to download {full_name}: status {r.status_code} text={r.text[:200]}")
                if r.status_code == 403:
                    # rate limit?
                    print("Maybe rate-limited or no permissions.")
                # retry with backoff
                time.sleep(2 * attempt)
        except Exception as e:
            print(f"Exception downloading {full_name}: {e}")
            traceback.print_exc()
            time.sleep(2 * attempt)
    return False

def main():
    items = read_candidates(CANDIDATES_JSON)
    if not items:
        print("No candidates found, exiting.")
        return

    # limit and dedupe by full_name
    seen = set()
    todo = []
    for it in items:
        name = it.get("full_name") or it.get("fullName") or it.get("repo") or it.get("url")
        if not name:
            continue
        # if URL provided, try to extract owner/repo
        if name.startswith("http"):
            # try to parse path
            try:
                import urllib.parse as up
                p = up.urlparse(name).path.strip("/")
                parts = p.split("/")
                if len(parts) >= 2:
                    name = f"{parts[0]}/{parts[1]}"
            except Exception:
                pass
        if name in seen:
            continue
        seen.add(name)
        todo.append({"full_name": name, "meta": it})
        if len(todo) >= MAX_DOWNLOADS:
            break

    print(f"Preparing to download {len(todo)} repos (MAX_DOWNLOADS={MAX_DOWNLOADS})")

    failed = []
    for idx, entry in enumerate(todo, start=1):
        full = entry["full_name"]
        safe = safe_filename(full)
        dest = OUT_DIR / f"{safe}.zip"
        if SKIP_EXISTING and dest.exists():
            print(f"[{idx}/{len(todo)}] Skip existing {full} -> {dest}")
            continue
        print(f"[{idx}/{len(todo)}] Downloading {full} -> {dest}")
        ok = download_zipball(full, str(dest))
        if not ok:
            print(f"Failed to download {full}")
            failed.append(entry)
        else:
            print(f"Saved {full} to {dest}")

    # If any failed, also save a small JSON with failed candidates + meta for later retry
    if failed:
        failed_path = OUT_DIR / "failed_candidates.json"
        print(f"Saving {len(failed)} failed candidates to {failed_path}")
        with failed_path.open("w", encoding="utf-8") as f:
            json.dump([e["meta"] for e in failed], f, ensure_ascii=False, indent=2)

    # Also copy/save the merged all_candidates.json for reference if exists
    try:
        merged = pathlib.Path(CANDIDATES_JSON)
        if merged.exists():
            import shutil
            shutil.copy(merged, OUT_DIR / merged.name)
    except Exception as e:
        print("Could not copy merged candidates file:", e)

    print("Done. Artifacts available under", OUT_DIR)

if __name__ == "__main__":
    main()
