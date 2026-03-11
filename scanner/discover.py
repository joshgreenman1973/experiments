#!/usr/bin/env python3
"""
Vital City Experiments — Monthly Tool Discovery Scanner

Scans GitHub, Hacker News, Reddit, and Twitter/X for compelling new
urban data tools and civic tech projects. Run monthly to find candidates
for the Experiments gallery.

Usage:
    python discover.py                    # Run all scanners, output to stdout
    python discover.py --output report    # Save markdown report to scanner/reports/
    python discover.py --github-only      # Only scan GitHub
    python discover.py --days 60          # Look back 60 days (default: 45)

Requires:
    pip install requests

Optional (for richer results):
    - Set GITHUB_TOKEN env var for higher API rate limits
    - Set REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET for Reddit API
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Install with: pip install requests")
    sys.exit(1)


# ── Configuration ──────────────────────────────────────────

SEARCH_QUERIES = [
    # GitHub
    "nyc open data visualization",
    "new york city map interactive",
    "nyc civic tech",
    "urban data visualization new york",
    "nyc transit data",
    "new york housing data tool",
    "nyc 311 data",
    "mta data visualization",
    "city data dashboard",
    "urban planning tool interactive",
]

GITHUB_TOPIC_QUERIES = [
    "nyc-open-data",
    "civic-tech",
    "urban-data",
    "new-york-city",
    "nyc",
    "urban-planning",
    "transit-data",
]

HN_SEARCH_TERMS = [
    "NYC data",
    "New York map",
    "civic tech",
    "urban visualization",
    "city data tool",
    "open data visualization",
    "transit visualization",
]

REDDIT_SUBREDDITS = [
    "nyc",
    "dataisbeautiful",
    "datasets",
    "MapPorn",
    "urbanplanning",
    "civictech",
]

# Tools already featured — skip these
KNOWN_URLS = {
    "311wrapped.com",
    "cannoneyed.com",
    "permitpulse.nyc",
    "nyc-civic-calendar.vercel.app",
    "subwaystories.nyc",
    "bikemap.nyc",
    "artworkmta.pages.dev",
    "eshaghoff.github.io/nyc-rent-map",
    "languagemap.nyc",
    "sidewalkwidths.nyc",
}


# ── GitHub Scanner ─────────────────────────────────────────

def scan_github(days_back=45):
    """Search GitHub for recently active repos matching urban/civic data themes."""
    results = []
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Search repos by query
    for query in SEARCH_QUERIES:
        url = (
            f"https://api.github.com/search/repositories"
            f"?q={quote_plus(query)}+pushed:>{since}"
            f"&sort=stars&order=desc&per_page=10"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                for repo in resp.json().get("items", []):
                    results.append(_parse_github_repo(repo, query))
            elif resp.status_code == 403:
                print(f"  [rate limited] GitHub search for '{query}' — set GITHUB_TOKEN for higher limits", file=sys.stderr)
                break
        except requests.RequestException as e:
            print(f"  [error] GitHub search for '{query}': {e}", file=sys.stderr)

    # Search repos by topic
    for topic in GITHUB_TOPIC_QUERIES:
        url = (
            f"https://api.github.com/search/repositories"
            f"?q=topic:{topic}+pushed:>{since}"
            f"&sort=updated&order=desc&per_page=10"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                for repo in resp.json().get("items", []):
                    results.append(_parse_github_repo(repo, f"topic:{topic}"))
        except requests.RequestException:
            pass

    return _deduplicate(results)


def _parse_github_repo(repo, source_query):
    homepage = repo.get("homepage", "") or ""
    return {
        "source": "GitHub",
        "query": source_query,
        "name": repo.get("name", ""),
        "description": repo.get("description", "") or "",
        "url": homepage if homepage.startswith("http") else repo.get("html_url", ""),
        "repo_url": repo.get("html_url", ""),
        "stars": repo.get("stargazers_count", 0),
        "language": repo.get("language", ""),
        "updated": repo.get("pushed_at", ""),
        "topics": repo.get("topics", []),
        "owner": repo.get("owner", {}).get("login", ""),
    }


# ── Hacker News Scanner ───────────────────────────────────

def scan_hackernews(days_back=45):
    """Search Hacker News (via Algolia API) for relevant Show HN and stories."""
    results = []
    since_ts = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())

    for term in HN_SEARCH_TERMS:
        for tag in ["show_hn", "story"]:
            url = (
                f"https://hn.algolia.com/api/v1/search"
                f"?query={quote_plus(term)}"
                f"&tags={tag}"
                f"&numericFilters=created_at_i>{since_ts}"
                f"&hitsPerPage=10"
            )
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    for hit in resp.json().get("hits", []):
                        results.append({
                            "source": "Hacker News",
                            "query": f"{term} ({tag})",
                            "name": hit.get("title", ""),
                            "description": "",
                            "url": hit.get("url", "") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                            "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                            "points": hit.get("points", 0),
                            "comments": hit.get("num_comments", 0),
                            "author": hit.get("author", ""),
                            "date": hit.get("created_at", ""),
                        })
            except requests.RequestException:
                pass

    return _deduplicate(results)


# ── Reddit Scanner ─────────────────────────────────────────

def scan_reddit(days_back=45):
    """Search Reddit for relevant posts (uses public JSON endpoint, no auth needed)."""
    results = []

    for subreddit in REDDIT_SUBREDDITS:
        for query in ["data tool", "interactive map", "visualization", "civic tech"]:
            url = (
                f"https://www.reddit.com/r/{subreddit}/search.json"
                f"?q={quote_plus(query)}&sort=new&restrict_sr=on&t=month&limit=10"
            )
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": "VitalCity-Scanner/1.0"},
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    for child in data.get("children", []):
                        post = child.get("data", {})
                        results.append({
                            "source": "Reddit",
                            "query": f"r/{subreddit}: {query}",
                            "name": post.get("title", ""),
                            "description": (post.get("selftext", "") or "")[:200],
                            "url": post.get("url", ""),
                            "reddit_url": f"https://reddit.com{post.get('permalink', '')}",
                            "score": post.get("score", 0),
                            "subreddit": subreddit,
                            "author": post.get("author", ""),
                            "date": datetime.fromtimestamp(
                                post.get("created_utc", 0), tz=timezone.utc
                            ).isoformat(),
                        })
            except requests.RequestException:
                pass

    return _deduplicate(results)


# ── Utilities ──────────────────────────────────────────────

def _deduplicate(results):
    """Remove duplicate URLs and already-known tools."""
    seen = set()
    unique = []
    for r in results:
        url = r.get("url", "").rstrip("/").lower()
        # Skip known tools
        if any(known in url for known in KNOWN_URLS):
            continue
        # Skip duplicates
        if url in seen or not url:
            continue
        seen.add(url)
        unique.append(r)
    return unique


def score_result(result):
    """Heuristic score: higher = more likely to be a good gallery candidate."""
    score = 0

    desc = (result.get("description", "") + " " + result.get("name", "")).lower()

    # NYC/urban relevance
    nyc_terms = ["nyc", "new york", "manhattan", "brooklyn", "queens", "bronx", "staten island", "mta", "subway"]
    urban_terms = ["urban", "civic", "city", "transit", "housing", "zoning", "311", "permit", "pedestrian"]
    for t in nyc_terms:
        if t in desc:
            score += 3
    for t in urban_terms:
        if t in desc:
            score += 2

    # Interactive/visual
    viz_terms = ["interactive", "map", "visualization", "dashboard", "tool", "explore"]
    for t in viz_terms:
        if t in desc:
            score += 2

    # Engagement signals
    score += min(result.get("stars", 0) // 5, 10)
    score += min(result.get("points", 0) // 10, 10)
    score += min(result.get("score", 0) // 20, 5)

    # Has a live website (not just a repo)
    url = result.get("url", "")
    if url and "github.com" not in url and "reddit.com" not in url:
        score += 5

    return score


def generate_report(github_results, hn_results, reddit_results, days_back):
    """Generate a markdown report of findings."""
    all_results = github_results + hn_results + reddit_results
    scored = [(score_result(r), r) for r in all_results]
    scored.sort(key=lambda x: x[0], reverse=True)

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Experiments Gallery — Discovery Report",
        f"",
        f"**Scanned:** {today}",
        f"**Lookback:** {days_back} days",
        f"**Sources:** GitHub ({len(github_results)} results), "
        f"Hacker News ({len(hn_results)} results), "
        f"Reddit ({len(reddit_results)} results)",
        f"**Total unique candidates:** {len(all_results)}",
        f"",
        f"---",
        f"",
        f"## Top Candidates",
        f"",
        f"Ranked by relevance score (NYC focus, interactivity, engagement).",
        f"",
    ]

    for i, (score, r) in enumerate(scored[:25], 1):
        lines.append(f"### {i}. {r['name']}")
        lines.append(f"")
        lines.append(f"- **Score:** {score}")
        lines.append(f"- **Source:** {r['source']} — {r.get('query', '')}")
        lines.append(f"- **URL:** {r['url']}")
        if r.get("repo_url"):
            lines.append(f"- **Repo:** {r['repo_url']}")
        if r.get("hn_url"):
            lines.append(f"- **HN Discussion:** {r['hn_url']}")
        if r.get("reddit_url"):
            lines.append(f"- **Reddit:** {r['reddit_url']}")
        lines.append(f"- **Description:** {r.get('description', 'N/A')}")
        if r.get("stars"):
            lines.append(f"- **Stars:** {r['stars']}")
        if r.get("points"):
            lines.append(f"- **HN Points:** {r['points']}")
        if r.get("owner") or r.get("author"):
            lines.append(f"- **Creator:** {r.get('owner') or r.get('author')}")
        lines.append(f"")

    lines.extend([
        "---",
        "",
        "## Next Steps",
        "",
        "1. Review top candidates above",
        "2. Visit each URL and evaluate: Is it live? Interactive? Well-designed?",
        "3. Check if it's built by an individual or small team",
        "4. For approved tools, add to the `tools` array in `index.html`",
        "5. Move any retired tools to `archived: true` in the same array",
        "",
    ])

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scan for new urban data tools for the Vital City Experiments gallery."
    )
    parser.add_argument("--days", type=int, default=45, help="Days to look back (default: 45)")
    parser.add_argument("--output", choices=["stdout", "report"], default="stdout",
                        help="Output format: stdout (default) or save markdown report")
    parser.add_argument("--github-only", action="store_true", help="Only scan GitHub")
    parser.add_argument("--hn-only", action="store_true", help="Only scan Hacker News")
    parser.add_argument("--reddit-only", action="store_true", help="Only scan Reddit")
    args = parser.parse_args()

    scan_all = not (args.github_only or args.hn_only or args.reddit_only)

    print("Vital City Experiments — Tool Discovery Scanner", file=sys.stderr)
    print(f"Looking back {args.days} days...\n", file=sys.stderr)

    github_results, hn_results, reddit_results = [], [], []

    if scan_all or args.github_only:
        print("Scanning GitHub...", file=sys.stderr)
        github_results = scan_github(args.days)
        print(f"  Found {len(github_results)} candidates", file=sys.stderr)

    if scan_all or args.hn_only:
        print("Scanning Hacker News...", file=sys.stderr)
        hn_results = scan_hackernews(args.days)
        print(f"  Found {len(hn_results)} candidates", file=sys.stderr)

    if scan_all or args.reddit_only:
        print("Scanning Reddit...", file=sys.stderr)
        reddit_results = scan_reddit(args.days)
        print(f"  Found {len(reddit_results)} candidates", file=sys.stderr)

    report = generate_report(github_results, hn_results, reddit_results, args.days)

    if args.output == "report":
        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = reports_dir / f"discovery-{datetime.now().strftime('%Y-%m-%d')}.md"
        filename.write_text(report)
        print(f"\nReport saved to {filename}", file=sys.stderr)
    else:
        print(report)

    total = len(github_results) + len(hn_results) + len(reddit_results)
    print(f"\nDone. {total} total candidates found.", file=sys.stderr)


if __name__ == "__main__":
    main()
