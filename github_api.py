import os
import time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import requests

from dotenv import load_dotenv
try:
    load_dotenv()
except ImportError:
    pass

app = FastAPI()

GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}"
GITHUB_HEADERS = lambda token: {"Authorization": f"token {token}"} if token else {}

class RepoInfo(BaseModel):
    name: str
    owner: str
    description: Optional[str]
    stars: int
    forks: int
    open_issues: int
    watchers: int
    url: str
    total_downloads: int = 0
    releases_amount: int = 0
    latest_release_tag: Optional[str] = None
    

CACHE = {}
CACHE_TIMESTAMPS = {}
CACHE_TTL = 60  # seconds

def get_github_repo_info(owner: str, repo: str, token: Optional[str] = None):
    url = GITHUB_API_URL.format(owner=owner, repo=repo)
    headers = GITHUB_HEADERS(token)
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get('message', 'GitHub API error'))
    data = resp.json()

    # Fetch releases info
    releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    releases_resp = requests.get(releases_url, headers=headers)
    total_downloads = 0
    releases_amount = 0
    latest_release_tag = None
    if releases_resp.status_code == 200:
        releases = releases_resp.json()
        releases_amount = len(releases)
        if releases:
            latest_release_tag = releases[0].get("tag_name")
            for release in releases:
                for asset in release.get("assets", []):
                    total_downloads += asset.get("download_count", 0)

    return RepoInfo(
        name=data.get('name'),
        owner=data.get('owner', {}).get('login'),
        description=data.get('description'),
        stars=data.get('stargazers_count', 0),
        forks=data.get('forks_count', 0),
        open_issues=data.get('open_issues_count', 0),
        watchers=data.get('watchers_count', 0),
        url=data.get('html_url'),
        total_downloads=total_downloads,
        releases_amount=releases_amount,
        latest_release_tag=latest_release_tag,
    )

@app.get("/repo", response_model=RepoInfo)
def repo_info(owner: str = Query(...), repo: str = Query(...), token: Optional[str] = None):
    cache_key = f"{owner}/{repo}:{token}"
    now = time.time()
    # Check cache
    if cache_key in CACHE and (now - CACHE_TIMESTAMPS[cache_key] < CACHE_TTL):
        return CACHE[cache_key]
    # Fetch and cache
    info = get_github_repo_info(owner, repo, token or os.getenv("GITHUB_PAT"))
    CACHE[cache_key] = info
    CACHE_TIMESTAMPS[cache_key] = now
    return info