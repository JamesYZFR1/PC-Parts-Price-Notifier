import os
import re
import feedparser
import apprise
import datetime
import sys
from typing import Iterable, Optional, Pattern, Tuple, Union
from zoneinfo import ZoneInfo

r"""
PC Parts Price Notifier
-----------------------
Purpose:
    Polls the /r/bapcsalescanada RSS feed and the /r/CanadianHardwareSwap RSS feed,
    sending notifications for deals/keywords that match rules
    that match price rules (CPU, CPU bundles, GPUs, monitors, motherboards).

Key features:
    - Price parsing from post titles (supports $1,234 and = $123 formats)
    - Multiple product filters with configurable thresholds
    - Seen-post tracking to avoid duplicate alerts
    - "--test" mode to send a test notification
    - "--dry-run" mode to preview matches without notifying
    - Environment-variable overrides so secrets/URLs aren't hardcoded

Environment variables (optional):
    FEED_URL        - RSS URL to read. Defaults to /r/bapcsalescanada
    SEEN_FILE       - Path to file that stores alerted post IDs
    LOG_FILE        - Path to run log file
    ROLE_MENTION    - Discord role mention string to prepend to messages
    APPRISE_URLS    - Comma-separated list of Apprise URLs (e.g. Discord webhook)

Run examples (PowerShell):
    $env:APPRISE_URLS = "https://discord.com/api/webhooks/..."
        python .\\pc_parts_price_notifier.py --dry-run
        python .\\pc_parts_price_notifier.py --test
        python .\\pc_parts_price_notifier.py
    """

# --- CONFIG ---
FEED_URL = os.getenv("FEED_URL", "https://www.reddit.com/r/bapcsalescanada/.rss")
# Additional marketplace feed: r/CanadianHardwareSwap (old.reddit RSS)
CHS_FEED_URL = os.getenv("CHS_FEED_URL", "https://old.reddit.com/r/CanadianHardwareSwap/.rss")
# Thresholds and keywords
GPU_PRICE_LIMIT = 2000
MONITOR_PRICE_LIMIT = 1000
CPU_MODELS = ["5800x3d", "7600x3d", "7800x3d"]
CPU_PRICE_LIMIT = 500  # notify for CPUs under this price
CPU_BUNDLE_PRICE_LIMIT = 600  # notify for [CPU Bundle] under this price
CPU_MOBO_BUNDLE_PRICE_LIMIT = 600  # notify for CPU+Mobo(/RAM) combos under this price
MOTHERBOARD_PRICE_LIMIT = 300  # notify for standalone motherboards under this price
KEYWORD = "[GPU]"
SEEN_FILE = os.getenv("SEEN_FILE", "seen_posts.txt")
# If you want to ping a Discord role, set ROLE_MENTION to the role mention string
# Example: ROLE_MENTION = "<@&123456789012345678>"
# To get your role ID: enable Developer Mode in Discord, right-click the role and select Copy ID.
# Note: The webhook's bot/user must have permission to @mention that role.
ROLE_MENTION = os.getenv("ROLE_MENTION", "<@&1431577185558331404>")
LOG_FILE = os.getenv("LOG_FILE", "run_log.txt")
TIMEZONE = os.getenv("TIMEZONE", "UTC")  # e.g., "America/Toronto", "America/Vancouver", "UTC"

# Add your Apprise URL(s) here
# APPRISE_URLS can be supplied via env var APPRISE_URLS (comma-separated)
_env_apprise = os.getenv("APPRISE_URLS")
if _env_apprise:
    APPRISE_URLS = [u.strip() for u in _env_apprise.split(",") if u.strip()]
else:
    APPRISE_URLS = [
        "",
        # "pb://...", 
        # "mailto://..."
    ]

# --- SETUP NOTIFIER ---
# Placed notifier setup early to be available for the test message
notifier = apprise.Apprise()
for url in APPRISE_URLS:
    notifier.add(url)

# --- TIME/LOG HELPERS ---
def _now_local():
    """Return timezone-aware datetime using TIMEZONE env var, fallback to UTC."""
    try:
        return datetime.datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        # On invalid timezone value, fall back to UTC
        return datetime.datetime.now(datetime.timezone.utc)

def log(message: str) -> None:
    ts = _now_local().isoformat(timespec="seconds")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")

# --- HANDLE TEST NOTIFICATION ---
if "--test" in sys.argv:
    print("Sending a test notification...")
    test_message = "This is a test notification to confirm the role mention is working."
    if ROLE_MENTION:
        test_message = f"{ROLE_MENTION}\n\n{test_message}"
    
    notifier.notify(
        body=test_message
    )
    print("✅ Test notification sent!")
    log("--- Test notification sent ---")
    sys.exit() # Exit after sending the test message

# --- CHECK FOR DRY RUN MODE ---
dry_run_mode = "--dry-run" in sys.argv

# --- LOG SCRIPT START ---
log("--- Script run started ---")

# --- LOAD PREVIOUSLY SEEN POSTS ---
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen_posts = set(line.strip() for line in f if line.strip())
else:
    seen_posts = set()

new_matches = []

# --- HELPERS ---
def normalize_text(s: str) -> str:
    """Lowercase and strip all non-alphanumeric characters to simplify matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower())

def extract_price(title):
    """Extract a sensible price from a post title.

    Strategy:
    - If there's a pattern like "=$123" (final price after '='), prefer that.
    - Otherwise, use the last $amount in the title.
    - Supports commas in numbers (e.g., $1,299).

    Returns:
        int | None: The parsed price, or None if no price could be found.
    """
    # prefer "= $123" or "=$123"
    eq_match = re.search(r"=\$?([\d,]+)", title)
    if eq_match:
        return int(eq_match.group(1).replace(",", ""))

    money_matches = re.findall(r"\$([\d,]+)", title)
    if money_matches:
        return int(money_matches[-1].replace(",", ""))

    return None
# PSU helpers
_RX_1000W = re.compile(r"(?<!\d)1[, ]?000\s*w\b", re.IGNORECASE)
_RX_1KW = re.compile(r"\b1\s*k\s*w\b|\b1kw\b", re.IGNORECASE)

def has_1000w_psu(text: str) -> bool:
    """Return True if text mentions a PSU/power supply and 1000W (or 1kW)."""
    t = text.lower()
    mentions_psu = ("psu" in t) or ("power supply" in t)
    mentions_1000w = bool(_RX_1000W.search(t) or _RX_1KW.search(t))
    return mentions_psu and mentions_1000w



def extract_first_match(
    text: str,
    patterns: Iterable[Union[str, Tuple[str, Pattern[str]]]]
) -> Optional[str]:
    """Return the first human-readable pattern label that matches the given text.

    "patterns" items can be tuples (label, compiled_regex) or strings (interpreted as regex with word-ish boundaries).
    Returns the label (string) of the first match, or None if no match.
    """
    for item in patterns:
        if isinstance(item, tuple):
            label, rx = item
            if rx.search(text):
                return label
        else:
            if re.search(item, text):
                return item
    return None


# --- PROCESS BAPCSALESCANADA FEED (price-based filters) ---
bapc_feed = feedparser.parse(FEED_URL)
for entry in bapc_feed.entries:
    post_id = entry.get("id", entry.get("link"))
    title = entry.get("title", "")

    # Skip if we've already alerted this one
    if post_id in seen_posts:
        continue

    price = extract_price(title)

    # Normalize title for model/keyword checks
    title_lower = title.lower()
    normalized = normalize_text(title_lower)

    alerted = False

    # CPU detection: notify for CPUs under price limits
    # Detect flexible bracketed tags like [CPU], [CPU Bundle], [CPU+Cooler], [CPU/Mobo], etc.
    # We capture what's inside the first [...] that starts with 'cpu' and use it to infer type.
    tag_match = re.search(r"\[(cpu[^\]]*)\]", title_lower)
    cpu_tag_text = tag_match.group(1) if tag_match else ""
    has_any_cpu_tag = bool(tag_match)
    is_cpu_bundle = "bundle" in cpu_tag_text or "cpu bundle" in title_lower
    # Additional indicators for CPU+Mobo combos and motherboards
    has_mobo_word = ("mobo" in title_lower) or ("motherboard" in title_lower)
    has_mobo_tag = bool(re.search(r"\[(?:mobo|motherboard)[^\]]*\]", title_lower))
    has_any_mobo = has_mobo_word or has_mobo_tag or ("mobo" in cpu_tag_text) or ("motherboard" in cpu_tag_text)
    is_cpu_mobo_combo = has_any_cpu_tag and has_any_mobo or bool(re.search(r"cpu\s*(?:\+|/|&)?\s*(?:mobo|motherboard)", title_lower))
    # Additional general indicators
    is_processor_word = "processor" in title_lower or " cpu " in f" {title_lower} "  # word-ish match
    is_known_model = any(model in normalized for model in CPU_MODELS)

    # CPU+Mobo(/RAM) bundle: use its own threshold
    if (not alerted) and (price is not None) and is_cpu_mobo_combo:
        if price < CPU_MOBO_BUNDLE_PRICE_LIMIT:
            new_matches.append((title, entry.link, f"CPU+Mobo Bundle ${price}"))
            alerted = True

    # CPU Bundle: only alert when there's a price and it's under the bundle threshold
    if (not alerted) and (price is not None) and is_cpu_bundle:
        if price < CPU_BUNDLE_PRICE_LIMIT:
            new_matches.append((title, entry.link, f"CPU Bundle ${price}"))
            alerted = True

    # Regular CPU: alert for CPUs under CPU_PRICE_LIMIT. This covers any CPU* tags,
    # known models, and general CPU/processor posts.
    if (not alerted) and (price is not None) and (has_any_cpu_tag or is_processor_word or is_known_model):
        if price < CPU_PRICE_LIMIT:
            # build a helpful reason: include known models if present
            reason_parts = [f"CPU ${price}"]
            if is_known_model:
                matched_models = [m.upper() for m in CPU_MODELS if m in normalized]
                if matched_models:
                    reason_parts.append("models: " + ",".join(matched_models))
            new_matches.append((title, entry.link, " ".join(reason_parts)))
            alerted = True

    # Standalone Motherboards: no CPU tag, just motherboard/mobo and under threshold
    if (not alerted) and (price is not None) and has_any_mobo and (not has_any_cpu_tag):
        if price < MOTHERBOARD_PRICE_LIMIT:
            new_matches.append((title, entry.link, f"Motherboard ${price}"))
            alerted = True

    # GPU filter: look for the GPU keyword/tag and compare price
    if (not alerted) and (KEYWORD.lower() in title_lower):
        if price is not None and price < GPU_PRICE_LIMIT:
            new_matches.append((title, entry.link, f"GPU ${price}"))
            alerted = True

    # Monitor filter: look for the word 'monitor' and compare price
    if (not alerted) and ("monitor" in title_lower):
        if price is not None and price < MONITOR_PRICE_LIMIT:
            new_matches.append((title, entry.link, f"Monitor ${price}"))
            alerted = True

    # PSU 1000W: alert when title mentions PSU (or power supply) and 1000W (or 1kW)
    if (not alerted) and has_1000w_psu(title_lower):
        reason = "PSU 1000W"
        if price is not None:
            reason += f" ${price}"
        new_matches.append((title, entry.link, reason))
        alerted = True

    # Mark post as seen only if we alerted (so skipped posts can be re-evaluated later)
    if alerted:
        seen_posts.add(post_id)

# --- PROCESS r/CanadianHardwareSwap FEED (keyword-only GPU hunt) ---
# We only look for specific high-end GPU model keywords, regardless of price.
chs_feed = feedparser.parse(CHS_FEED_URL)

# Build robust regex patterns that allow optional vendor prefixes and flexible spacing/hyphens.
# We'll match case-insensitively using normalized comparisons where needed.
chs_keyword_labels_and_regexes = [
    ("RTX 5090", re.compile(r"\brtx\s*-?\s*5090\b", re.IGNORECASE)),
    ("5090", re.compile(r"(?<!\d)5090(?!\d)", re.IGNORECASE)),
    ("RTX 4090", re.compile(r"\brtx\s*-?\s*4090\b", re.IGNORECASE)),
    ("4090", re.compile(r"(?<!\d)4090(?!\d)", re.IGNORECASE)),
    ("RTX 4080 SUPER", re.compile(r"\brtx\s*-?\s*4080\s*-?\s*super\b", re.IGNORECASE)),
    ("4080 SUPER", re.compile(r"\b4080\s*-?\s*super\b", re.IGNORECASE)),
    ("RTX 4080", re.compile(r"\brtx\s*-?\s*4080\b", re.IGNORECASE)),
    ("4080", re.compile(r"(?<!\d)4080(?!\d)", re.IGNORECASE)),
    ("RTX 5070 Ti", re.compile(r"\brtx\s*-?\s*5070\s*-?\s*ti\b", re.IGNORECASE)),
    ("5070 Ti", re.compile(r"\b5070\s*-?\s*ti\b", re.IGNORECASE)),
    ("RX 9070 XT", re.compile(r"\brx\s*-?\s*9070\s*-?\s*xt\b", re.IGNORECASE)),
    ("9070 XT", re.compile(r"\b9070\s*-?\s*xt\b", re.IGNORECASE)),
    ("RX 9070", re.compile(r"\brx\s*-?\s*9070\b", re.IGNORECASE)),
    ("RX 7900 XTX", re.compile(r"\brx\s*-?\s*7900\s*-?\s*xtx\b", re.IGNORECASE)),
    ("7900 XTX", re.compile(r"\b7900\s*-?\s*xtx\b", re.IGNORECASE)),
    ("RX 7900 XT", re.compile(r"\brx\s*-?\s*7900\s*-?\s*xt\b", re.IGNORECASE)),
    ("7900 XT", re.compile(r"\b7900\s*-?\s*xt\b", re.IGNORECASE)),
]

for entry in chs_feed.entries:
    post_id = entry.get("id", entry.get("link"))
    title = entry.get("title", "")

    if post_id in seen_posts:
        continue

    title_lower = title.lower()

    # Only match when the keyword appears under the [H] (Have) section, not [W] (Want).
    # We'll locate [H] and [W] (case-insensitive) and search only within the [H] segment.
    def _index_of_tag(s: str, tag: str) -> int:
        try:
            return s.index(tag)
        except ValueError:
            return -1

    idx_h = _index_of_tag(title_lower, "[h]")
    idx_w = _index_of_tag(title_lower, "[w]")

    # Derive the H segment of the title: content after [H] up to [W] (if [W] comes after [H]).
    h_segment = ""
    if idx_h != -1:
        if idx_w != -1 and idx_w > idx_h:
            h_segment = title_lower[idx_h:idx_w]
        else:
            h_segment = title_lower[idx_h:]

    # If there is no [H], we do not alert (strict interpretation per request).
    if not h_segment:
        continue

    alerted_chs = False

    match_label = extract_first_match(h_segment, chs_keyword_labels_and_regexes)
    if match_label and not alerted_chs:
        # Alert only when the keyword appears under [H].
        new_matches.append((title, entry.link, f"CHS match (H): {match_label}"))
        seen_posts.add(post_id)
        alerted_chs = True

    # Also detect 1000W PSU in [H]
    if (not alerted_chs) and has_1000w_psu(h_segment):
        new_matches.append((title, entry.link, "CHS match (H): 1000W PSU"))
        seen_posts.add(post_id)
        alerted_chs = True

# --- SEND ALERTS ---
# If dry-run, print a human-readable list and avoid sending or marking side effects.
# Otherwise, build a single message body with reasons and links and push via Apprise.
if new_matches:
    if dry_run_mode:
        print(f"🔍 DRY RUN: Found {len(new_matches)} matching deals (no notifications sent):")
        for i, (title, link, reason) in enumerate(new_matches, 1):
            print(f"\n{i}. {title}")
            print(f"   Reason: {reason}")
            print(f"   Link: {link}")
        log(f"DRY RUN: Found {len(new_matches)} deals. No notification sent.")
    else:
        # message includes title, reason, and link for each match
        message = "\n\n".join([f"{t}\n{reason}\n{u}" for t, u, reason in new_matches])
        # If ROLE_MENTION is configured, prepend it so Discord will ping the role.
        if ROLE_MENTION:
            message = f"{ROLE_MENTION}\n\n" + message
        notifier.notify(
            body=message
        )
        print(f"✅ Sent {len(new_matches)} alert(s)")
        log(f"Found {len(new_matches)} new deals. Notification sent.")
else:
    if dry_run_mode:
        print("🔍 DRY RUN: No deals found matching filters.")
    else:
        print("No new deals found matching filters.")
    log("No new deals found.")

# --- SAVE UPDATED SEEN POSTS ---
# Save updated seen posts atomically
tmp_seen = SEEN_FILE + ".tmp"
with open(tmp_seen, "w", encoding="utf-8") as f:
    for pid in seen_posts:
        f.write(pid + "\n")
os.replace(tmp_seen, SEEN_FILE)
