"""Render the project's Markdown docs as styled HTML at ``/documentation``.

Server-side rendering (no CDN) so the docs page works in air-gapped/offline
deployments. The available pages are whitelisted to avoid path traversal.
"""
import re
from functools import lru_cache
from pathlib import Path

import markdown
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.core.exceptions import NotFoundError

# project root = three parents up from this file (app/api/docs_pages.py -> /var/www/seo)
BASE_DIR = Path(__file__).resolve().parents[2]

# slug -> (file path, page title)
PAGES: dict[str, tuple[Path, str]] = {
    "api": (BASE_DIR / "docs" / "API.md", "API Reference"),
    "readme": (BASE_DIR / "README.md", "README"),
}

router = APIRouter(tags=["documentation"])

_STYLE = """
*,*::before,*::after { box-sizing:border-box; }
:root {
  --bg:#ffffff; --surface:#fbfbfd; --fg:#1d1d1f; --muted:#6e6e73;
  --border:#ececf0; --border-strong:#e0e0e6; --code-bg:#f6f6f8;
  --accent:#5b5bf6; --accent-soft:rgba(91,91,246,.10);
  --radius:10px; --header-h:58px; --sidebar-w:272px; --measure:760px;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){ :root{
  --bg:#0c0c0f; --surface:#141417; --fg:#ededef; --muted:#9a9aa3;
  --border:#222227; --border-strong:#2c2c33; --code-bg:#16161b;
  --accent:#8b8bfb; --accent-soft:rgba(139,139,251,.14);
}}
html { scroll-behavior:smooth; }
body { margin:0; background:var(--bg); color:var(--fg);
  font-family:var(--sans); font-size:15.5px; line-height:1.7;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }

/* Header */
header.top { position:fixed; inset:0 0 auto 0; height:var(--header-h); z-index:50;
  display:flex; align-items:center; gap:18px; padding:0 22px;
  background:color-mix(in srgb,var(--bg) 82%,transparent);
  backdrop-filter:saturate(160%) blur(12px);
  -webkit-backdrop-filter:saturate(160%) blur(12px);
  border-bottom:1px solid var(--border); }
header.top .brand { display:flex; align-items:center; gap:9px; font-weight:650;
  letter-spacing:-.01em; white-space:nowrap; }
header.top .dot { width:9px; height:9px; border-radius:50%;
  background:var(--accent); box-shadow:0 0 0 4px var(--accent-soft); }
header.top nav { display:flex; gap:4px; margin-left:6px; }
header.top nav a { font-size:13.5px; color:var(--muted); text-decoration:none;
  padding:6px 11px; border-radius:8px; line-height:1; }
header.top nav a:hover { color:var(--fg); background:var(--surface); }
header.top nav a.active { color:var(--accent); background:var(--accent-soft); }
header.top .spacer { flex:1; }
header.top .ext { font-size:13.5px; color:var(--muted); text-decoration:none; }
header.top .ext:hover { color:var(--fg); }
#menu { display:none; background:none; border:0; color:var(--fg);
  font-size:20px; cursor:pointer; padding:4px 8px; }

/* Layout */
.wrap { display:flex; max-width:1200px; margin:0 auto; padding-top:var(--header-h); }
aside { position:sticky; top:var(--header-h); align-self:flex-start;
  width:var(--sidebar-w); flex:0 0 var(--sidebar-w);
  height:calc(100vh - var(--header-h)); overflow:auto; padding:26px 16px 60px; }
aside .label { font-size:11px; font-weight:600; letter-spacing:.07em;
  text-transform:uppercase; color:var(--muted); margin:0 0 10px 10px; }
aside .toc ul { list-style:none; margin:0; padding:0; }
aside .toc > ul > li > a { font-weight:550; }
aside .toc li { margin:1px 0; }
aside .toc a { display:block; padding:5px 10px; border-radius:7px; font-size:13.5px;
  color:var(--muted); text-decoration:none; border-left:2px solid transparent;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
aside .toc a:hover { color:var(--fg); background:var(--surface); }
aside .toc a.active { color:var(--accent); background:var(--accent-soft);
  border-left-color:var(--accent); font-weight:550; }
aside .toc ul ul a { padding-left:22px; font-size:13px; }

main { flex:1; min-width:0; padding:36px 56px 120px; }
article { max-width:var(--measure); }

/* Typography */
article h1,article h2,article h3,article h4 { letter-spacing:-.02em; line-height:1.25;
  scroll-margin-top:calc(var(--header-h) + 18px); font-weight:650; }
article h1 { font-size:2.1rem; margin:.2em 0 .6em; }
article h2 { font-size:1.5rem; margin:2.4em 0 .8em; padding-top:1.4em;
  border-top:1px solid var(--border); }
article h3 { font-size:1.18rem; margin:1.8em 0 .6em; }
article h4 { font-size:1rem; margin:1.4em 0 .5em; color:var(--muted); }
article p { margin:.9em 0; }
article a { color:var(--accent); text-decoration:none; }
article a:hover { text-decoration:underline; text-underline-offset:2px; }
article strong { font-weight:650; }
article ul,article ol { padding-left:1.4em; }
article li { margin:.3em 0; }
article hr { border:0; border-top:1px solid var(--border); margin:2.4em 0; }

/* Code */
article code { font-family:var(--mono); font-size:.86em; background:var(--code-bg);
  border:1px solid var(--border); padding:.12em .42em; border-radius:6px; }
article pre { background:var(--code-bg); border:1px solid var(--border);
  border-radius:var(--radius); padding:16px 18px; overflow:auto; margin:1.2em 0;
  line-height:1.55; }
article pre code { background:none; border:0; padding:0; font-size:.84rem; }

/* Tables */
article table { border-collapse:separate; border-spacing:0; width:100%; margin:1.4em 0;
  font-size:14px; border:1px solid var(--border); border-radius:var(--radius);
  overflow:hidden; display:block; overflow-x:auto; }
article th,article td { padding:9px 14px; text-align:left;
  border-bottom:1px solid var(--border); border-right:1px solid var(--border);
  vertical-align:top; }
article th { background:var(--surface); font-weight:600; font-size:12.5px;
  letter-spacing:.02em; color:var(--muted); text-transform:uppercase; }
article tr:last-child td { border-bottom:0; }
article th:last-child,article td:last-child { border-right:0; }

/* Blockquote */
article blockquote { margin:1.4em 0; padding:2px 16px; color:var(--muted);
  border-left:3px solid var(--accent); background:var(--accent-soft);
  border-radius:0 8px 8px 0; }
article blockquote p { margin:.6em 0; }

/* HTTP method badges (added server-side in code spans) */
.m { display:inline-block; font-family:var(--mono); font-size:.7rem; font-weight:700;
  letter-spacing:.04em; padding:.28em .55em; border-radius:6px; color:#fff;
  vertical-align:middle; transform:translateY(-2px); }
.m-get{background:#2f81f7;} .m-post{background:#3fb950;} .m-put{background:#d29922;}
.m-delete{background:#f85149;} .m-patch{background:#a371f7;}
article h3 code.ep,article h4 code.ep { font-size:.95em; background:none; border:0;
  padding:0; color:var(--fg); }

@media (max-width:860px){
  aside { position:fixed; top:var(--header-h); left:0; z-index:40; background:var(--bg);
    border-right:1px solid var(--border); transform:translateX(-100%);
    transition:transform .2s ease; box-shadow:0 10px 40px rgba(0,0,0,.25); }
  body.nav-open aside { transform:translateX(0); }
  #menu { display:block; }
  main { padding:28px 20px 100px; }
}
"""

_SCRIPT = """
const links=[...document.querySelectorAll('aside .toc a')];
const map=new Map(links.map(a=>[a.getAttribute('href').slice(1),a]));
const heads=[...document.querySelectorAll('article h1,article h2,article h3')]
  .filter(h=>h.id&&map.has(h.id));
const io=new IntersectionObserver((es)=>{
  es.forEach(e=>{ if(e.isIntersecting){
    links.forEach(a=>a.classList.remove('active'));
    const a=map.get(e.target.id); if(a){a.classList.add('active');
      a.scrollIntoView({block:'nearest'});}
  }});
},{rootMargin:'-12% 0px -78% 0px',threshold:0});
heads.forEach(h=>io.observe(h));
const menu=document.getElementById('menu');
if(menu){menu.onclick=()=>document.body.classList.toggle('nav-open');}
document.querySelectorAll('aside .toc a').forEach(a=>a.addEventListener('click',
  ()=>document.body.classList.remove('nav-open')));
"""

# Turn a leading HTTP verb in a heading (e.g. "### POST /auth/login") into a
# coloured badge followed by the path in monospace.
_METHOD_RE = re.compile(
    r'(<h[1-4][^>]*>)\s*(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)'
)


def _badge_methods(html: str) -> str:
    def repl(m: re.Match) -> str:
        open_tag, verb, path = m.group(1), m.group(2), m.group(3)
        return (
            f'{open_tag}<span class="m m-{verb.lower()}">{verb}</span> '
            f'<code class="ep">{path}</code>'
        )

    return _METHOD_RE.sub(repl, html)


@lru_cache(maxsize=8)
def _render(slug: str) -> str:
    path, title = PAGES[slug]
    text = path.read_text(encoding="utf-8")
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "sane_lists", "attr_list"]
    )
    body = _badge_methods(md.convert(text))
    toc = getattr(md, "toc", "")

    tabs = []
    for s, (_, t) in PAGES.items():
        cls = " active" if s == slug else ""
        tabs.append(f'<a class="{cls.strip()}" href="/documentation/{s}">{t}</a>')
    tabs_html = "".join(tabs)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {settings.APP_NAME}</title>
<style>{_STYLE}</style></head>
<body>
<header class="top">
  <button id="menu" aria-label="Toggle menu">☰</button>
  <span class="brand"><span class="dot"></span>{settings.APP_NAME}</span>
  <nav>{tabs_html}</nav>
  <span class="spacer"></span>
  <a class="ext" href="/docs">Swagger</a>
  <a class="ext" href="/redoc">ReDoc</a>
</header>
<div class="wrap">
  <aside>
    <div class="label">On this page</div>
    {toc}
  </aside>
  <main><article>{body}</article></main>
</div>
<script>{_SCRIPT}</script>
</body></html>"""


@router.get("/documentation", response_class=HTMLResponse)
async def documentation_index() -> HTMLResponse:
    """Render the API reference (default documentation page)."""
    return HTMLResponse(_render("api"))


@router.get("/documentation/{slug}", response_class=HTMLResponse)
async def documentation_page(slug: str) -> HTMLResponse:
    if slug not in PAGES:
        raise NotFoundError(f"No documentation page '{slug}'.")
    return HTMLResponse(_render(slug))
