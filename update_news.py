#!/usr/bin/env python3
"""
The Go To - Automated Daily News Curator (real edition).

Fetches live RSS/API feeds every morning, applies the editorial guardrails
(zero sports, zero partisan punditry - executive orders only), extracts
summaries + takeaways, and rewrites:
  - stories.json          (data for the PWA live-update check)
  - index.html            (lead hero, story cards, and modals, between
                           AUTO-LEAD / AUTO-STORIES / AUTO-MODALS markers)

Only stdlib + feedparser (pip install feedparser).
"""

import feedparser
import html
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from html import unescape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORIES_PATH = os.path.join(BASE_DIR, "stories.json")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ----------------------------------------------------------------------------
# Editorial guardrails (kept from the original edition)
# ----------------------------------------------------------------------------
BANNED_SPORTS_KEYWORDS = [
    "saints", "pelicans", "nfl", "nba", "mlb", "nhl", "touchdown", "quarterback",
    "super bowl", "world series", "stanley cup", "playoffs", "basketball",
    "football", "baseball", "score", "scores", "roster", "coach",
    "transfer portal", "lsu tigers", "sec championship", "golf", "tennis",
    "nascar", "ufc", "olympics",
]
# Narrower list for the gaming desk: kill real-world sports, keep sports games.
BANNED_SPORTS_GAMING = [
    "saints", "pelicans", "nfl", "nba", "mlb", "nhl", "lsu",
    "super bowl", "world series", "stanley cup", "touchdown", "quarterback",
]
BANNED_SPORTS_OUTLETS = [
    "espn", "bleacher report", "sports illustrated", "wrestling",
    "mma fighting", "ufc.com", "nfl.com", "nba.com", "wwe",
]
BANNED_PARTISAN_POLITICS = [
    "senate debate", "campaign trail", "poll numbers", "gop primary",
    "democratic debate", "partisan", "election rally", "pundit", "talking heads",
    "impeach", "midterms",
]
# Business Insider is broad - only keep tech-flavored items from it.
BI_TECH_KEYWORDS = [
    "ai", "artificial intelligence", "tech", "technology", "chip",
    "semiconductor", "apple", "google", "microsoft", "openai", "anthropic",
    "nvidia", "software", "startup", "cyber", "robot", "spacex", "tesla",
    "amazon", "meta", "iphone", "android",
]

# ----------------------------------------------------------------------------
# Sources: (outlet name, feed url). All verified live 2026-10-09.
# ----------------------------------------------------------------------------
SOURCES = {
    "local": [
        ("Google News",
         "https://news.google.com/rss/search?q=Kenner%20Louisiana&hl=en-US&gl=US&ceid=US:en"),
        ("Google News",
         "https://news.google.com/rss/search?q=New%20Orleans%20news&hl=en-US&gl=US&ceid=US:en"),
    ],
    "tech": [
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("ScienceDaily", "https://www.sciencedaily.com/rss/matter_energy/technology.xml"),
        ("Business Insider", "https://www.businessinsider.com/rss"),
    ],
    "aviation": [
        ("AVweb", "https://www.avweb.com/feed/"),
    ],
    "drones": [
        ("sUAS News", "https://www.suasnews.com/feed/"),
    ],
    "cars": [
        ("Electrek", "https://electrek.co/feed/"),
    ],
    "gaming": [
        ("Polygon", "https://www.polygon.com/rss/index.xml"),
        ("Kotaku", "https://kotaku.com/rss"),
    ],
}

CATEGORY_LABELS = {
    "local": "Local News",
    "tech": "Tech",
    "aviation": "Aviation",
    "drones": "Drones",
    "cars": "Cars",
    "gaming": "Gaming",
    "presidential": "Presidential Action",
}
CATEGORY_PREFIX = {
    "local": "loc", "tech": "tech", "aviation": "av", "drones": "drone",
    "cars": "car", "gaming": "game", "presidential": "pres",
}
SECTION_LIMITS = {
    "local": 4, "tech": 3, "aviation": 2, "drones": 2,
    "cars": 2, "gaming": 2, "presidential": 2,
}
SECTION_ORDER = ["local", "tech", "aviation", "drones", "cars", "gaming", "presidential"]

# ----------------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------------
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
SENT_RE = re.compile(r"(?<=[.!?])\s+")


def clean_text(raw):
    """Strip HTML tags/entities, collapse whitespace."""
    if not raw:
        return ""
    text = TAG_RE.sub(" ", raw)
    text = unescape(text)
    text = WS_RE.sub(" ", text).strip()
    return text


def split_sentences(text):
    parts = [s.strip() for s in SENT_RE.split(text) if s.strip()]
    # Drop fragments that are clearly not sentences (nav junk, very short).
    return [s for s in parts if len(s) > 25]


def contains_any(text, keywords):
    low = text.lower()
    return any(k in low for k in keywords)


def format_date(struct_or_none):
    try:
        if struct_or_none:
            dt = datetime.fromtimestamp(time.mktime(struct_or_none))
            return dt.strftime("%B %d, %Y")
    except Exception:
        pass
    return datetime.now().strftime("%B %d, %Y")


def fetch_feed(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return feedparser.parse(data)
    except Exception as e:
        print(f"  !! feed failed: {url} ({e})", file=sys.stderr)
        return None

# ----------------------------------------------------------------------------
# Story building
# ----------------------------------------------------------------------------

def passes_guardrails(category, title, body):
    blob = f"{title} {body}"
    if category == "presidential":
        return True  # executive orders are the exception by design
    sports_list = BANNED_SPORTS_GAMING if category == "gaming" else BANNED_SPORTS_KEYWORDS
    if contains_any(blob, sports_list):
        return False
    if contains_any(blob, BANNED_PARTISAN_POLITICS):
        return False
    return True


def make_takeaways(sentences):
    """Turn sentences into {title, desc} takeaway dicts."""
    out = []
    for s in sentences:
        if ":" in s:
            head, tail = s.split(":", 1)
            if len(head.strip()) < 60 and len(tail.strip()) > 10:
                out.append({"title": head.strip(), "desc": tail.strip()})
                continue
        out.append({"title": "Detail", "desc": s})
    return out


def story_from_entry(category, outlet, entry):
    title = clean_text(entry.get("title", "")).strip()
    if not title or len(title) < 15:
        return None
    link = entry.get("link", "")
    raw_desc = entry.get("description", "") or entry.get("summary", "")
    body = clean_text(raw_desc)

    # Google News items carry the real outlet in <source>.
    src = entry.get("source", {})
    real_outlet = clean_text(src.get("title", "")) if isinstance(src, dict) else ""
    source_name = real_outlet or outlet

    # Google News titles look like "Headline - Outlet": strip the outlet suffix.
    if real_outlet:
        title = re.sub(r"\s+-\s+" + re.escape(real_outlet) + r"\s*$",
                       "", title, flags=re.IGNORECASE).strip()

    # Skip real-estate listings / address-like junk.
    if re.match(r"^\d+\s+\w+\s+(st|ave|avenue|blvd|rd|dr|ln|ct|street)\b",
                title, re.IGNORECASE):
        return None

    # Skip stale items (older than 4 days) when the feed gives a date.
    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub:
        try:
            age_days = (time.time() - time.mktime(pub)) / 86400
            if age_days > 4:
                return None
        except Exception:
            pass

    # Hard block on sports outlets no matter the headline.
    if contains_any(source_name, BANNED_SPORTS_OUTLETS):
        return None
    if not passes_guardrails(category, title, body):
        return None
    if outlet == "Business Insider" and not contains_any(f"{title} {body}", BI_TECH_KEYWORDS):
        return None

    sentences = split_sentences(body)
    if sentences:
        summary = " ".join(sentences[:2])
        if len(summary) > 400:
            summary = summary[:397].rsplit(" ", 1)[0] + "..."
        why = sentences[0]
        takeaways = make_takeaways(sentences[1:4]) or make_takeaways(sentences[:1])
    else:
        # Thin feeds (Google News): headline-driven story.
        summary = f"Latest local reporting from {source_name} - tap through for the full story."
        why = f"Latest local reporting from {source_name}."
        takeaways = [{"title": "Read more",
                      "desc": f"Full story via {source_name} - open the source link."}]

    return {
        "headline": title,
        "source": source_name,
        "source_url": link,
        "date": format_date(entry.get("published_parsed") or entry.get("updated_parsed")),
        "summary": summary,
        "why_it_matters": why,
        "takeaways": takeaways[:3],
    }


def fetch_presidential_orders(limit=2):
    """Executive orders only, via the Federal Register API."""
    url = ("https://www.federalregister.gov/api/v1/documents.json"
           "?conditions%5Btype%5D%5B%5D=PRESDOCU&per_page=10&order=newest"
           "&fields%5B%5D=title&fields%5B%5D=subtype&fields%5B%5D=publication_date"
           "&fields%5B%5D=html_url&fields%5B%5D=abstract"
           "&fields%5B%5D=executive_order_number")
    stories = []
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for doc in data.get("results", []):
            if doc.get("subtype") != "Executive Order":
                continue
            num = doc.get("executive_order_number")
            title = clean_text(doc.get("title", ""))
            pub = doc.get("publication_date", "")
            try:
                date_s = datetime.strptime(pub, "%Y-%m-%d").strftime("%B %d, %Y")
            except Exception:
                date_s = datetime.now().strftime("%B %d, %Y")
            label = f"Executive Order {num}" if num else "Executive Order"
            abstract = clean_text(doc.get("abstract") or "")
            stories.append({
                "headline": f"{title} ({label})",
                "source": "Federal Register",
                "source_url": doc.get("html_url", ""),
                "date": date_s,
                "summary": abstract or f"{label}: {title}. Published {date_s}.",
                "why_it_matters": f"Direct presidential action published {date_s}.",
                "takeaways": [
                    {"title": "Official text",
                     "desc": "Read the full signed order at the source link."},
                    {"title": "Published", "desc": f"Federal Register, {date_s}."},
                ],
            })
            if len(stories) >= limit:
                break
    except Exception as e:
        print(f"  !! presidential fetch failed ({e})", file=sys.stderr)
    return stories

# ----------------------------------------------------------------------------
# HTML generation (matches the existing card / modal / lead markup)
# ----------------------------------------------------------------------------

def esc(s):
    return html.escape(s or "", quote=True)


def card_html(story):
    sid = story["id"]
    takeaway_items = "\n".join(
        f"<li><strong>{esc(t['title'])}:</strong> {esc(t['desc'])}</li>"
        for t in story["takeaways"]
    )
    return f"""        <article class="story-card" data-category="{story['category']}" id="card-{sid}">
          <div class="card-top">
            <div class="badge-row">
              <span class="badge-cat">{esc(story['category_label'])}</span>
              <span class="badge-source">{esc(story['source'])}</span>
            </div>
            <h3 class="story-headline">
              <a href="#modal-{sid}" class="headline-link">{esc(story['headline'])}</a>
            </h3>
            <p class="story-snippet">{esc(story['summary'])}</p>

            <details class="inline-takeaways-details">
              <summary class="inline-takeaways-summary">
                <span class="summary-toggle-icon">📌</span> Click to expand key takeaways directly
              </summary>
              <div class="inline-takeaways-content">
                <div class="takeaways-subheading">Why It Matters:</div>
                <p class="inline-overview-p">{esc(story['why_it_matters'])}</p>
                <div class="takeaways-subheading" style="margin-top: 10px;">Important Takeaways:</div>
                <ul class="inline-bullet-list">
                  {takeaway_items}
                </ul>
              </div>
            </details>
          </div>
          <div class="card-footer">
            <span class="story-date">{esc(story['date'])}</span>
            <div style="display: flex; gap: 10px; align-items: center;">
              <a href="#modal-{sid}" class="preview-cta-link">
                Open Pop-Up Modal →
              </a>
            </div>
          </div>
        </article>
"""


def modal_html(story):
    sid = story["id"]
    items = "\n".join(
        f"""        <div class="modal-takeaway-item">
          <div class="takeaway-point-title">👉 {esc(t['title'])}</div>
          <div class="takeaway-point-desc">{esc(t['desc'])}</div>
        </div>"""
        for t in story["takeaways"]
    )
    return f"""  <div class="modal-overlay" id="modal-{sid}" role="dialog" aria-modal="true">
    <div class="modal-box">
      <a href="#close" class="modal-close-btn" title="Close">✕</a>

      <div class="modal-meta-row">
        <span class="badge-cat">{esc(story['category_label'])}</span>
        <span class="badge-source">{esc(story['source'])}</span>
        <span style="color: var(--text-muted);">{esc(story['date'])}</span>
      </div>

      <h2 class="modal-headline">{esc(story['headline'])}</h2>

      <div class="modal-overview-box">
        <div class="modal-overview-title">Why It Matters</div>
        <div class="modal-overview-text">{esc(story['why_it_matters'])}</div>
      </div>

      <div class="modal-section-title">
        📌 Key Takeaways & Core Impact
      </div>
      <div>

{items}

      </div>

      <div class="modal-action-bar">
        <div class="verified-source-badge">
          🛡️ Verified Reputable Outlet
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
          <a href="#close" class="close-modal-link">Close Window</a>
          <a href="{esc(story['source_url'])}" target="_blank" rel="noopener noreferrer" class="open-source-link">
            Read Original Source on {esc(story['source'])} ↗
          </a>
        </div>
      </div>
    </div>
  </div>
"""


def lead_html(story):
    sid = story["id"]
    bullets = "\n".join(
        f"            <li><strong>{esc(t['title'])}:</strong> {esc(t['desc'][:120])}</li>"
        for t in story["takeaways"]
    )
    return f"""      <div class="lead-card">
        <div class="lead-content">
          <div class="badge-row">
            <span class="badge-cat">⭐ Lead Story • {esc(story['category_label'])}</span>
            <span class="badge-source">{esc(story['source'])}</span>
            <span style="color: var(--text-muted);">• {esc(story['date'])}</span>
          </div>
          <h2 class="lead-headline">
            <a href="#modal-{sid}" class="headline-link">{esc(story['headline'])}</a>
          </h2>
          <p class="lead-summary">{esc(story['summary'])}</p>
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <a href="#modal-{sid}" class="lead-interactive-cta">
              <span>View Key Takeaways & Impact</span> →
            </a>
            <a href="{esc(story['source_url'])}" target="_blank" rel="noopener noreferrer" class="direct-source-link">
              Source: {esc(story['source'])} ↗
            </a>
          </div>
        </div>
        <div class="lead-side-takeaways">
          <div class="takeaways-label">⚡ Executive Snapshot (Click Headline for Full Modal)</div>
          <ul class="quick-bullet-list">
{bullets}
          </ul>
        </div>
      </div>
"""


def replace_between_markers(page, start, end, new_inner):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    replacement = start + "\n" + new_inner.rstrip("\n") + "\n" + end
    new_page, n = pattern.subn(replacement, page)
    if n == 0:
        print(f"  !! markers not found: {start}", file=sys.stderr)
    return new_page


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def run_update():
    print("Starting 'The Go To' Daily News Update Engine (live feeds)...")
    stories = []
    seen_titles, seen_links = set(), set()

    for category in SECTION_ORDER:
        if category == "presidential":
            raw = fetch_presidential_orders(SECTION_LIMITS[category])
        else:
            per_outlet = []
            for outlet, url in SOURCES[category]:
                print(f"  fetching {outlet} [{category}]...")
                feed = fetch_feed(url)
                if not feed:
                    continue
                got = []
                for entry in feed.entries:
                    s = story_from_entry(category, outlet, entry)
                    if not s:
                        continue
                    key_t = re.sub(r"\W+", "", s["headline"].lower())[:60]
                    if key_t in seen_titles or s["source_url"] in seen_links:
                        continue
                    seen_titles.add(key_t)
                    seen_links.add(s["source_url"])
                    got.append(s)
                per_outlet.append(got)
            # Round-robin across outlets so no single source dominates.
            raw = []
            for i in range(max((len(g) for g in per_outlet), default=0)):
                for got in per_outlet:
                    if i < len(got):
                        raw.append(got[i])
                    if len(raw) >= SECTION_LIMITS[category]:
                        break
                if len(raw) >= SECTION_LIMITS[category]:
                    break
            raw = raw[:SECTION_LIMITS[category]]

        prefix = CATEGORY_PREFIX[category]
        for i, s in enumerate(raw):
            s["id"] = f"{prefix}-{i + 1}"
            s["category"] = category
            s["category_label"] = CATEGORY_LABELS[category]
            s["is_lead"] = False
            stories.append(s)
        print(f"  -> {category}: {len(raw)} stories")

    if not stories:
        print("No stories fetched - leaving existing files untouched.", file=sys.stderr)
        sys.exit(1)

    # Lead = first local story, else first story overall.
    lead = next((s for s in stories if s["category"] == "local"), stories[0])
    lead["is_lead"] = True

    # --- stories.json ---
    now = datetime.now()
    data = {
        "last_updated": now.isoformat(),
        "date_display": now.strftime("%A, %B %d, %Y"),
        "stories": stories,
    }
    with open(STORIES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"wrote {STORIES_PATH} ({len(stories)} stories)")

    # --- index.html ---
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        page = f.read()

    cards = "\n".join(card_html(s) for s in stories)
    modals = "\n".join(modal_html(s) for s in stories)
    page = replace_between_markers(page, "<!-- AUTO-LEAD-START -->",
                                   "<!-- AUTO-LEAD-END -->", lead_html(lead))
    page = replace_between_markers(page, "<!-- AUTO-STORIES-START -->",
                                   "<!-- AUTO-STORIES-END -->", cards)
    page = replace_between_markers(page, "<!-- AUTO-MODALS-START -->",
                                   "<!-- AUTO-MODALS-END -->", modals)
    page = re.sub(r"Showing \d+ stories",
                  f"Showing {len(stories)} stories", page)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"rewrote {INDEX_PATH} (lead + {len(stories)} cards + modals)")
    print("Update complete!")


if __name__ == "__main__":
    run_update()
