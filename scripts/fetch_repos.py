#!/usr/bin/env python3
"""Fetch public repo metadata from GitHub for the SBP partner organizations."""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

ORGS = ["genepattern", "igvteam", "uclahs-cds", "GSEA-MSigDB"]
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "_data", "repositories.json")
API_BASE = "https://api.github.com"

FIELDS = [
    "name", "full_name", "html_url", "description",
    "language", "stargazers_count", "forks_count",
    "watchers_count", "open_issues_count", "pushed_at",
    "created_at", "updated_at", "topics", "archived", "disabled",
]


def get_headers():
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sbp-aggregator-bot",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    else:
        print("WARNING: No GH_PAT or GITHUB_TOKEN found; using unauthenticated requests (60 req/hr limit).", file=sys.stderr)
    return headers


def fetch_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            if remaining != "?" and int(remaining) < 10:
                print(f"WARNING: Only {remaining} API requests remaining.", file=sys.stderr)
            return json.loads(resp.read().decode()), resp.headers.get("Link", "")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} fetching {url}: {e.reason}", file=sys.stderr)
        if e.code == 403:
            print("Rate limited or forbidden. Check your GH_PAT secret.", file=sys.stderr)
        raise


def get_org_repos(org, headers):
    repos = []
    page = 1
    while True:
        url = f"{API_BASE}/orgs/{org}/repos?type=public&per_page=100&page={page}"
        print(f"  Fetching {org} page {page}...", file=sys.stderr)
        data, link_header = fetch_json(url, headers)
        if not data:
            break
        repos.extend(data)
        if 'rel="next"' not in link_header:
            break
        page += 1
        time.sleep(0.25)
    return repos


def extract(repo, org):
    license_name = None
    if repo.get("license"):
        license_name = repo["license"].get("spdx_id") or repo["license"].get("name")
    return {
        "org": org,
        "name": repo["name"],
        "full_name": repo["full_name"],
        "html_url": repo["html_url"],
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "license": license_name or "",
        "stargazers_count": repo.get("stargazers_count", 0),
        "forks_count": repo.get("forks_count", 0),
        "watchers_count": repo.get("watchers_count", 0),
        "open_issues_count": repo.get("open_issues_count", 0),
        "pushed_at": repo.get("pushed_at") or "",
        "created_at": repo.get("created_at") or "",
        "topics": repo.get("topics") or [],
        "archived": repo.get("archived", False),
    }


def main():
    headers = get_headers()
    all_repos = []

    for org in ORGS:
        print(f"Fetching repos for {org}...", file=sys.stderr)
        try:
            raw = get_org_repos(org, headers)
            for r in raw:
                if not r.get("disabled"):
                    all_repos.append(extract(r, org))
            print(f"  {len(raw)} repos fetched for {org}.", file=sys.stderr)
        except Exception as e:
            print(f"ERROR fetching {org}: {e}", file=sys.stderr)

    all_repos.sort(key=lambda r: (r["org"].lower(), r["name"].lower()))

    output = os.path.realpath(OUTPUT_PATH)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_repos, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {len(all_repos)} repos to {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
