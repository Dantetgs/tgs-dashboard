"""
X Content Engine — Dashboard

Shows pipeline run history, generated posts, and published Typefully drafts.

Run with:
    streamlit run dashboard/app.py
(from the x-content-engine/ project root)
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
RUN_HISTORY_FILE = DATA_DIR / "run_history.json"
PIPELINE_STATUS_FILE = DATA_DIR / "pipeline_status.json"
TYPEFULLY_LOG_FILE = DATA_DIR / "typefully_log.json"

VERTICAL_ICONS = {
    "ai": "🤖",
    "crypto": "₿",
    "tech": "💻",
    "entertainment": "🎬",
}

STATUS_COLORS = {
    "ready_to_publish": "success",
    "skipped_no_new_stories": "info",
    "skipped": "info",
    "error": "error",
    "generated": "success",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_json(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def fmt_dt(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%b %d  %H:%M")
    except Exception:
        return iso[:16] if iso else "—"


def duration_str(start: str, end: str) -> str:
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        secs = int(delta.total_seconds())
        return f"{secs // 60}m {secs % 60}s"
    except Exception:
        return "—"


def vertical_icon(v: str) -> str:
    return VERTICAL_ICONS.get(v, "📌")


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="X Content Engine",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_refresh = st.columns([6, 1])
with col_title:
    st.title("🐦 X Content Engine")
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# ── Live status banner ────────────────────────────────────────────────────────
pipeline_status = load_json(PIPELINE_STATUS_FILE)
if pipeline_status:
    run_status = pipeline_status.get("status")
    if run_status == "running":
        current = pipeline_status.get("current_vertical") or "starting"
        st.warning(f"⚙️ **Pipeline running** — currently processing: `{current}`")
    elif run_status == "success":
        completed = fmt_dt(pipeline_status.get("completed_at", ""))
        st.success(f"✅ Last run succeeded · {completed}")
    elif run_status == "error":
        completed = fmt_dt(pipeline_status.get("completed_at", ""))
        st.error(f"❌ Last run had errors · {completed}")
else:
    st.info("No pipeline runs yet. Run `python -m src.pipeline --all` to get started.")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Run History", "📝 Generated Posts", "✅ Published to Typefully"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Run History
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    history = load_json(RUN_HISTORY_FILE)

    if not history:
        st.info("No runs recorded yet.")
    else:
        runs = list(reversed(history))

        # Summary metrics
        total_runs = len(runs)
        successful = sum(1 for r in runs if r.get("status") == "success")
        total_posts = sum(
            sum(v.get("posts_generated", 0) for v in r.get("results", {}).values())
            for r in runs
        )
        skipped_runs = sum(
            sum(
                1 for v in r.get("results", {}).values()
                if v.get("status") == "skipped_no_new_stories"
            )
            for r in runs
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Runs", total_runs)
        m2.metric("Successful", f"{successful} / {total_runs}")
        m3.metric("Posts Generated", total_posts)
        m4.metric("Verticals Skipped (no new stories)", skipped_runs)

        st.write("")

        # Per-run expandable rows
        for run in runs[:30]:
            run_status = run.get("status", "unknown")
            icon = "✅" if run_status == "success" else "❌" if run_status == "error" else "⏳"
            started = fmt_dt(run.get("started_at", ""))
            dur = duration_str(run.get("started_at", ""), run.get("completed_at", ""))
            results = run.get("results", {})
            posts_count = sum(v.get("posts_generated", 0) for v in results.values())
            run_id = run.get("run_id", "")

            with st.expander(f"{icon}  {started}   ·   {dur}   ·   {posts_count} posts   ·   `{run_id}`"):
                if not results:
                    st.caption("No vertical results recorded.")
                for vertical, result in results.items():
                    vstatus = result.get("status", "unknown")
                    vicon = vertical_icon(vertical)

                    if vstatus == "ready_to_publish":
                        posts = result.get("posts_generated", 0)
                        tweets = result.get("tweets_scraped", "?")
                        stories = result.get("stories_found", "?")
                        st.success(
                            f"{vicon} **{vertical}** — {posts} posts generated  "
                            f"_(scraped {tweets} tweets → {stories} stories)_"
                        )
                    elif vstatus == "skipped_no_new_stories":
                        st.info(f"{vicon} **{vertical}** — no new stories (already covered today)")
                    elif vstatus in ("skipped", "generated"):
                        reason = result.get("reason", "")
                        st.info(f"{vicon} **{vertical}** — skipped  _{reason}_")
                    elif vstatus == "error":
                        error = result.get("error", "unknown error")
                        st.error(f"{vicon} **{vertical}** — ❌ {error}")
                    else:
                        st.write(f"{vicon} **{vertical}** — {vstatus}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Generated Posts
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    if not OUTPUT_DIR.exists():
        st.info("No generated posts yet.")
    else:
        date_dirs = sorted(
            [d for d in OUTPUT_DIR.iterdir() if d.is_dir()],
            reverse=True,
        )

        if not date_dirs:
            st.info("No generated posts yet.")
        else:
            date_options = [d.name for d in date_dirs]
            selected_date = st.selectbox("Date", date_options, index=0)

            post_files = sorted((OUTPUT_DIR / selected_date).glob("*_posts.json"))
            verticals_available = [f.stem.replace("_posts", "") for f in post_files]

            if not verticals_available:
                st.info(f"No posts saved for {selected_date}.")
            else:
                selected_verticals = st.multiselect(
                    "Verticals",
                    verticals_available,
                    default=verticals_available,
                )

                for vertical in selected_verticals:
                    posts_file = OUTPUT_DIR / selected_date / f"{vertical}_posts.json"
                    posts = load_json(posts_file)
                    if not posts:
                        continue

                    icon = vertical_icon(vertical)
                    st.subheader(f"{icon} {vertical.upper()}")

                    for i, post in enumerate(posts, 1):
                        title = post.get("source_story_title", f"Post {i}")
                        fmt = post.get("format_type", "")
                        generated = post.get("generated_at", "")[:16].replace("T", "  ")
                        content = post.get("content", "")
                        summary = post.get("source_story_summary", "")

                        with st.expander(f"**{title[:100]}**"):
                            col_meta1, col_meta2 = st.columns(2)
                            col_meta1.caption(f"Format: `{fmt}`")
                            col_meta2.caption(f"Generated: {generated}")

                            if summary:
                                st.caption(f"_{summary[:200]}_")

                            st.text_area(
                                "Draft content",
                                value=content,
                                height=220,
                                disabled=True,
                                key=f"post_{selected_date}_{vertical}_{i}",
                                label_visibility="collapsed",
                            )

                    st.write("")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Published to Typefully
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    typefully_log = load_json(TYPEFULLY_LOG_FILE)

    if not typefully_log:
        st.info("Nothing published to Typefully yet.")
    else:
        real_drafts = [e for e in typefully_log if not e.get("dry_run")]
        dry_run_entries = [e for e in typefully_log if e.get("dry_run")]

        p1, p2 = st.columns(2)
        p1.metric("Drafts Published", len(real_drafts))
        p2.metric("Dry Runs", len(dry_run_entries))

        if not real_drafts:
            st.info("No real drafts published yet (only dry runs).")
        else:
            st.write("")
            for entry in reversed(real_drafts[-50:]):
                icon = vertical_icon(entry.get("vertical", ""))
                pushed = fmt_dt(entry.get("pushed_at", ""))
                title = (entry.get("story_title") or "")[:80]
                fmt = entry.get("format_type", "")
                url = entry.get("typefully_url", "")
                draft_id = entry.get("draft_id", "")

                with st.expander(f"{icon}  {pushed}  —  {title}"):
                    col_a, col_b = st.columns(2)
                    col_a.caption(f"Format: `{fmt}`")
                    col_b.caption(f"Draft ID: `{draft_id}`")

                    if url and "typefully.com" in url and draft_id != "dry-run":
                        st.markdown(f"[Open in Typefully →]({url})")
