from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
CREATIVE_H3_SKILLS = (
    "3d-animation-short-generator",
    "brand-promo-video-generator",
    "co-op-game-intro-generator",
    "handdrawn-live-video-generator",
    "minimalist-product-ad-generator",
    "music-video-subtitle-generator",
    "paper-collage-explainer-generator",
    "papercraft-stop-motion-explainer",
)
SOURCES = (
    {
        "name": "MiniMax H3 h3-prompt-writing",
        "repo": "MiniMax-AI/MiniMax-H3",
        "path": "skills/h3-prompt-writing",
        "manifest": ROOT / "official_skills" / "H3_SOURCE.json",
        "commit_field": "commit",
    },
    {
        "name": "MiniMax Music 3 music-caption-rewriter",
        "repo": "MiniMax-AI/MiniMax-Music3",
        "path": "skills/music-caption-rewriter",
        "manifest": ROOT / "official_skills" / "SOURCE.json",
        "commit_field": "commit",
    },
) + tuple(
    {
        "name": f"MiniMax H3 {skill}",
        "repo": "MiniMax-AI/MiniMax-H3",
        "path": f"skills/{skill}",
        "manifest": ROOT / "web" / "js" / "assets" / "official-previews" / "manifest.json",
        "commit_field": "source_commit",
    }
    for skill in CREATIVE_H3_SKILLS
)


class DriftCheckError(RuntimeError):
    pass


def latest_commit(session: requests.Session, repo: str, path: str) -> str:
    response = session.get(
        f"https://api.github.com/repos/{repo}/commits",
        params={"path": path, "per_page": 1},
        headers={"Accept": "application/vnd.github+json", "User-Agent": "t8-prompt-enhancer-drift-check/1"},
        timeout=(10, 30),
    )
    if response.status_code != 200:
        raise DriftCheckError(f"GitHub returned HTTP {response.status_code} for {repo}/{path}")
    data = response.json()
    if not isinstance(data, list) or not data or not isinstance(data[0].get("sha"), str):
        raise DriftCheckError(f"GitHub returned no commit for {repo}/{path}")
    return data[0]["sha"]


def pinned_contains_upstream(session: requests.Session, repo: str, upstream: str, pinned: str) -> bool:
    """Return true when the pinned repository snapshot already contains upstream.

    A manifest intentionally pins a reviewed repository commit, while GitHub's
    path-scoped endpoint returns the newest commit that *changed the path*.
    Those SHAs are normally different even when the path content is current.
    Comparing ancestry prevents a permanent false-positive drift alert.
    """
    if upstream == pinned:
        return True
    response = session.get(
        f"https://api.github.com/repos/{repo}/compare/{upstream}...{pinned}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "t8-prompt-enhancer-drift-check/1"},
        timeout=(10, 30),
    )
    if response.status_code != 200:
        raise DriftCheckError(f"GitHub compare returned HTTP {response.status_code} for {repo}")
    status = response.json().get("status")
    if status not in {"identical", "ahead", "behind", "diverged"}:
        raise DriftCheckError(f"GitHub compare returned an invalid status for {repo}")
    return status in {"identical", "ahead"}


def check_sources(session: requests.Session | None = None) -> list[dict[str, Any]]:
    owns_session = session is None
    active = session or requests.Session()
    results: list[dict[str, Any]] = []
    try:
        for source in SOURCES:
            manifest = json.loads(source["manifest"].read_text(encoding="utf-8"))
            pinned = str(manifest[source["commit_field"]])
            current = latest_commit(active, source["repo"], source["path"])
            covers_upstream = pinned_contains_upstream(active, source["repo"], current, pinned)
            results.append({
                "name": source["name"],
                "repo": source["repo"],
                "path": source["path"],
                "pinned": pinned,
                "upstream": current,
                "pinned_contains_upstream": covers_upstream,
                "drift": not covers_upstream,
            })
    finally:
        if owns_session:
            active.close()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Check pinned official Skill snapshots for upstream drift.")
    parser.add_argument("--fail-on-drift", action="store_true")
    args = parser.parse_args()
    results = check_sources()
    print(json.dumps({"schema_version": "t8-upstream-skill-drift/v1", "sources": results}, indent=2))
    if args.fail_on_drift and any(item["drift"] for item in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
