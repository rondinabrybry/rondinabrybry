"""Generate neon stat cards for the profile README.

Runs inside GitHub Actions. Uses only the Python standard library and the
built-in GITHUB_TOKEN, so no external stats server is needed.
Outputs: assets/stats.svg, assets/langs.svg, assets/activity.svg, assets/repo-<name>.svg
"""
import json, os, sys, urllib.request
from html import escape

USER = os.environ.get("GH_USER", "rondinabrybry")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
PINNED = os.environ.get("PINNED", "brybry-sql-practice,laravel-notifly,rich-text-editor,caveman").split(",")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

BG, BG2, CYAN, PINK, PURPLE, TEXT, MUTED = "#05010f", "#0b0628", "#00f0ff", "#ff00c8", "#8a2be2", "#e0e0ff", "#7a7aa8"
FONT = "'JetBrains Mono','Fira Code',Consolas,monospace"
LANG_COLORS = ["#00f0ff", "#ff00c8", "#8a2be2", "#27c93f", "#ffbd2e", "#ff5f56"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name description stargazerCount forkCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions totalIssueContributions
      contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
    }
  }
}"""


def fetch():
    if os.environ.get("MOCK_JSON"):
        return json.load(open(os.environ["MOCK_JSON"]))
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": USER},
    )
    data = json.load(urllib.request.urlopen(req))
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{BG2}"/></linearGradient>
  <linearGradient id="neon" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset=".5" stop-color="{PURPLE}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
  <filter id="glow"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="{CYAN}" stroke-opacity=".06"/></pattern>
</defs>
<rect width="{w}" height="{h}" rx="12" fill="url(#bg)"/>
<rect width="{w}" height="{h}" rx="12" fill="url(#grid)"/>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="12" fill="none" stroke="url(#neon)" stroke-width="1.5"/>
<g font-family="{FONT}">
<text x="22" y="34" fill="{CYAN}" font-size="15" font-weight="700" filter="url(#glow)">{escape(title)}</text>
{body}
</g>
</svg>"""


def fade(i):
    return f'opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{0.15*i:.2f}s" dur=".5s" fill="freeze"/'


def stats_card(u):
    repos = u["repositories"]["nodes"]
    c = u["contributionsCollection"]
    rows = [
        ("TOTAL STARS", sum(r["stargazerCount"] for r in repos)),
        ("COMMITS (1Y)", c["totalCommitContributions"]),
        ("PULL REQUESTS", c["totalPullRequestContributions"]),
        ("ISSUES", c["totalIssueContributions"]),
        ("PUBLIC REPOS", u["repositories"]["totalCount"]),
        ("CONTRIBS (1Y)", c["contributionCalendar"]["totalContributions"]),
    ]
    body = ""
    for i, (k, v) in enumerate(rows):
        y = 66 + i * 24
        body += f'<g {fade(i)}><text x="22" y="{y}" fill="{PINK}" font-size="12">&gt;</text>'
        body += f'<text x="38" y="{y}" fill="{MUTED}" font-size="12">{k}</text>'
        body += f'<text x="300" y="{y}" fill="{TEXT}" font-size="13" font-weight="700" text-anchor="end">{v}</text></g>'
    return frame(320, 210, "> telemetry.stats", body)


def langs_card(u):
    totals = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            totals[e["node"]["name"]] = totals.get(e["node"]["name"], 0) + e["size"]
    top = sorted(totals.items(), key=lambda x: -x[1])[:6]
    s = sum(v for _, v in top) or 1
    body, x = "", 22
    for i, (name, v) in enumerate(top):
        w = 276 * v / s
        body += f'<rect x="{x:.1f}" y="52" width="{w:.1f}" height="10" fill="{LANG_COLORS[i]}"/>'
        x += w
    for i, (name, v) in enumerate(top):
        col, row = i % 2, i // 2
        px, py = 22 + col * 150, 92 + row * 26
        body += f'<g {fade(i)}><circle cx="{px+5}" cy="{py-4}" r="5" fill="{LANG_COLORS[i]}"/>'
        body += f'<text x="{px+16}" y="{py}" fill="{TEXT}" font-size="12">{escape(name)} <tspan fill="{MUTED}">{100*v/s:.1f}%</tspan></text></g>'
    return frame(320, 210, "> top.languages", body)


def activity_card(u):
    days = [d for w in u["contributionsCollection"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]][-60:]
    W, H, pad, top, bottom = 860, 240, 40, 60, 200
    mx = max((d["contributionCount"] for d in days), default=1) or 1
    step = (W - 2 * pad) / max(len(days) - 1, 1)
    pts = [(pad + i * step, bottom - (bottom - top) * d["contributionCount"] / mx) for i, d in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad},{bottom} {line} {W-pad},{bottom}"
    grid = "".join(f'<line x1="{pad}" x2="{W-pad}" y1="{top + j*(bottom-top)/4:.1f}" y2="{top + j*(bottom-top)/4:.1f}" stroke="{PURPLE}" stroke-opacity=".25"/>' for j in range(5))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="#fff"/>' for x, y in pts)
    length = 3000
    body = f"""{grid}
<text x="{W-pad}" y="34" fill="{MUTED}" font-size="12" text-anchor="end">last 60 days · peak {mx}/day</text>
<polygon points="{area}" fill="{PURPLE}" fill-opacity=".25"/>
<polyline points="{line}" fill="none" stroke="{PINK}" stroke-width="2.2" filter="url(#glow)" stroke-dasharray="{length}" stroke-dashoffset="{length}">
  <animate attributeName="stroke-dashoffset" from="{length}" to="0" dur="2.5s" fill="freeze"/>
</polyline>
{dots}
<text x="{pad}" y="{bottom+22}" fill="{MUTED}" font-size="11">{days[0]['date'] if days else ''}</text>
<text x="{W-pad}" y="{bottom+22}" fill="{MUTED}" font-size="11" text-anchor="end">{days[-1]['date'] if days else ''}</text>"""
    return frame(W, H, "> activity.graph --live", body)


def repo_card(r):
    desc = (r["description"] or "No description yet.")
    if len(desc) > 52:
        desc = desc[:50].rstrip() + "…"
    lang = r["primaryLanguage"] or {"name": "n/a", "color": MUTED}
    body = f"""<text x="22" y="62" fill="{TEXT}" font-size="12">{escape(desc)}</text>
<circle cx="27" cy="96" r="5" fill="{lang['color'] or CYAN}"/>
<text x="38" y="100" fill="{MUTED}" font-size="12">{escape(lang['name'])}</text>
<text x="200" y="100" fill="{PINK}" font-size="12">★ {r['stargazerCount']}</text>
<text x="260" y="100" fill="{PINK}" font-size="12">⑂ {r['forkCount']}</text>"""
    return frame(400, 125, f"> {r['name']}", body)


def main():
    u = fetch()
    os.makedirs(OUT, exist_ok=True)
    files = {"stats.svg": stats_card(u), "langs.svg": langs_card(u), "activity.svg": activity_card(u)}
    by_name = {r["name"]: r for r in u["repositories"]["nodes"]}
    for name in PINNED:
        if name in by_name:
            files[f"repo-{name}.svg"] = repo_card(by_name[name])
    for f, svg in files.items():
        open(os.path.join(OUT, f), "w", encoding="utf-8").write(svg)
        print("wrote", f)


if __name__ == "__main__":
    main()
