"""
LinkedIn Pattern Scraper — Streamlit Frontend
Double-click launch.bat to open in browser, or deploy to Streamlit Community Cloud.
"""

import json
import csv
import io
import sys
import hashlib
from pathlib import Path
from datetime import date

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from linkedin_scraper import (
    parse_posts, parse_plain_text, select_top_posts,
    classify_posts_with_api, _normalise_text,
)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

CONFIG_FILE = Path(__file__).parent / ".scraper_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(data: dict):
    cfg = load_config()
    cfg.update(data)
    try:
        CONFIG_FILE.write_text(json.dumps(cfg))
    except Exception:
        pass


def get_secret_api_key() -> str:
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return ""


def input_hash(inputs: list, top_n, top_pct) -> str:
    """Stable hash of current inputs + settings. Changes only when content/settings change."""
    key = f"{top_n}|{top_pct}|" + "||".join(
        f"{label}:{fc}:{mode}:{hashlib.md5(content.encode(errors='replace')).hexdigest()}"
        for label, content, fc, mode in inputs
    )
    return hashlib.md5(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="LinkedIn Pattern Scraper", page_icon="🔍", layout="wide")
st.title("🔍 LinkedIn Pattern Scraper")
st.caption("Paste LinkedIn activity content → AI classifies posting patterns against the testing framework.")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Settings")

    secret_key = get_secret_api_key()
    cfg = load_config()
    cloud_mode = bool(secret_key)

    if cloud_mode:
        st.success("API key loaded from server secrets.", icon="🔒")
        api_key = secret_key
    else:
        api_key = st.text_input(
            "Anthropic API Key",
            value=cfg.get("api_key", ""),
            type="password",
            help="Saved locally — never sent anywhere except Anthropic's API.",
        )
        if api_key and api_key != cfg.get("api_key", ""):
            save_config({"api_key": api_key})
            st.success("API key saved.")

    st.divider()
    st.subheader("Post selection")
    selection_mode = st.radio("Select top posts by", ["Fixed count", "Percentage"])
    if selection_mode == "Fixed count":
        top_n = st.slider("Number of top posts to analyse", 1, 20, 5)
        top_pct = None
    else:
        top_pct = st.slider("Top % of posts by engagement", 10, 100, 40, step=10)
        top_n = None

    st.divider()
    st.caption("Engagement score = reactions + (comments × 2) + reposts.")

# ---------------------------------------------------------------------------
# Input tabs
# ---------------------------------------------------------------------------

tab_upload, tab_paste_html, tab_paste_text = st.tabs([
    "📁 Upload file", "📋 Paste HTML", "📝 Paste plain text (easiest)"
])

inputs = []  # (label, content, follower_count, mode)

with tab_upload:
    st.caption("Save a LinkedIn activity page with **Ctrl+S → Webpage, Complete** and upload.")
    uploaded_files = st.file_uploader(
        "Drop LinkedIn HTML or text files here",
        type=["html", "htm", "txt"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        for f in uploaded_files:
            fc = st.number_input(
                f"Follower count for **{f.name}** (0 = auto-detect)",
                min_value=0, value=0, step=1000, key=f"fc_upload_{f.name}",
            )
            raw = f.read().decode("utf-8", errors="replace")
            mode = "text" if f.name.endswith(".txt") else "html"
            inputs.append((f.name, raw, fc or None, mode))

with tab_paste_html:
    st.caption("Open LinkedIn → Ctrl+U (view source) → Ctrl+A, Ctrl+C → paste below.")
    pasted_label_html = st.text_input("Account name / label", value="Pasted HTML", key="lbl_html")
    pasted_fc_html = st.number_input("Follower count (0 = auto-detect)", min_value=0, value=0, step=1000, key="fc_paste_html")
    pasted_html = st.text_area("Paste HTML here", height=220, placeholder="<html>...</html>", key="paste_html")
    if pasted_html.strip():
        inputs.append((pasted_label_html or "Pasted HTML", pasted_html, pasted_fc_html or None, "html"))

with tab_paste_text:
    st.caption(
        "**Easiest:** Open LinkedIn activity page → **Ctrl+A** (select all) → **Ctrl+C** → paste below."
    )
    pasted_label_text = st.text_input("Account name / label", value="Pasted text", key="lbl_text")
    pasted_fc_text = st.number_input(
        "Follower count (look it up on their profile — needed for per-follower scoring)",
        min_value=0, value=0, step=1000, key="fc_paste_text",
    )
    pasted_text = st.text_area(
        "Paste everything here", height=300,
        placeholder="Select all on the LinkedIn page (Ctrl+A), copy (Ctrl+C), paste here (Ctrl+V)...",
        key="paste_text",
    )
    if pasted_text.strip():
        inputs.append((pasted_label_text or "Pasted text", pasted_text, pasted_fc_text or None, "text"))

# ---------------------------------------------------------------------------
# Decide whether to show Run button or go straight to cached results
# ---------------------------------------------------------------------------

if not inputs:
    st.info("Upload a file or paste content above to get started.")
    st.stop()

if not api_key:
    st.warning("Enter your Anthropic API key in the sidebar to run analysis.")
    st.stop()

current_hash = input_hash(inputs, top_n, top_pct)
has_cached_results = (
    st.session_state.get("result_hash") == current_hash
    and st.session_state.get("classified")
)

if not has_cached_results:
    # Inputs changed (or first run) — show the Run button
    if st.session_state.get("classified"):
        st.info("Content changed — click Run Analysis to update results.")
    run = st.button("▶ Run Analysis", type="primary", use_container_width=True)
    if not run:
        st.stop()

    # --- Parse ---
    all_top_posts = []
    parse_notes = []

    for label, content, follower_override, mode in inputs:
        content = _normalise_text(content)
        with st.spinner(f"Parsing {label}…"):
            posts = (parse_plain_text if mode == "text" else parse_posts)(
                content, label, follower_count=follower_override
            )

        if not posts:
            st.warning(f"No posts found in '{label}'.")
            continue

        top = select_top_posts(posts, top_n, top_pct)
        all_top_posts.extend(top)

        followers = posts[0].get("followers")
        follower_str = f"{followers:,} followers" if followers else "follower count unknown"
        sort_note = "per-follower score" if followers else "raw eng. score"
        parse_notes.append(
            f"**{label}** → {len(posts)} posts found, top {len(top)} selected by {sort_note} | {follower_str}"
        )

    if not all_top_posts:
        st.error("No posts could be extracted.")
        st.stop()

    # --- Classify ---
    with st.spinner(f"Sending {len(all_top_posts)} posts to Claude for classification…"):
        try:
            classified = classify_posts_with_api(all_top_posts, api_key)
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    # --- Cache everything in session state ---
    st.session_state["classified"] = classified
    st.session_state["parse_notes"] = parse_notes
    st.session_state["result_hash"] = current_hash

# Read results from session state — always, including after download clicks
classified = st.session_state["classified"]
parse_notes = st.session_state["parse_notes"]

# ---------------------------------------------------------------------------
# Display parse notes
# ---------------------------------------------------------------------------

for note in parse_notes:
    st.success(note)

# ---------------------------------------------------------------------------
# Engagement table
# ---------------------------------------------------------------------------

st.subheader("📊 Posts selected for analysis")

has_followers = any(p.get("followers") for p in classified)
engagement_rows = []
for p in classified:
    row = {
        "Author": p["author"], "#": p["post_num"],
        "Hook (first line)": p["hook_line"], "Format": p["format"],
        "Words": p["word_count"], "Reactions": p["reactions"],
        "Comments": p["comments"], "Reposts": p["reposts"],
        "C/L Ratio": p["comment_like_ratio"], "Eng. Score": p["engagement_score"],
    }
    if has_followers:
        row["Followers"]      = p.get("followers") or "—"
        row["Reactions/1k"]   = p.get("reactions_per_1k") or "—"
        row["Comments/1k"]    = p.get("comments_per_1k") or "—"
        row["Eng.Score/1k"]   = p.get("eng_score_per_1k") or "—"
    row["Time Posted"] = p["time_posted"]
    engagement_rows.append(row)

st.caption(
    "Sorted by Eng.Score/1k followers — normalised for account size." if has_followers
    else "No follower count provided — sorted by raw engagement score."
)
st.dataframe(pd.DataFrame(engagement_rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Classification table
# ---------------------------------------------------------------------------

st.subheader("🤖 AI Classification")
st.success("Classification complete.")

st.markdown("### Variable Classifications")
class_rows = []
for p in classified:
    row = {
        "Author": p["author"], "#": p["post_num"],
        "Hook (first line)": p["hook_line"],
        "Hook Type": p.get("hook_type", ""),
        "Body Type": p.get("body_type", ""),
        "CTA Type": p.get("cta_type", ""),
        "Person Featured": p.get("person_featured", ""),
        "Format": p["format"],
        "Emotional Triggers": p.get("emotional_triggers", ""),
        "Reactions": p["reactions"], "Comments": p["comments"],
        "C/L Ratio": p["comment_like_ratio"],
    }
    if p.get("eng_score_per_1k") is not None:
        row["Eng.Score/1k"] = p["eng_score_per_1k"]
    class_rows.append(row)
st.dataframe(pd.DataFrame(class_rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Per-post deep dive
# ---------------------------------------------------------------------------

st.markdown("### Per-Post Deep Dive")
for p in classified:
    label = (
        f"**Post #{p['post_num']} — {p['author']}** | "
        f"{p['reactions']} reactions · {p['comments']} comments · {p['reposts']} reposts"
    )
    with st.expander(label, expanded=False):
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("**Classification**")
            st.markdown(f"- **Hook Type:** {p.get('hook_type', '—')}")
            st.markdown(f"- **Body Type:** {p.get('body_type', '—')}")
            st.markdown(f"- **CTA Type:** {p.get('cta_type', '—')}")
            st.markdown(f"- **Person Featured:** {p.get('person_featured', '—')}")
            st.markdown(f"- **Format:** {p['format']}")
            st.markdown(f"- **Word Count:** {p['word_count']}")
            st.markdown("**Analysis**")
            st.markdown(f"*Hook:* {p.get('hook_analysis', '—')}")
            st.markdown(f"*Body:* {p.get('body_analysis', '—')}")
            st.markdown(f"*CTA:* {p.get('cta_analysis', '—')}")
            st.markdown(f"**Emotional Triggers:** {p.get('emotional_triggers', '—')}")
            st.markdown(f"*{p.get('emotional_triggers_analysis', '')}*")
            st.markdown("**Standout Pattern**")
            st.info(p.get("standout_pattern", "—"))
        with col2:
            st.markdown("**Verbatim Post Text**")
            st.text_area(
                label="", value=p["text"], height=350,
                key=f"text_{p['author']}_{p['post_num']}",
                label_visibility="collapsed",
            )

# ---------------------------------------------------------------------------
# Frequency summary
# ---------------------------------------------------------------------------

st.markdown("### Pattern Frequency Summary")
st.caption("Counts across all analysed posts. Download the full table below.")

VAR_COLS = {
    "Variable 1 — Hook Type": "hook_type",
    "Variable 2 — Body Type": "body_type",
    "Variable 3 — CTA Type": "cta_type",
    "Variable 4 — Person Featured": "person_featured",
    "Variable 5 — Format": "format",
}
# Variable 6 is multi-value per post — needs exploding before counting
MULTI_VALUE_COLS = {"Variable 6 — Emotional Triggers": "emotional_triggers"}

freq_tables: dict[str, pd.DataFrame] = {}

for label_var, field in VAR_COLS.items():
    counts = pd.Series([p.get(field, "") for p in classified]).value_counts().reset_index()
    counts.columns = ["Value", "Count"]
    freq_tables[label_var] = counts

for label_var, field in MULTI_VALUE_COLS.items():
    # Explode comma-separated trigger lists into individual counts
    all_triggers = []
    for p in classified:
        raw = p.get(field, "")
        for t in raw.split(","):
            t = t.strip()
            if t:
                all_triggers.append(t)
    counts = pd.Series(all_triggers).value_counts().reset_index()
    counts.columns = ["Value", "Count"]
    freq_tables[label_var] = counts

all_var_cols = st.columns(3)
for i, (label_var, df) in enumerate(freq_tables.items()):
    with all_var_cols[i % 3]:
        st.markdown(f"**{label_var}**")
        st.dataframe(df, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Build export payloads (always rebuilt from session state, cheap)
# ---------------------------------------------------------------------------

priority_keys = [
    "source_file", "author", "post_num", "hook_line",
    "hook_type", "hook_analysis", "body_type", "body_analysis",
    "cta_type", "cta_analysis", "person_featured", "format",
    "word_count", "reactions", "comments", "reposts",
    "comment_like_ratio", "engagement_score", "time_posted",
    "standout_pattern", "text",
]
all_keys = list(classified[0].keys())
fieldnames = [k for k in priority_keys if k in all_keys] + [k for k in all_keys if k not in priority_keys]

csv_buf = io.StringIO()
csv.DictWriter(csv_buf, fieldnames=fieldnames).writeheader() or None
writer = csv.DictWriter(csv_buf, fieldnames=fieldnames)
# reopen cleanly
csv_buf = io.StringIO()
dw = csv.DictWriter(csv_buf, fieldnames=fieldnames)
dw.writeheader()
dw.writerows(classified)

freq_rows = [
    {"Variable": v, "Value": row["Value"], "Count": int(row["Count"])}
    for v, df in freq_tables.items()
    for _, row in df.iterrows()
    if row["Value"]
]
freq_buf = io.StringIO()
fw = csv.DictWriter(freq_buf, fieldnames=["Variable", "Value", "Count"])
fw.writeheader()
fw.writerows(freq_rows)


def build_markdown_report(posts, freq_tables):
    authors = list(dict.fromkeys(p["author"] for p in posts))
    lines = [
        "# LinkedIn Post Analysis Report",
        f"**Generated:** {date.today()}",
        f"**Authors analysed:** {', '.join(authors)}",
        f"**Posts analysed:** {len(posts)}",
        "",
        "> **Framework reference:** TESTING-FRAMEWORK.md",
        "> Variables 1–5 map to the hypothesis tables in that document.",
        "> Classification values in backticks are machine-readable for LLM parsing.",
        "",
        "---", "", "## Pattern Frequency Summary", "",
    ]
    for var_label, df in freq_tables.items():
        lines += [f"### {var_label}", "", "| Value | Count |", "|-------|-------|"]
        for _, row in df.iterrows():
            lines.append(f"| {row['Value']} | {int(row['Count'])} |")
        lines.append("")
    lines += ["---", "", "## Per-Post Analysis", ""]
    for p in posts:
        followers_str = f"{p['followers']:,}" if p.get("followers") else "unknown"
        eng_per_1k = p.get("eng_score_per_1k", "n/a")
        lines += [
            f"### Post #{p['post_num']} — {p['author']}",
            "",
            f"**Engagement:** {p['reactions']} reactions · {p['comments']} comments · {p['reposts']} reposts · C/L ratio: {p['comment_like_ratio']}",
            f"**Followers:** {followers_str} | **Eng.Score/1k:** {eng_per_1k}",
            f"**Posted:** {p.get('time_posted', 'unknown')} ago",
            "",
            "#### Variable 1: Hook Type",
            f"**Classification:** `{p.get('hook_type', '—')}`",
            f"**Analysis:** {p.get('hook_analysis', '—')}",
            "",
            "#### Variable 2: Body Type",
            f"**Classification:** `{p.get('body_type', '—')}`",
            f"**Analysis:** {p.get('body_analysis', '—')}",
            "",
            "#### Variable 3: CTA Type",
            f"**Classification:** `{p.get('cta_type', '—')}`",
            f"**Analysis:** {p.get('cta_analysis', '—')}",
            "",
            "#### Variable 4: Person Featured",
            f"**Classification:** `{p.get('person_featured', '—')}`",
            "",
            "#### Variable 5: Format",
            f"**Classification:** `{p.get('format', '—')}`",
            "",
            "#### Variable 6: Emotional Triggers",
            f"**Active triggers:** `{p.get('emotional_triggers', '—')}`",
            f"**Analysis:** {p.get('emotional_triggers_analysis', '—')}",
            "",
            "#### Standout Replicable Pattern",
            f"> {p.get('standout_pattern', '—')}",
            "",
            "#### Verbatim Post Text",
            "```",
            p.get("text", ""),
            "```",
            "", "---", "",
        ]
    return "\n".join(lines)


md_content = build_markdown_report(classified, freq_tables)

# ---------------------------------------------------------------------------
# Export buttons
# ---------------------------------------------------------------------------

st.divider()
st.subheader("⬇️ Export")

col_dl1, col_dl2, col_dl3 = st.columns(3)
with col_dl1:
    st.download_button(
        "📥 Post data (CSV)",
        data=csv_buf.getvalue().encode("utf-8"),
        file_name="linkedin_posts.csv",
        mime="text/csv",
        use_container_width=True,
    )
with col_dl2:
    st.download_button(
        "📥 Frequency table (CSV)",
        data=freq_buf.getvalue().encode("utf-8"),
        file_name="linkedin_frequency.csv",
        mime="text/csv",
        use_container_width=True,
    )
with col_dl3:
    st.download_button(
        "📥 Full analysis (Markdown)",
        data=md_content.encode("utf-8"),
        file_name="linkedin_analysis.md",
        mime="text/markdown",
        use_container_width=True,
    )
