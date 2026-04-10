#!/usr/bin/env python3
"""
Account Manager Scheduling Skill

Schedules "Ready to Post" content from GeniusGTX's Notion pipeline to Typefully
with intelligent timing respecting velocity rules and anti-repetition logic.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Velocity constraints
VELOCITY_RULES = {
    "max_posts_per_day": (5, 8),  # min, max
    "max_qrts_per_day": 3,
    "max_longform_per_day": 2,  # Thread, Explainer, Educational
    "min_spacing_hours": 2,  # Between different ideas
    "min_spacing_same_idea_hours": 3,  # Between posts from same idea
}

# Format categories for velocity limits
FORMAT_CATEGORIES = {
    "qrt": ["Tuki QRT", "Bark QRT"],
    "longform": ["Thread", "Explainer", "Multi-Source Explainer", "Educational Long-Form + Video"],
    "other": [
        "Stat Bomb", "Commentary Post", "Contrarian Take",
        "Clip Commentary", "Video Clip Post", "Clip Thread",
        "Short Caption + Video Clip", "Quote-Extract + Video"
    ]
}

# Staggering windows (in hours) by urgency
STAGGER_WINDOWS = {
    "🔴": {"first": (0, 0.25), "second": (1, 3), "third": (24, 48)},  # Breaking
    "🟡": {"first": (2, 4), "second": (4, 12), "third": (24, 48)},     # Trending
    "🟢": {"first": (0, 168), "second": (24, 168)},                     # Evergreen (spread over week)
}


class ScheduleOptimizer:
    """Optimizes content scheduling respecting all velocity and anti-repetition rules."""

    def __init__(self, timezone_offset: int = -5):
        """
        Initialize scheduler.

        Args:
            timezone_offset: UTC offset for scheduling (default: US Eastern = -5)
        """
        self.timezone_offset = timezone_offset
        self.scheduled_posts = []  # Posts scheduled in this run
        self.blocked_posts = []     # Posts that couldn't be scheduled

    def schedule_posts(self, posts: List[Dict], today: datetime = None) -> Dict:
        """
        Main scheduling method.

        Args:
            posts: List of post dicts with keys:
                   - id, title, format, urgency, idea_id, topic_tags,
                   - post_text, media_id (optional), source_url (optional)
            today: Reference date (default: now)

        Returns:
            Dict with 'scheduled', 'blocked', 'by_date' summaries
        """
        if today is None:
            today = datetime.now()

        self.scheduled_posts = []
        self.blocked_posts = []

        # Load existing scheduled posts (for today onwards)
        existing = self._load_existing_schedule(today)

        # Sort posts by urgency (breaking first)
        urgency_order = {"🔴": 0, "🟡": 1, "🟢": 2}
        posts = sorted(posts, key=lambda p: urgency_order.get(p.get("urgency"), 3))

        # Schedule each post
        for post in posts:
            scheduled_time = self._find_slot(
                post=post,
                today=today,
                existing=existing
            )

            if scheduled_time:
                self.scheduled_posts.append({
                    **post,
                    "scheduled_at": scheduled_time.isoformat()
                })
                existing.append({
                    "time": scheduled_time,
                    "idea_id": post.get("idea_id"),
                    "format": post.get("format"),
                    "topic": post.get("topic_tags", [])[0] if post.get("topic_tags") else None
                })
            else:
                self.blocked_posts.append({
                    **post,
                    "reason": "No available slot respecting velocity rules"
                })

        return self._build_summary(today)

    def _find_slot(self, post: Dict, today: datetime, existing: List[Dict]) -> Optional[datetime]:
        """Find the next available scheduling slot for a post."""
        urgency = post.get("urgency", "🟢")
        idea_id = post.get("idea_id")
        topic = (post.get("topic_tags") or [None])[0]

        # Determine search window based on urgency
        window = STAGGER_WINDOWS.get(urgency, STAGGER_WINDOWS["🟢"])
        search_hours = window.get("first", (0, 24))[1] * 24  # Convert to hours

        # Try each hour in the search window
        for hour_offset in range(int(search_hours)):
            candidate = today + timedelta(hours=hour_offset)

            if self._can_schedule_at(candidate, post, existing):
                return candidate

        return None

    def _can_schedule_at(self, time_slot: datetime, post: Dict, existing: List[Dict]) -> bool:
        """Check if post can be scheduled at given time slot."""
        idea_id = post.get("idea_id")
        post_format = post.get("format")
        topic = (post.get("topic_tags") or [None])[0]

        # Get posts scheduled around this time
        day_posts = [p for p in existing if p["time"].date() == time_slot.date()]

        # Check daily velocity limits
        if len(day_posts) >= VELOCITY_RULES["max_posts_per_day"][1]:
            return False

        # Check QRT limit
        qrt_count = sum(1 for p in day_posts if p["format"] in FORMAT_CATEGORIES["qrt"])
        if qrt_count >= VELOCITY_RULES["max_qrts_per_day"] and post_format in FORMAT_CATEGORIES["qrt"]:
            return False

        # Check long-form limit
        lf_count = sum(1 for p in day_posts if p["format"] in FORMAT_CATEGORIES["longform"])
        if lf_count >= VELOCITY_RULES["max_longform_per_day"] and post_format in FORMAT_CATEGORIES["longform"]:
            return False

        # Check topic rotation (no 3 in a row of same topic)
        recent_topics = [p["topic"] for p in sorted(existing, key=lambda x: x["time"])[-2:]]
        if topic and len(recent_topics) >= 2 and all(t == topic for t in recent_topics):
            return False

        # Check spacing rules
        for existing_post in existing:
            time_diff = abs((time_slot - existing_post["time"]).total_seconds() / 3600)

            if existing_post["idea_id"] == idea_id:
                # Same idea: 3-hour minimum
                if time_diff < VELOCITY_RULES["min_spacing_same_idea_hours"]:
                    return False
            else:
                # Different ideas: 2-hour minimum
                if time_diff < VELOCITY_RULES["min_spacing_hours"]:
                    return False

        return True

    def _load_existing_schedule(self, from_date: datetime) -> List[Dict]:
        """Load posts already scheduled from Notion/Typefully."""
        # This would fetch from Notion via API in production
        # For now, return empty list
        return []

    def _build_summary(self, today: datetime) -> Dict:
        """Build summary of scheduling results."""
        by_date = {}
        for post in self.scheduled_posts:
            date_str = post["scheduled_at"].split("T")[0]
            if date_str not in by_date:
                by_date[date_str] = []
            by_date[date_str].append({
                "title": post.get("title"),
                "format": post.get("format"),
                "time": post["scheduled_at"]
            })

        return {
            "scheduled_count": len(self.scheduled_posts),
            "blocked_count": len(self.blocked_posts),
            "by_date": by_date,
            "blocked_posts": self.blocked_posts
        }


class NotionTypefullySync:
    """Syncs posts between Notion and Typefully."""

    def __init__(self, notion_api_key: str = None, typefully_api_key: str = None):
        """Initialize sync client."""
        self.notion_key = notion_api_key or os.getenv("NOTION_API_KEY")
        self.typefully_key = typefully_api_key or os.getenv("TYPEFULLY_API_KEY")

    def fetch_posts_to_schedule(self) -> List[Dict]:
        """Fetch posts from Notion marked as 'Ready to Schedule'."""
        # In production, this queries Notion API directly
        logger.info("Fetching posts from Notion (Long-Form Post Library + Idea Pipeline)")

        # Expected return structure:
        # [
        #   {
        #     "id": "notion-page-id",
        #     "title": "Post title",
        #     "format": "Stat Bomb",
        #     "urgency": "🟡 Trending",
        #     "idea_id": "IDEA-123",
        #     "topic_tags": ["AI", "Finance"],
        #     "post_text": "Hook + body",
        #     "media_id": optional,
        #     "source_url": optional
        #   }
        # ]
        return []

    def create_typefully_draft(self, post: Dict, scheduled_time: datetime) -> Optional[str]:
        """Create draft in Typefully and return draft ID."""
        logger.info(f"Creating Typefully draft: {post['title']}")

        draft_payload = {
            "platforms": {
                "x": {
                    "enabled": True,
                    "posts": [{
                        "text": post.get("post_text", ""),
                        "media_ids": [post["media_id"]] if post.get("media_id") else [],
                        "quote_post_url": post.get("source_url")
                    }]
                },
                "bluesky": {"enabled": False},
                "linkedin": {"enabled": False},
                "mastodon": {"enabled": False},
                "threads": {"enabled": False}
            },
            "publish_at": scheduled_time.isoformat(),
            "scratchpad_text": self._build_scratchpad(post, scheduled_time),
            "tags": ["needs-review"] + self._build_tags(post),
            "draft_title": post.get("title")
        }

        # In production, POST to Typefully API
        logger.info(f"  Payload: {json.dumps(draft_payload, indent=2)}")

        # Return mock draft ID
        return f"draft-{post['id']}"

    def update_notion_post_status(self, post_id: str, status: str, draft_id: str = None) -> bool:
        """Update Notion post status and link draft ID."""
        logger.info(f"Updating Notion post {post_id}: status={status}, draft_id={draft_id}")
        return True

    def _build_scratchpad(self, post: Dict, scheduled_time: datetime) -> str:
        """Build Typefully scratchpad metadata."""
        return f"""Source: {post.get('source_url', 'N/A')}
Source Type: {post.get('source_type', 'Articles')}
Notion Idea: https://www.notion.so/{post.get('idea_id', 'unknown').replace('-', '')}
Format: {post.get('format', 'Unknown')}
Urgency: {post.get('urgency', '🟢 Evergreen')}
Generated: {datetime.now().strftime('%Y-%m-%d')}
Scheduled For: {scheduled_time.strftime('%Y-%m-%d %H:%M (EST)')}"""

    def _build_tags(self, post: Dict) -> List[str]:
        """Build Typefully tags."""
        tags = []
        source_type = post.get("source_type", "articles")
        tags.append(f"source-{source_type.lower()}")

        # Add format category tag
        post_format = post.get("format", "").lower()
        if any(fmt in post_format for fmt in ["qrt", "quote", "bark", "tuki"]):
            tags.append("format-qrt")
        elif any(fmt in post_format for fmt in ["stat", "bomb"]):
            tags.append("format-statbomb")
        elif any(fmt in post_format for fmt in ["thread"]):
            tags.append("format-thread")

        return tags


def main(action: str = "schedule"):
    """Main entry point."""
    logger.info(f"Account Manager Skill started: action={action}")

    try:
        # Initialize components
        optimizer = ScheduleOptimizer()
        sync = NotionTypefullySync()

        # Fetch posts to schedule
        posts = sync.fetch_posts_to_schedule()
        logger.info(f"Found {len(posts)} posts to schedule")

        if not posts:
            logger.info("No posts to schedule")
            return {"status": "ok", "scheduled": 0}

        # Optimize scheduling
        schedule = optimizer.schedule_posts(posts)
        logger.info(f"Optimization result: {schedule['scheduled_count']} scheduled, {schedule['blocked_count']} blocked")

        # Create Typefully drafts
        for post in optimizer.scheduled_posts:
            draft_id = sync.create_typefully_draft(
                post,
                datetime.fromisoformat(post["scheduled_at"])
            )

            if draft_id:
                sync.update_notion_post_status(
                    post["id"],
                    "Scheduled",
                    draft_id
                )
            else:
                sync.update_notion_post_status(
                    post["id"],
                    "Blocked",
                    None
                )

        logger.info("✅ Scheduling complete")
        return {
            "status": "ok",
            **schedule
        }

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import json
    result = main("schedule")
    print(json.dumps(result, indent=2, default=str))
