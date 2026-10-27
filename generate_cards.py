"""
Genera las tarjetas de estadísticas del perfil con una paleta propia.
Solo usa la librería estándar de Python. Lo ejecuta el workflow
.github/workflows/profile-cards.yml y guarda los SVG en profile-cards/.
"""
import json
import math
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

# ---------------- Paleta (cartel retro americano: rojo / azul marino / crema) ----------------
C = {
    "bg": "#FAE3AC",        # papel crema
    "ink": "#01344F",       # azul marino: bordes, sombra y texto
    "title": "#D12128",     # rojo cartel
    "text": "#01344F",
    "muted": "#4F6B7A",
    "moss": "#01344F",      # acento secundario
    "grid": "#E6C987",      # crema más oscuro para pistas y ejes
}
SLICES = ["#D12128", "#01344F", "#C99A3E", "#4C7A96", "#8C1419", "#E07A5F"]
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
DISPLAY = "'Arial Black', 'Segoe UI Black', Impact, 'Helvetica Neue', sans-serif"
UTC_OFFSET = -5  # Colombia
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

USERNAME = os.environ.get("GH_USERNAME", "WilliamSanchezR")
OUT_DIR = os.environ.get("OUT_DIR", "profile-cards")


# ---------------- Datos ----------------
def gql(query, variables):
    token = os.environ["GH_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


Q_USER = """
query($login: String!) {
  user(login: $login) {
    id name login createdAt
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    contributionsCollection {
      totalCommitContributions restrictedContributionsCount
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

Q_REPOS = """
query($login: String!, $id: ID!, $after: String) {
  user(login: $login) {
    repositories(first: 50, after: $after, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name stargazerCount
        primaryLanguage { name }
        defaultBranchRef { target { ... on Commit {
          history(first: 100, author: { id: $id }) { nodes { committedDate } }
        } } }
      }
    }
  }
}"""


def fetch():
    user = gql(Q_USER, {"login": USERNAME})["user"]
    repos, after, total = [], None, 0
    while True:
        page = gql(Q_REPOS, {"login": USERNAME, "id": user["id"], "after": after})["user"]["repositories"]
        total = page["totalCount"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]

    cc = user["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]

    by_repo_lang, by_commit_lang, hours, stars = Counter(), Counter(), [0] * 24, 0
    for repo in repos:
        stars += repo["stargazerCount"]
        lang = (repo["primaryLanguage"] or {}).get("name")
        if lang:
            by_repo_lang[lang] += 1
        target = (repo.get("defaultBranchRef") or {}).get("target") or {}
        commits = (target.get("history") or {}).get("nodes", [])
        for c in commits:
            t = datetime.fromisoformat(c["committedDate"].replace("Z", "+00:00"))
            hours[(t + timedelta(hours=UTC_OFFSET)).hour] += 1
        if lang and commits:
            by_commit_lang[lang] += len(commits)

    return {
        "name": user["name"] or user["login"],
        "login": user["login"],
        "since": user["createdAt"][:4],
        "repos": total,
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "days": days,
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "lang_repo": by_repo_lang.most_common(5),
        "lang_commit": by_commit_lang.most_common(5),
        "hours": hours,
    }


# ---------------- Dibujo ----------------
def halftone(x0, x1, y0, y1, color, step=7):
    """Trama de puntos que crecen hacia la derecha, como la impresión de un cartel viejo."""
    dots = []
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            r = 0.4 + 2.3 * (x - x0) / max(x1 - x0, 1)
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}"/>')
            x += step
        y += step
    return f'<g fill="{color}" opacity="0.45">{"".join(dots)}</g>'


def card(w, h, title, body, label):
    # Tarjeta de papel con borde de tinta, sombra dura desplazada y cabecera roja
    cw, ch, band = w - 6, h - 6, 48
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">
<style>
  text {{ font-family: {FONT}; }}
  .t {{ font-family: {DISPLAY}; font-size: 19px; font-weight: 900; fill: {C['bg']}; letter-spacing: .3px; }}
  .x {{ font-size: 14px; fill: {C['text']}; }}
  .m {{ font-size: 11px; fill: {C['muted']}; }}
  .v {{ font-family: {DISPLAY}; font-size: 14px; font-weight: 900; fill: {C['text']}; }}
</style>
<clipPath id="k"><rect x="1.5" y="1.5" width="{cw}" height="{ch}" rx="16"/></clipPath>
<rect x="6" y="6" width="{cw - 1}" height="{ch - 1}" rx="16" fill="{C['ink']}"/>
<rect x="1.5" y="1.5" width="{cw}" height="{ch}" rx="16" fill="{C['bg']}"/>
<g clip-path="url(#k)">
  <rect x="0" y="0" width="{w}" height="{band}" fill="{C['title']}"/>
  {halftone(cw - 110, cw - 14, 9, band - 6, C['bg'])}
  <line x1="0" y1="{band}" x2="{w}" y2="{band}" stroke="{C['ink']}" stroke-width="2.5"/>
</g>
<rect x="1.5" y="1.5" width="{cw}" height="{ch}" rx="16" fill="none" stroke="{C['ink']}" stroke-width="2.5"/>
<text class="t" x="22" y="32">{escape(title)}</text>
{body}
</svg>"""


def donut(items, cx, cy, r=48, sw=22):
    # Arcos reales (no stroke-dasharray), separados por una línea del color del papel
    total = sum(v for _, v in items) or 1
    ro, ri = r + sw / 2, r - sw / 2
    if len(items) == 1:
        return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{SLICES[0]}" stroke-width="{sw}"/>'
                f'<circle cx="{cx}" cy="{cy}" r="{ro}" fill="none" stroke="{C["ink"]}" stroke-width="2"/>')

    def pt(rad, a):
        return f"{cx + rad * math.cos(a):.2f},{cy + rad * math.sin(a):.2f}"

    out, a0 = [], -math.pi / 2
    for i, (_, v) in enumerate(items):
        a1 = a0 + 2 * math.pi * v / total
        big = 1 if a1 - a0 > math.pi else 0
        out.append(
            f'<path d="M{pt(ro, a0)} A{ro},{ro} 0 {big} 1 {pt(ro, a1)} L{pt(ri, a1)} A{ri},{ri} 0 {big} 0 {pt(ri, a0)} Z" '
            f'fill="{SLICES[i % len(SLICES)]}" stroke="{C["bg"]}" stroke-width="2.5" stroke-linejoin="round"/>'
        )
        a0 = a1
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{ri - 4}" fill="none" stroke="{C["ink"]}" stroke-width="1.5" stroke-dasharray="2 3"/>')
    return "\n".join(out)


def legend(items, x, y):
    total = sum(v for _, v in items) or 1
    out = []
    for i, (name, v) in enumerate(items):
        yy = y + i * 24
        out.append(f'<rect x="{x}" y="{yy-11}" width="12" height="12" rx="3" fill="{SLICES[i % len(SLICES)]}" stroke="{C['ink']}" stroke-width="1.2"/>')
        out.append(f'<text class="x" x="{x+20}" y="{yy}">{escape(name)} <tspan class="m">{v*100/total:.0f}%</tspan></text>')
    return "\n".join(out)


def lang_card(title, items, label):
    if not items:
        body = '<text class="m" x="24" y="110">Sin datos todavía</text>'
    else:
        body = legend(items, 24, 78) + donut(items, 258, 122, r=44, sw=22)
    return card(340, 200, title, body, label)


def smooth_path(pts, floor):
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1 = pts[max(i - 1, 0)], pts[i]
        p2, p3 = pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, min(p1[1] + (p2[1] - p0[1]) / 6, floor))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, min(p2[1] - (p3[1] - p1[1]) / 6, floor))
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def profile_card(d):
    days = d["days"]
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    vals = [sum(x["contributionCount"] for x in w) for w in weeks]
    x0, x1, y0, y1 = 330, 668, 74, 164
    top = max(vals + [1])
    step = (x1 - x0) / max(len(vals) - 1, 1)
    pts = [(x0 + i * step, y1 - (v / top) * (y1 - y0)) for i, v in enumerate(vals)]
    line = smooth_path(pts, y1)
    area = f"{line} L{x1},{y1} L{x0},{y1} Z"

    labels, last = [], None
    for i, w in enumerate(weeks):
        dt = datetime.fromisoformat(w[0]["date"])
        if dt.month != last and dt.day <= 7 and i % 1 == 0:
            last = dt.month
            if dt.month % 2 == 1:
                labels.append(f'<text class="m" x="{x0 + i*step:.1f}" y="{y1+18}" text-anchor="middle">{MESES[dt.month-1]}</text>')

    rows = [
        (f"{d['contributions']:,}".replace(",", ".") + " contribuciones en el último año"),
        (f"{d['repos']} repositorios propios"),
        (f"En GitHub desde {d['since']}"),
    ]
    info = "\n".join(
        f'<circle cx="31" cy="{90 + i*32}" r="5" fill="{C["moss"] if i else C["title"]}"/>'
        f'<text class="x" x="46" y="{95 + i*32}">{escape(r)}</text>'
        for i, r in enumerate(rows)
    )
    body = f"""
<defs><linearGradient id="a" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{C['title']}" stop-opacity="0.55"/>
  <stop offset="1" stop-color="{C['moss']}" stop-opacity="0.05"/>
</linearGradient></defs>
<text class="m" x="{x1}" y="66" text-anchor="end">contribuciones por semana</text>
<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{C['grid']}"/>
<path d="{area}" fill="url(#a)"/>
<path d="{line}" fill="none" stroke="{C['title']}" stroke-width="2.5"/>
{''.join(labels)}
{info}"""
    title = d["name"] if len(d["name"]) <= 24 else d["name"][:23] + "…"
    return card(700, 200, title, body, "Resumen del perfil de GitHub")


def hours_card(hours):
    x0, x1, y0, y1 = 36, 312, 80, 164
    top = max(hours + [1])
    bw = (x1 - x0) / 24
    peak = hours.index(max(hours)) if any(hours) else -1
    bars = []
    for h, v in enumerate(hours):
        bh = (v / top) * (y1 - y0)
        fill = C["title"] if h == peak else C["moss"]
        bars.append(f'<rect x="{x0 + h*bw + 1.5:.1f}" y="{y1 - bh:.1f}" width="{bw - 3:.1f}" height="{bh:.1f}" rx="2" fill="{fill}"/>')
    ticks = "".join(
        f'<text class="m" x="{x0 + h*bw + bw/2:.1f}" y="{y1+16}" text-anchor="middle">{h}h</text>' for h in (0, 6, 12, 18, 23)
    )
    note = f'<text class="m" x="22" y="68">Hora Colombia (UTC-5){f", pico a las {peak}h" if peak >= 0 else ""}</text>'
    body = f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{C["grid"]}"/>{"".join(bars)}{ticks}{note}'
    return card(340, 200, "Commits por hora", body, "Commits por hora del día")


def stats_card(d):
    rows = [("Estrellas", d["stars"]), ("Commits (último año)", d["commits"]),
            ("Pull requests", d["prs"]), ("Issues", d["issues"]), ("Contribuyó a", d["contributed_to"])]
    body = "\n".join(
        f'<text class="x" x="24" y="{78 + i*23}">{label}</text><text class="v" x="208" y="{78 + i*23}" text-anchor="end">{val}</text>'
        for i, (label, val) in enumerate(rows)
    )
    r, cx, cy = 40, 266, 120
    circ = 2 * math.pi * r
    filled = circ * min(d["commits"] / 1000, 1)
    body += f"""
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{C['grid']}" stroke-width="9"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{C['title']}" stroke-width="9" stroke-linecap="round"
  stroke-dasharray="{filled:.1f} {circ:.1f}" transform="rotate(-90 {cx} {cy})"/>
<text x="{cx}" y="{cy+4}" text-anchor="middle" style="font-family:{DISPLAY};font-size:22px;font-weight:900;fill:{C['text']}">{d['commits']}</text>
<text class="m" x="{cx}" y="{cy+22}" text-anchor="middle">commits</text>"""
    return card(340, 200, "Estadísticas", body, "Estadísticas de GitHub")


def render(d):
    os.makedirs(OUT_DIR, exist_ok=True)
    files = {
        "profile.svg": profile_card(d),
        "langs-repo.svg": lang_card("Lenguajes por repositorio", d["lang_repo"], "Lenguajes por repositorio"),
        "commit-hours.svg": hours_card(d["hours"]),
        "stats.svg": stats_card(d),
        "langs-commit.svg": lang_card("Lenguajes por commit", d["lang_commit"], "Lenguajes por commit"),
    }
    for name, svg in files.items():
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(svg)
    print("Tarjetas generadas en", OUT_DIR)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--mock":
        render(json.load(open(sys.argv[2], encoding="utf-8")))
    else:
        render(fetch())
