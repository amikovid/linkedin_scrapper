"""
LinkedIn Post Pattern Scraper  (two-step: parse → LLM classify)

Step 1: Parse HTML activity page → extract posts → filter top performers
Step 2: Send cleaned post data to Claude API → classify against testing framework
Output: Terminal table + CSV

Usage:
    python linkedin_scraper.py <file1.html> [file2.html ...]
    python linkedin_scraper.py "example data.txt" --top 5 --output results.csv
    python linkedin_scraper.py "example data.txt" --top-pct 40   # top 40%
"""

import re
import sys
import csv
import json
import argparse
import io
from pathlib import Path
from bs4 import BeautifulSoup
from tabulate import tabulate
import anthropic

# Force UTF-8 on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Testing Framework (used verbatim in the system prompt)
# ---------------------------------------------------------------------------

FRAMEWORK = """
## Variable 1: Hook Type
Which opening pattern was used?
- Contradicting: breaks pattern, challenges assumption. e.g. "Something shifted and nobody announced it."
- Emotional/Scene-first: opens with a specific sensory or personal moment before revealing the topic
- Authority/Social Proof: leads with a credential, name, or impressive number as social proof
- Transformation (before/after): maps a before-state to an after-state
- Data/Stat-first: leads with a number, dollar amount, time span, or concrete count
- Analogy: "like a / imagine / think of it as" framing
- Polarizing/Hot Take: strong opinion, "brutal truth", "unpopular opinion"
- Question: opens with a direct question

Note: A big specific number (count, $, time) followed by the story behind it is common in high-performing posts — classify as Data/Stat-first even if it reads like a story opener.

## Variable 2: Content Body Type
What structure does the body of the post follow?
- Story Arc: setup → complication → resolution; one person's journey
- Data Narrative: surprising stat → interpretation → implication
- Contrarian Reframe: states common belief → shows why it's wrong/incomplete → offers better frame
- List/Framework: 3-5 numbered or bulleted points with brief explanations
- Quote + Context: person said X → what that means → implication
- Observation Chain: string of related observations building to one conclusion

## Variable 3: CTA / Closing Type
How does the post end?
- Open Question (specific): a specific question that prompts a real answer (not a generic nod)
- Implication Statement: ends on a thought that leaves the reader thinking — no ask, no wrap-up
- Direct Quote as Closer: final line is a direct quote from a real person
- Link Drop (no CTA language): drops a URL or resource without "check it out" language
- Hard CTA: explicit ask — "follow", "share", "repost", "comment below", "sign up", "DM me"
- No Close (just stops): post ends on the final insight with zero wrap-up

## Variable 4: Person Featured
Who (if anyone) does the post center on?
- Well-known Public Figure: widely recognizable name (e.g. Elon Musk, Steve Jobs, Oprah)
- Mid-tier Influencer: credible in the niche but not mainstream famous
- Unknown Researcher/Study: cites a study, paper, or academic source
- Podcast Guest: a guest from a podcast or interview context
- No Person (self-story): the author themselves is the subject — first-person narrative
- No Person (brand/observation): no individual featured; opinion or observation post

## Variable 5: Visual Format
What visual format does the post use?
- Text Only: no image, no document, no video
- Single Image: one photo, graphic, or quote card
- Carousel (document): multi-slide PDF/document carousel
- Video: native video
- Article/Link: shared article or external link with preview card
"""

CLASSIFICATION_SCHEMA = {
    "hook_type": "one of: Contradicting | Emotional/Scene-first | Authority/Social Proof | Transformation | Data/Stat-first | Analogy | Polarizing/Hot Take | Question",
    "body_type": "one of: Story Arc | Data Narrative | Contrarian Reframe | List/Framework | Quote + Context | Observation Chain",
    "cta_type": "one of: Open Question (specific) | Implication Statement | Direct Quote as Closer | Link Drop (no CTA language) | Hard CTA | No Close (just stops)",
    "person_featured": "one of: Well-known Public Figure | Mid-tier Influencer | Unknown Researcher/Study | Podcast Guest | No Person (self-story) | No Person (brand/observation)",
    "hook_analysis": "1-2 sentence explanation of why you chose this hook type",
    "body_analysis": "1-2 sentence explanation of why you chose this body type",
    "cta_analysis": "1-2 sentence explanation of why you chose this CTA type",
    "standout_pattern": "The single most replicable structural pattern in this post (1 sentence)",
}


# ---------------------------------------------------------------------------
# Step 1: HTML Parsing
# ---------------------------------------------------------------------------

def detect_format(post_soup) -> str:
    if post_soup.find(class_=re.compile(r"update-components-document")):
        return "Carousel (document)"
    if post_soup.find(class_=re.compile(r"update-components-image--single")):
        return "Single Image"
    if post_soup.find(class_=re.compile(r"update-components-video")):
        return "Video"
    if post_soup.find(class_=re.compile(r"update-components-article|feed-shared-article")):
        return "Article/Link"
    return "Text Only"


def parse_posts(html_content: str, source_file: str) -> list[dict]:
    """Parse all posts from a LinkedIn activity HTML page. Returns raw data only — no classification."""
    soup = BeautifulSoup(html_content, "lxml")

    title_tag = soup.find("title")
    author = "Unknown"
    if title_tag:
        parts = title_tag.text.split("|")
        if len(parts) >= 2:
            author = parts[1].strip()

    post_divs = soup.find_all("div", class_=re.compile(r"feed-shared-update-v2\b"))

    # De-duplicate by data-urn
    seen_urns = set()
    unique_posts = []
    for div in post_divs:
        urn = div.get("data-urn", "")
        if urn and urn not in seen_urns:
            seen_urns.add(urn)
            unique_posts.append(div)
        elif not urn:
            unique_posts.append(div)

    posts = []
    for idx, post in enumerate(unique_posts, 1):
        # Post text
        text_div = post.find("div", class_=re.compile(r"update-components-text"))
        raw_text = ""
        if text_div:
            for br in text_div.find_all("br"):
                br.replace_with("\n")
            raw_text = text_div.get_text(separator="").strip()
            raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)

        if not raw_text:
            continue

        # Reactions
        reactions = 0
        btn = post.find("button", attrs={"aria-label": re.compile(r"\d+ reactions?")})
        if btn:
            m = re.search(r"([\d,]+) reactions?", btn["aria-label"])
            if m:
                reactions = int(m.group(1).replace(",", ""))

        # Comments
        comments = 0
        btn = post.find("button", attrs={"aria-label": re.compile(r"\d+ comments?")})
        if btn:
            m = re.search(r"([\d,]+) comments?", btn["aria-label"])
            if m:
                comments = int(m.group(1).replace(",", ""))

        # Reposts
        reposts = 0
        btn = post.find("button", attrs={"aria-label": re.compile(r"\d+ reposts?")})
        if btn:
            m = re.search(r"([\d,]+) reposts?", btn["aria-label"])
            if m:
                reposts = int(m.group(1).replace(",", ""))

        # Timestamp
        timestamp = ""
        sub_desc = post.find("span", class_=re.compile(r"update-components-actor__sub-description"))
        if sub_desc:
            visible = sub_desc.find("span", attrs={"aria-hidden": "true"})
            if visible:
                raw_ts = visible.get_text(" ", strip=True)
                m = re.match(r"([\d]+[smhdw])", raw_ts)
                if m:
                    timestamp = m.group(1)

        # Engagement score: weight comments 2x (per framework — comments signal real engagement)
        engagement_score = reactions + (comments * 2) + reposts

        posts.append({
            "source_file": Path(source_file).name,
            "author": author,
            "post_num": idx,
            "text": raw_text,
            "hook_line": raw_text.splitlines()[0][:120],
            "word_count": len(raw_text.split()),
            "format": detect_format(post),
            "reactions": reactions,
            "comments": comments,
            "reposts": reposts,
            "comment_like_ratio": round(comments / reactions, 3) if reactions > 0 else 0.0,
            "engagement_score": engagement_score,
            "time_posted": timestamp,
        })

    return posts


def select_top_posts(posts: list[dict], top_n: int | None, top_pct: int | None) -> list[dict]:
    """Return top performers by engagement score."""
    ranked = sorted(posts, key=lambda p: p["engagement_score"], reverse=True)
    if top_n:
        return ranked[:top_n]
    if top_pct:
        n = max(1, round(len(ranked) * top_pct / 100))
        return ranked[:n]
    # Default: top 40%
    n = max(1, round(len(ranked) * 0.4))
    return ranked[:n]


# ---------------------------------------------------------------------------
# Step 2: Build API payload & classify
# ---------------------------------------------------------------------------

def build_post_payload(post: dict) -> str:
    """Format a single post as clean structured text for the LLM."""
    return f"""POST #{post['post_num']} — {post['author']}
Source: {post['source_file']}
Format: {post['format']} | Words: {post['word_count']} | Time posted: {post['time_posted'] or 'unknown'}
Engagement: {post['reactions']} reactions | {post['comments']} comments | {post['reposts']} reposts | C/L ratio: {post['comment_like_ratio']}

--- POST TEXT ---
{post['text']}
--- END POST TEXT ---"""


SYSTEM_PROMPT = f"""You are an expert LinkedIn content analyst. Your job is to classify LinkedIn posts against a specific testing framework and identify replicable patterns.

{FRAMEWORK}

You will receive one or more posts. For EACH post, return a JSON object with these exact keys:
{json.dumps(CLASSIFICATION_SCHEMA, indent=2)}

Return your response as a JSON array — one object per post, in the same order as the input.
Be precise. Use only the exact option strings listed in the schema (e.g. "Story Arc", not "story arc").
Base your classification on the actual text, not the engagement numbers."""


def classify_posts_with_api(posts: list[dict], api_key: str | None = None) -> list[dict]:
    """Send top posts to Claude API for classification. Returns posts with classification fields added."""
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    # Build the user message: all posts concatenated
    user_content = "\n\n" + ("=" * 60) + "\n\n"
    user_content += f"\n\n{'='*60}\n\n".join(build_post_payload(p) for p in posts)
    user_content += f"\n\n{'='*60}\n\nClassify each of the {len(posts)} posts above. Return a JSON array with {len(posts)} objects."

    print(f"\n[API] Sending {len(posts)} posts to Claude for classification...", flush=True)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # fast + cheap for structured extraction
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()

    # Extract JSON array from response (handle markdown code blocks)
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON array found in API response:\n{raw[:500]}")

    classifications = json.loads(json_match.group(0))

    if len(classifications) != len(posts):
        raise ValueError(f"Expected {len(posts)} classifications, got {len(classifications)}")

    # Merge classification results back into post dicts
    enriched = []
    for post, cls in zip(posts, classifications):
        enriched.append({**post, **cls})

    return enriched


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

DISPLAY_COLS = [
    "post_num", "author", "hook_line",
    "hook_type", "body_type", "cta_type", "person_featured", "format",
    "word_count", "reactions", "comments", "reposts", "comment_like_ratio",
]

DISPLAY_HEADERS = [
    "#", "Author", "Hook (first line)",
    "Hook Type", "Body Type", "CTA Type", "Person Featured", "Format",
    "Words", "Reactions", "Comments", "Reposts", "C/L Ratio",
]

ANALYSIS_COLS = ["post_num", "author", "hook_type", "hook_analysis", "body_type", "body_analysis", "cta_type", "cta_analysis", "standout_pattern"]
ANALYSIS_HEADERS = ["#", "Author", "Hook Type", "Hook Analysis", "Body Type", "Body Analysis", "CTA Type", "CTA Analysis", "Standout Pattern"]


def truncate(val, n=35):
    s = str(val)
    return s if len(s) <= n else s[:n - 1] + "…"


def print_results(posts: list[dict]):
    print(f"\n{'='*80}")
    print(f"  TOP POSTS — Classification Results")
    print(f"{'='*80}\n")

    # Main metrics + classification table
    rows = []
    for p in posts:
        row = []
        for col in DISPLAY_COLS:
            val = p.get(col, "")
            if col == "hook_line":
                val = truncate(val, 40)
            row.append(val)
        rows.append(row)
    print(tabulate(rows, headers=DISPLAY_HEADERS, tablefmt="rounded_outline"))

    # Analysis / reasoning table
    print(f"\n{'='*80}")
    print(f"  LLM ANALYSIS — Why these classifications were made")
    print(f"{'='*80}\n")
    analysis_rows = []
    for p in posts:
        row = []
        for col in ANALYSIS_COLS:
            val = p.get(col, "")
            if col in ("hook_analysis", "body_analysis", "cta_analysis", "standout_pattern"):
                val = truncate(val, 50)
            row.append(val)
        analysis_rows.append(row)
    print(tabulate(analysis_rows, headers=ANALYSIS_HEADERS, tablefmt="rounded_outline"))
    print()


def save_csv(posts: list[dict], output_path: str):
    if not posts:
        return
    # Put classification fields right after engagement, full text last
    priority = [
        "source_file", "author", "post_num", "hook_line",
        "hook_type", "hook_analysis",
        "body_type", "body_analysis",
        "cta_type", "cta_analysis",
        "person_featured", "format",
        "word_count", "reactions", "comments", "reposts",
        "comment_like_ratio", "engagement_score", "time_posted",
        "standout_pattern", "text",
    ]
    all_keys = list(posts[0].keys())
    fieldnames = [k for k in priority if k in all_keys] + [k for k in all_keys if k not in priority]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(posts)
    print(f"CSV saved → {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract top LinkedIn posts from HTML and classify them via Claude API."
    )
    parser.add_argument("files", nargs="+", help="HTML/txt files to process")
    parser.add_argument(
        "--top", "-n", type=int, default=None,
        help="Number of top posts to classify per file (by engagement score). Default: top 40%%."
    )
    parser.add_argument(
        "--top-pct", type=int, default=None,
        help="Percentage of top posts to classify (e.g. 40 = top 40%%). Overridden by --top."
    )
    parser.add_argument(
        "--output", "-o", default="linkedin_analysis.csv",
        help="Output CSV filename (default: linkedin_analysis.csv)"
    )
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV export")
    parser.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    all_classified = []

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"[!] File not found: {filepath}", file=sys.stderr)
            continue

        # --- Step 1: Parse ---
        print(f"\n[Step 1] Parsing: {path.name} ...", end=" ", flush=True)
        content = path.read_text(encoding="utf-8", errors="ignore")
        posts = parse_posts(content, filepath)
        print(f"{len(posts)} posts found.")

        if not posts:
            continue

        top_posts = select_top_posts(posts, args.top, args.top_pct)
        print(f"[Step 1] Selected top {len(top_posts)} posts by engagement score.")

        # Show quick engagement preview before API call
        preview_rows = [[p["post_num"], truncate(p["hook_line"], 55),
                         p["reactions"], p["comments"], p["reposts"], p["engagement_score"]]
                        for p in top_posts]
        print(tabulate(preview_rows,
                       headers=["#", "Hook (first line)", "Reactions", "Comments", "Reposts", "Eng.Score"],
                       tablefmt="simple"))

        # --- Step 2: Classify ---
        try:
            classified = classify_posts_with_api(top_posts, args.api_key)
            print(f"[API] Classification complete.")
            print_results(classified)
            all_classified.extend(classified)
        except Exception as e:
            print(f"[!] API error: {e}", file=sys.stderr)
            raise

    if not all_classified:
        print("No posts classified.")
        return

    if not args.no_csv:
        save_csv(all_classified, args.output)


if __name__ == "__main__":
    main()
