"""Thresholds, weights and word lists for the SEO engine.

Centralizing these keeps scoring tunable without touching check logic.
"""

# Category contribution to the overall score. Must sum to 1.0.
CATEGORY_WEIGHTS: dict[str, float] = {
    "meta": 0.20,
    "content": 0.22,
    "structure": 0.12,
    "links": 0.10,
    "indexability": 0.12,
    "performance": 0.12,
    "security": 0.06,
    "mobile": 0.06,
}

# Relative weight of a check *within its category*. Only ratios matter here:
# 1.0 is an ordinary check, so a missing title tag (3.0) moves the meta score
# six times as far as a missing Twitter card (0.5). Averaging a category's
# checks equally is what makes a score feel arbitrary — it lets a favicon
# outvote an H1. A check absent from this map counts as 1.0.
CHECK_WEIGHTS: dict[str, float] = {
    # meta
    "title_tag": 3.0,
    "meta_robots": 2.5,
    "canonical": 2.0,
    "meta_description": 1.5,
    "structured_data": 1.5,
    "html_lang": 0.5,
    "open_graph": 0.5,
    "twitter_card": 0.25,
    # content
    # Note: keyword targeting is not here. It is scored as its own feature (see
    # app/seo/keywords.py) because its result depends on what the submitter
    # typed, and a page-health score must depend only on the page.
    "word_count": 2.0,
    "image_alt": 1.5,
    "readability": 1.0,
    "image_optimization": 1.0,
    "stopword_density": 0.5,
    "typos": 0.5,
    # structure
    "h1_heading": 3.0,
    "heading_hierarchy": 1.5,
    "charset": 1.0,
    "doctype": 0.5,
    "favicon": 0.25,
    # links
    "broken_links": 2.0,
    "anchor_quality": 1.5,
    "links": 1.0,
    # indexability
    "robots_txt": 2.0,
    "sitemap": 1.5,
    "hreflang": 0.5,
    # performance
    "ttfb": 2.0,
    "load_time": 2.0,
    "compression": 1.5,
    "render_blocking": 1.5,
    "page_size": 1.0,
    "core_web_vitals": 1.0,
    # security
    "https": 3.0,
    "mixed_content": 2.0,
    "security_headers": 1.0,
    # mobile
    "mobile_viewport": 1.0,
}

# A page that cannot be indexed or reached over HTTPS cannot rank, whatever
# the rest of the report says. Averaging such a failure in with 35 healthy
# checks hides it behind a respectable-looking score, so these checks put a
# ceiling on the overall score instead when they come back critical.
SCORE_CAPS: dict[str, int] = {
    "meta_robots": 40,  # noindex
    "robots_txt": 40,  # Disallow: / for every user-agent
    "https": 60,  # served over plain HTTP
}

# --- Title ---
TITLE_MIN = 30
TITLE_MAX = 60
TITLE_PIXEL_SAFE_MAX = 65

# --- Meta description ---
DESC_MIN = 70
DESC_MAX = 160

# --- Content ---
THIN_CONTENT_WORDS = 300
GOOD_CONTENT_WORDS = 600
KEYWORD_DENSITY_MIN = 0.5  # percent
KEYWORD_DENSITY_MAX = 3.0  # percent (above is potential stuffing)

# --- Keyword targeting (user-supplied keywords) ---
MAX_TARGET_KEYWORDS = 5
# Where a target keyword appears, weighted by how far that placement actually
# moves on-page relevance. Sums to 100, so a keyword's score reads as a
# percentage of the placements that matter.
KEYWORD_PLACEMENT_WEIGHTS: dict[str, int] = {
    "title": 25,
    "h1": 20,
    "meta_description": 15,
    "first_paragraph": 15,
    "subheading": 10,
    "url_slug": 10,
    "image_alt": 5,
}
KEYWORD_PLACEMENT_LABELS: dict[str, str] = {
    "title": "title tag",
    "h1": "H1 heading",
    "meta_description": "meta description",
    "first_paragraph": "first 100 words",
    "subheading": "a subheading",
    "url_slug": "the URL",
    "image_alt": "image alt text",
}
# Words of body copy counted as the page opening, where placement matters most.
KEYWORD_OPENING_WORDS = 100
# Below this many words, density is noise rather than signal: on a 4-word page
# every term scores 25% and trips the stuffing threshold. Judging keyword focus
# at all needs a corpus big enough for one repetition not to swing the number.
KEYWORD_DENSITY_MIN_SAMPLE = 100
STOPWORD_DENSITY_WARN = 45.0  # percent

# --- Performance (HTTP-derived only; see performance.py) ---
TTFB_GOOD_MS = 200
TTFB_OK_MS = 600
LOAD_GOOD_MS = 1000
LOAD_OK_MS = 2500
HTML_SIZE_GOOD_KB = 100
HTML_SIZE_OK_KB = 250
RENDER_BLOCKING_OK = 5

# --- Common misspellings checked against page text ---
COMMON_TYPOS = {
    "wtih", "teh", "recieve", "seperate", "occured", "untill", "definately",
    "accomodate", "begining", "beleive", "calender", "concious", "embarass",
    "existance", "goverment", "occassion", "publically", "neccessary",
}

STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
    "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an",
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of",
    "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can",
    "will", "just", "don", "should", "now", "said", "would", "could",
}

# Web/URL artifacts that routinely leak into visible text (email addresses,
# social links, copyright lines) but are never a page's actual topic. Without
# these, a domain like "example.com" or "www.site.org" tokenizes into
# meaningless-but-frequent 3-letter words that can outrank the real keyword,
# especially on thin-content pages.
WEB_ARTIFACT_WORDS = {
    "www", "com", "net", "org", "edu", "gov", "co", "io", "http", "https",
    "html", "htm", "php", "asp", "aspx", "jsp", "amp", "mailto", "tel",
    "jpg", "jpeg", "png", "gif", "svg", "webp", "ico", "pdf", "doc", "docx",
    "css", "xml", "json", "utm", "nbsp",
}

STOP_WORDS |= WEB_ARTIFACT_WORDS
