"""
Autoresearch Runner — Autonomous Content Optimization for GeniusGTX

Implements Karpathy's autoresearch pattern adapted for content optimization.
Pulls analytics, identifies what's working, generates hypotheses, and creates
A/B test variations as Typefully drafts.

Usage:
    python -m pipeline.autoresearch_runner --baseline     # compute and save 30-day baseline
    python -m pipeline.autoresearch_runner --analyze      # show performance insights
    python -m pipeline.autoresearch_runner --experiment   # run one full experiment cycle
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests
from anthropic import Anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

# ── Config ──────────────────────────────────────────────────────────────────

TYPEFULLY_API_KEY = os.getenv("TYPEFULLY_API_KEY")
TYPEFULLY_SOCIAL_SET_ID = int(os.getenv("TYPEFULLY_SOCIAL_SET_ID", "151393"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"

RESULTS_FILE = PROJECT_ROOT / "autoresearch_results.tsv"

# ── Format Definitions ──────────────────────────────────────────────────────

# The 11 GeniusGTX content formats and their signature patterns for detection
FORMAT_PATTERNS = {
    "Tuki QRT": {
        "patterns": [r"tuki", r"🐕", r"woof", r"bark.*qrt"],
        "markers": ["qrt", "quote retweet"],
    },
    "Bark QRT": {
        "patterns": [r"bark", r"🐕.*qrt"],
        "markers": ["qrt", "quote retweet"],
    },
    "Commentary Post": {
        "patterns": [r"^(?!.*thread).*commentary", r"take:"],
        "markers": ["commentary"],
        "length_range": (5, 20),  # lines
    },
    "Stat Bomb": {
        "patterns": [r"\d+[%$MBK]", r"stat[s]?\s*bomb", r"^\d"],
        "markers": ["stat", "data", "number"],
        "has_numbers": True,
    },
    "Explainer": {
        "patterns": [r"here'?s (how|why|what)", r"explained", r"breakdown"],
        "markers": ["explainer"],
        "length_range": (15, 40),
    },
    "Contrarian Take": {
        "patterns": [r"unpopular", r"hot take", r"actually.*wrong", r"nobody.*talking"],
        "markers": ["contrarian", "hot take"],
    },
    "Multi-Source Explainer": {
        "patterns": [r"sources?:", r"according to", r"multiple.*report"],
        "markers": ["multi-source"],
        "length_range": (20, 50),
    },
    "Thread": {
        "patterns": [r"thread", r"🧵", r"\d+/\d+"],
        "markers": ["thread"],
    },
    "Video Clip Post": {
        "patterns": [r"clip", r"watch", r"video"],
        "markers": ["video", "clip"],
    },
    "Clip Commentary": {
        "patterns": [r"clip.*commentary", r"watching.*this"],
        "markers": ["clip commentary"],
    },
    "Clip Thread": {
        "patterns": [r"clip.*thread", r"🧵.*clip"],
        "markers": ["clip thread"],
    },
}


# ── Typefully Analytics ─────────────────────────────────────────────────────

def _typefully_headers() -> dict:
    return {
        "Authorization": f"Bearer {TYPEFULLY_API_KEY}",
        "Content-Type": "application/json",
    }


def fetch_typefully_analytics(start_date: str, end_date: str) -> list[dict]:
    """Fetch post analytics from Typefully for a date range."""
    url = (
        f"https://api.typefully.com/v2/social-sets/{TYPEFULLY_SOCIAL_SET_ID}"
        f"/analytics/x/posts"
    )
    all_results = []
    offset = 0
    limit = 100

    while True:
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
            "offset": offset,
            "include_replies": "false",
        }
        resp = requests.get(url, headers=_typefully_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        all_results.extend(results)

        if data.get("next") and len(results) == limit:
            offset += limit
        else:
            break

    return all_results


def create_typefully_draft(content: str, tags: list[str] | None = None) -> dict:
    """Create a draft in Typefully with optional tags."""
    url = f"https://api.typefully.com/v2/social-sets/{TYPEFULLY_SOCIAL_SET_ID}/drafts"
    payload = {
        "content": content,
        "platforms": ["x"],
    }
    if tags:
        payload["tags"] = tags

    resp = requests.post(url, headers=_typefully_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Format Detection ────────────────────────────────────────────────────────

def detect_format(text: str) -> str:
    """Infer the content format from post text using pattern matching.

    Returns the best-guess format name or 'Unknown'.
    """
    text_lower = text.lower()
    lines = text.strip().split("\n")
    line_count = len(lines)

    scores: dict[str, int] = defaultdict(int)

    for fmt, rules in FORMAT_PATTERNS.items():
        # Check regex patterns
        for pattern in rules.get("patterns", []):
            if re.search(pattern, text_lower):
                scores[fmt] += 2

        # Check keyword markers
        for marker in rules.get("markers", []):
            if marker in text_lower:
                scores[fmt] += 1

        # Check length range if defined
        length_range = rules.get("length_range")
        if length_range:
            low, high = length_range
            if low <= line_count <= high:
                scores[fmt] += 1

        # Check number density for stat bombs
        if rules.get("has_numbers"):
            number_count = len(re.findall(r"\d+", text))
            if number_count >= 5:
                scores[fmt] += 2

    if not scores:
        return "Unknown"

    return max(scores, key=scores.get)


# ── Core Functions ──────────────────────────────────────────────────────────

def get_baseline_metrics(days: int = 30) -> dict:
    """Pull last N days of Typefully analytics and compute baseline averages.

    Returns:
        dict with avg_views, avg_engagement, total_posts, period_start, period_end
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"Fetching Typefully analytics: {start_date} to {end_date}...")
    posts = fetch_typefully_analytics(start_date, end_date)

    if not posts:
        print("  No posts found in the period.")
        return {
            "avg_views": 0,
            "avg_engagement": 0,
            "total_posts": 0,
            "period_start": start_date,
            "period_end": end_date,
        }

    total_views = sum(p["metrics"]["impressions"] for p in posts)
    total_engagement = sum(p["metrics"]["engagement"]["total"] for p in posts)
    count = len(posts)

    baseline = {
        "avg_views": round(total_views / count),
        "avg_engagement": round(total_engagement / count, 2),
        "total_posts": count,
        "total_views": total_views,
        "total_engagement": total_engagement,
        "period_start": start_date,
        "period_end": end_date,
    }

    print(f"  Posts: {count}")
    print(f"  Avg views/post: {baseline['avg_views']:,}")
    print(f"  Avg engagement/post: {baseline['avg_engagement']}")

    return baseline


def analyze_performance_by_format(days: int = 30) -> dict[str, dict]:
    """Group Typefully analytics by inferred format.

    Returns:
        dict of format_name -> {avg_views, avg_engagement, count}
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"Analyzing format performance: {start_date} to {end_date}...")
    posts = fetch_typefully_analytics(start_date, end_date)

    if not posts:
        print("  No posts found.")
        return {}

    # Group by detected format
    format_buckets: dict[str, list[dict]] = defaultdict(list)
    for post in posts:
        text = post.get("preview_text", "") or post.get("text", "")
        fmt = detect_format(text)
        format_buckets[fmt].append(post)

    results = {}
    for fmt, fmt_posts in sorted(format_buckets.items(), key=lambda x: -len(x[1])):
        views = [p["metrics"]["impressions"] for p in fmt_posts]
        engagement = [p["metrics"]["engagement"]["total"] for p in fmt_posts]
        count = len(fmt_posts)

        results[fmt] = {
            "avg_views": round(sum(views) / count),
            "avg_engagement": round(sum(engagement) / count, 2),
            "count": count,
            "best_views": max(views),
            "total_views": sum(views),
        }

    return results


def analyze_top_patterns(days: int = 30, top_n: int = 10) -> dict:
    """Identify top performing posts and analyze common patterns.

    Returns:
        dict with top_posts list and pattern_insights.
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"Analyzing top patterns: {start_date} to {end_date}...")
    posts = fetch_typefully_analytics(start_date, end_date)

    if not posts:
        print("  No posts found.")
        return {"top_posts": [], "pattern_insights": {}}

    # Sort by views (primary) then engagement (secondary)
    sorted_posts = sorted(
        posts,
        key=lambda p: (p["metrics"]["impressions"], p["metrics"]["engagement"]["total"]),
        reverse=True,
    )
    top_posts = sorted_posts[:top_n]

    # Analyze patterns in top posts
    hook_styles = []
    lengths = []
    formats_used = []

    for post in top_posts:
        text = post.get("preview_text", "") or post.get("text", "")
        lines = text.strip().split("\n")
        first_line = lines[0] if lines else ""

        # Classify hook style
        if first_line.endswith("?"):
            hook_styles.append("question")
        elif re.match(r"^\d", first_line):
            hook_styles.append("number_lead")
        elif any(w in first_line.lower() for w in ["nobody", "everyone", "most people"]):
            hook_styles.append("contrarian")
        elif len(first_line) < 50:
            hook_styles.append("short_punchy")
        else:
            hook_styles.append("statement")

        lengths.append(len(text))
        formats_used.append(detect_format(text))

    # Count patterns
    hook_counts = defaultdict(int)
    for h in hook_styles:
        hook_counts[h] += 1
    format_counts = defaultdict(int)
    for f in formats_used:
        format_counts[f] += 1

    avg_length = round(sum(lengths) / len(lengths)) if lengths else 0

    pattern_insights = {
        "dominant_hook_style": max(hook_counts, key=hook_counts.get) if hook_counts else "unknown",
        "hook_style_distribution": dict(hook_counts),
        "avg_length_chars": avg_length,
        "format_distribution": dict(format_counts),
        "top_post_views": [p["metrics"]["impressions"] for p in top_posts],
    }

    top_post_summaries = []
    for post in top_posts:
        text = post.get("preview_text", "") or post.get("text", "")
        top_post_summaries.append({
            "preview": text[:150],
            "views": post["metrics"]["impressions"],
            "engagement": post["metrics"]["engagement"]["total"],
            "format": detect_format(text),
            "hook_line": text.strip().split("\n")[0][:100] if text.strip() else "",
        })

    return {
        "top_posts": top_post_summaries,
        "pattern_insights": pattern_insights,
    }


def generate_variation(topic: str, format_name: str) -> dict:
    """Use Claude to generate 2 A/B test variations of a post.

    Variation A: uses current writing rules as-is.
    Variation B: uses a proposed modification (hypothesis).

    Returns:
        dict with variation_a, variation_b, hypothesis, format_name, topic
    """
    anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

    # Load current writing rules
    writing_rules_path = PROJECT_ROOT / "skills" / "writing-system" / "SKILL.md"
    hook_rules_path = PROJECT_ROOT / "skills" / "hook-writing-system" / "SKILL.md"

    writing_rules = ""
    hook_rules = ""
    if writing_rules_path.exists():
        writing_rules = writing_rules_path.read_text()[:3000]
    if hook_rules_path.exists():
        hook_rules = hook_rules_path.read_text()[:3000]

    prompt = f"""You are an expert content optimizer for the GeniusGTX X/Twitter account.

CURRENT WRITING RULES (summary):
{writing_rules[:2000]}

CURRENT HOOK RULES (summary):
{hook_rules[:2000]}

TASK: Generate two variations of a post for A/B testing.

Topic: {topic}
Format: {format_name}

VARIATION A (Control):
Write a post using the current writing and hook rules EXACTLY as they are.
Follow every guideline strictly.

VARIATION B (Experiment):
Write a post with ONE specific modification. Choose one of these experiment types:
- Hook experiment: Try a different opener formula (e.g., start with a number, start with "Nobody talks about...", start with a bold claim)
- Rhythm experiment: Try shorter/punchier sentences or longer flowing ones
- Structure experiment: Try a different arrangement of the same content

STATE YOUR HYPOTHESIS clearly: what you changed and why you think it might perform better.

Respond in this exact JSON format:
{{
    "variation_a": "the full post text for variation A",
    "variation_b": "the full post text for variation B",
    "hypothesis": "one sentence describing what was changed and the expected effect",
    "experiment_type": "hook|rhythm|structure",
    "specific_change": "brief description of the single variable changed"
}}

Return ONLY valid JSON. No markdown fences."""

    response = anthropic.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text.strip()

    # Parse JSON from response — handle potential markdown fences
    if response_text.startswith("```"):
        response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
        response_text = re.sub(r"\s*```$", "", response_text)

    result = json.loads(response_text)
    result["topic"] = topic
    result["format_name"] = format_name
    result["generated_at"] = datetime.now().isoformat()

    return result


def log_experiment(experiment_data: dict) -> None:
    """Append experiment result to autoresearch_results.tsv.

    Expected keys: commit, score, area, status, eye_test, description
    """
    file_exists = RESULTS_FILE.exists()

    with open(RESULTS_FILE, "a", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        if not file_exists:
            writer.writerow(["commit", "score", "area", "status", "eye_test", "description"])

        writer.writerow([
            experiment_data.get("commit", "n/a"),
            experiment_data.get("score", "0"),
            experiment_data.get("area", "unknown"),
            experiment_data.get("status", "pending"),
            experiment_data.get("eye_test", "-"),
            experiment_data.get("description", "").replace("\t", " "),
        ])

    print(f"  Logged to {RESULTS_FILE}")


def run_experiment_cycle() -> dict:
    """Full autonomous experiment cycle.

    1. Analyze what's working (top patterns + format performance)
    2. Hypothesize an improvement
    3. Generate A/B test variations
    4. Create Typefully drafts tagged autoresearch-test
    5. Log the experiment

    Returns:
        dict summarizing the experiment.
    """
    print("=" * 60)
    print("AUTORESEARCH EXPERIMENT CYCLE")
    print("=" * 60)

    # Step 1: Analyze current performance
    print("\n[1/5] Analyzing current performance...")
    baseline = get_baseline_metrics(days=30)
    format_perf = analyze_performance_by_format(days=30)
    top_patterns = analyze_top_patterns(days=30, top_n=10)

    if baseline["total_posts"] == 0:
        print("  No posts found. Cannot run experiment without baseline data.")
        return {"status": "skipped", "reason": "no baseline data"}

    # Step 2: Use Claude to hypothesize an improvement
    print("\n[2/5] Generating hypothesis...")
    anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

    analysis_summary = json.dumps({
        "baseline": baseline,
        "format_performance": format_perf,
        "top_patterns": top_patterns["pattern_insights"],
    }, indent=2, default=str)

    hypothesis_response = anthropic.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""You are an autonomous content researcher for GeniusGTX (X/Twitter).

Here is the current performance data:
{analysis_summary}

Based on this data, propose ONE specific experiment to improve content performance.
Focus on HOOKS first (they drive views).

Respond in JSON:
{{
    "topic": "a specific topic to write about for the test",
    "format": "the format to test with (pick from the 11 GeniusGTX formats)",
    "hypothesis": "what you want to test and why",
    "area": "hooks|voice|format|examples",
    "rationale": "2-3 sentences on why this experiment based on the data"
}}

Return ONLY valid JSON.""",
        }],
    )

    hypothesis_text = hypothesis_response.content[0].text.strip()
    if hypothesis_text.startswith("```"):
        hypothesis_text = re.sub(r"^```(?:json)?\s*", "", hypothesis_text)
        hypothesis_text = re.sub(r"\s*```$", "", hypothesis_text)

    hypothesis = json.loads(hypothesis_text)
    print(f"  Hypothesis: {hypothesis['hypothesis']}")
    print(f"  Area: {hypothesis['area']}")
    print(f"  Format: {hypothesis['format']}")
    print(f"  Topic: {hypothesis['topic']}")

    # Step 3: Generate A/B variations
    print("\n[3/5] Generating A/B test variations...")
    variations = generate_variation(
        topic=hypothesis["topic"],
        format_name=hypothesis["format"],
    )
    print(f"  Variation A (control): {variations['variation_a'][:80]}...")
    print(f"  Variation B (experiment): {variations['variation_b'][:80]}...")
    print(f"  Specific change: {variations.get('specific_change', 'n/a')}")

    # Step 3.5: Gate check — must-haves validation
    print("\n[3.5/5] Running must-haves gate check...")
    anthropic_for_gate = Anthropic(api_key=ANTHROPIC_API_KEY)
    gate_results = {}
    for label, key in [("A", "variation_a"), ("B", "variation_b")]:
        gate_resp = anthropic_for_gate.messages.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": (
                "You are a strict quality gate for GeniusGTX content. Review this post against ALL rules:\n"
                "- Voice: Systems thinker, incentive-first, calibrated urgency, no moralizing\n"
                "- Formatting: Max 2 sentences/paragraph, no em dashes, one idea per paragraph, hook <280 chars\n"
                "- Hooks: Visualization test, pivot phrase, approved pivot verbs, exact numbers\n"
                "- Quality: No banned AI words (delve/tapestry/nuanced/pivotal), no filler transitions, no hedging, varied rhythm\n"
                "- Brand: Never cynical, never breathless, never preachy, defensible positions\n\n"
                f"POST:\n{variations[key]}\n\n"
                "Respond EXACTLY: PASS: yes/no | FAILURES: [list or none]"
            )}],
        )
        gate_text = gate_resp.content[0].text
        passed = "pass: yes" in gate_text.lower()
        gate_results[label] = {"passed": passed, "raw": gate_text}
        status_icon = "✅" if passed else "❌"
        print(f"  Variation {label}: {status_icon} {'PASSED' if passed else 'FAILED'}")
        if not passed:
            print(f"    {gate_text[:200]}")

    if not gate_results["B"]["passed"]:
        print("  ⚠️  Variation B failed gate — flagging for review but still creating drafts")

    # Step 4: Create Typefully drafts
    print("\n[4/5] Creating Typefully drafts tagged autoresearch-test...")
    drafts_created = []
    for label, key in [("A (control)", "variation_a"), ("B (experiment)", "variation_b")]:
        text = variations[key]
        try:
            draft = create_typefully_draft(
                content=text,
                tags=["autoresearch-test"],
            )
            drafts_created.append({
                "label": label,
                "draft_id": draft.get("id", "unknown"),
            })
            print(f"  Created draft {label}: {draft.get('id', 'unknown')}")
        except Exception as e:
            print(f"  Failed to create draft {label}: {e}")
            drafts_created.append({"label": label, "error": str(e)})

    # Step 5: Log the experiment
    print("\n[5/5] Logging experiment...")
    experiment_record = {
        "commit": "n/a",
        "score": str(baseline["avg_views"]),
        "area": hypothesis["area"],
        "status": "pending",
        "eye_test": "-",
        "description": (
            f"experiment: {hypothesis['hypothesis']} | "
            f"format: {hypothesis['format']} | "
            f"change: {variations.get('specific_change', 'n/a')}"
        ),
    }
    log_experiment(experiment_record)

    # Summary
    summary = {
        "status": "created",
        "baseline_avg_views": baseline["avg_views"],
        "baseline_avg_engagement": baseline["avg_engagement"],
        "hypothesis": hypothesis,
        "variations": {
            "a_preview": variations["variation_a"][:200],
            "b_preview": variations["variation_b"][:200],
            "specific_change": variations.get("specific_change", "n/a"),
        },
        "drafts": drafts_created,
        "next_step": "Toan reviews drafts tagged autoresearch-test. Approved ones publish. Check analytics after 72h.",
    }

    print("\n" + "=" * 60)
    print("EXPERIMENT CYCLE COMPLETE")
    print("=" * 60)
    print(f"Baseline: {baseline['avg_views']:,} avg views, {baseline['avg_engagement']} avg engagement")
    print(f"Hypothesis: {hypothesis['hypothesis']}")
    print(f"Drafts created: {len([d for d in drafts_created if 'error' not in d])}/2")
    print(f"Next: Review drafts in Typefully (tagged autoresearch-test)")
    print("=" * 60)

    return summary


# ── Display Helpers ─────────────────────────────────────────────────────────

def print_format_table(format_perf: dict) -> None:
    """Pretty-print format performance data."""
    if not format_perf:
        print("  No format data available.")
        return

    print(f"\n  {'Format':<25} {'Count':>6} {'Avg Views':>12} {'Avg Eng':>10} {'Best Views':>12}")
    print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*10} {'-'*12}")
    for fmt, data in sorted(format_perf.items(), key=lambda x: -x[1]["avg_views"]):
        print(
            f"  {fmt:<25} {data['count']:>6} {data['avg_views']:>12,} "
            f"{data['avg_engagement']:>10.1f} {data['best_views']:>12,}"
        )


def print_top_posts(top_data: dict) -> None:
    """Pretty-print top posts and pattern insights."""
    insights = top_data.get("pattern_insights", {})
    if insights:
        print(f"\n  Dominant hook style: {insights.get('dominant_hook_style', 'unknown')}")
        print(f"  Hook distribution: {insights.get('hook_style_distribution', {})}")
        print(f"  Avg top-post length: {insights.get('avg_length_chars', 0):,} chars")
        print(f"  Format distribution: {insights.get('format_distribution', {})}")

    posts = top_data.get("top_posts", [])
    if posts:
        print(f"\n  Top {len(posts)} posts:")
        for i, post in enumerate(posts, 1):
            print(f"\n  #{i} — {post['views']:,} views, {post['engagement']:,} engagement [{post['format']}]")
            print(f"  Hook: {post['hook_line']}")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Autoresearch Runner — autonomous content optimization"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--baseline", action="store_true",
        help="Compute and save 30-day baseline metrics",
    )
    group.add_argument(
        "--analyze", action="store_true",
        help="Show performance insights (format breakdown + top patterns)",
    )
    group.add_argument(
        "--experiment", action="store_true",
        help="Run one full experiment cycle",
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Number of days to look back (default: 30)",
    )
    args = parser.parse_args()

    if args.baseline:
        print("=" * 60)
        print("AUTORESEARCH BASELINE")
        print("=" * 60)
        baseline = get_baseline_metrics(days=args.days)

        # Save baseline to results file
        log_experiment({
            "commit": "baseline",
            "score": str(baseline["avg_views"]),
            "area": "-",
            "status": "keep",
            "eye_test": "-",
            "description": (
                f"baseline from {baseline['period_start']} to {baseline['period_end']} | "
                f"{baseline['total_posts']} posts | "
                f"avg views {baseline['avg_views']} | "
                f"avg engagement {baseline['avg_engagement']}"
            ),
        })

        # Also save as JSON for easy programmatic access
        baseline_file = PROJECT_ROOT / "autoresearch_baseline.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline, f, indent=2)
        print(f"\n  Baseline saved to {baseline_file}")

    elif args.analyze:
        print("=" * 60)
        print("AUTORESEARCH ANALYSIS")
        print("=" * 60)

        print("\n--- Baseline Metrics ---")
        baseline = get_baseline_metrics(days=args.days)

        print("\n--- Performance by Format ---")
        format_perf = analyze_performance_by_format(days=args.days)
        print_format_table(format_perf)

        print("\n--- Top Post Patterns ---")
        top_data = analyze_top_patterns(days=args.days, top_n=10)
        print_top_posts(top_data)

        print("\n" + "=" * 60)

    elif args.experiment:
        run_experiment_cycle()


if __name__ == "__main__":
    main()
