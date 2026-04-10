"""
Maya — Lead Writer for GeniusGTX
Takes approved hooks + raw facts → writes full thread bodies for X/Twitter.
Also writes shorter-form content. Versatile writer with strong voice.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

SKILLS_DIR = PROJECT_ROOT / "skills" / "writing-system"
DOCS_DIR = PROJECT_ROOT / "docs"
MUTATION_LOG_PATH = Path(__file__).resolve().parent / "mutation_log.json"

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


def load_skill_files() -> str:
    """Load all skill files into a single context string."""
    files = {
        "SKILL.md": SKILLS_DIR / "SKILL.md",
        "voice-guide.md": SKILLS_DIR / "references" / "voice-guide.md",
        "narrator-phrases.md": SKILLS_DIR / "references" / "narrator-phrases.md",
        "thread-examples.md": SKILLS_DIR / "references" / "thread-examples.md",
        "content-generation-playbook.md": DOCS_DIR / "content-generation-playbook.md",
        "media-workflow-guide.md": DOCS_DIR / "media-workflow-guide.md",
    }
    context_parts = []
    for name, path in files.items():
        if path.exists():
            content = path.read_text(encoding="utf-8")
            context_parts.append(f"--- BEGIN {name} ---\n{content}\n--- END {name} ---")
    return "\n\n".join(context_parts)


def build_system_prompt(skill_context: str) -> str:
    """Build Maya's full system prompt."""
    return f"""You are Maya, the lead writer for GeniusGTX.

You write full thread bodies for X/Twitter and shorter-form content. You receive hooks from Jordan (or topics with raw facts) and produce publication-ready writing.

You are a writer first. You have strong opinions about phrasing, structure, and rhythm. You care about every sentence. You do not produce filler.

Follow the complete writing system below. This is your voice, your rules, your references.

{skill_context}

CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}
"""


CHAT_SYSTEM_PROMPT = """You are Maya, the lead writer on the GeniusGTX content team.

You're a real teammate. When someone messages you, just talk normally. Be direct, thoughtful, opinionated about writing and content.

Your specialty is writing full threads and long-form content for X/Twitter, but you only do that when explicitly asked (e.g. "write a thread", "write the body for this hook", "turn this into content").

When you're NOT writing threads:
- Chat naturally. Short, honest replies.
- You can discuss writing craft, brainstorm angles, give opinions on content strategy.
- You care deeply about voice and rhythm. You have opinions.
- You know the GeniusGTX brand: ancient civilizations, systemic shifts, hidden figures, cognitive science, business strategy.

When someone DOES ask you to write, you switch into full writing mode with the complete system.
"""


def chat(message: str, conversation_history: list | None = None) -> str:
    """Have a normal conversation as Maya."""
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": message})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=CHAT_SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


def write_thread(hook: str, raw_facts: str = "", topic: str = "", conversation_history: list | None = None) -> str:
    """
    Write a full thread body given a hook and/or raw facts.

    Args:
        hook: The approved hook from Jordan (or empty if just a topic).
        raw_facts: Raw facts, research, or transcript to inform the thread.
        topic: The topic if no hook is provided.
        conversation_history: Prior messages for feedback continuity.
    """
    skill_context = load_skill_files()
    system_prompt = build_system_prompt(skill_context)

    # Build the user message
    parts = []
    if hook:
        parts.append(f"HOOK:\n{hook}")
    if topic:
        parts.append(f"TOPIC: {topic}")
    if raw_facts:
        parts.append(f"RAW FACTS / RESEARCH:\n{raw_facts}")

    if not hook and not topic:
        return "I need either a hook or a topic to write from. What are we working with?"

    instruction = """

Write the COMPLETE post — hook and body together as one finished piece.

OUTPUT RULES:
- Output ONLY the post text. Nothing else.
- No preamble ("Here is the body:", "Here's the post:"). Just the raw content.
- No meta-commentary, no angle suggestions, no notes to yourself.
- Maximum 2 sentences per paragraph. Then a blank line.
- One idea per paragraph.
- No em dashes. Split into new sentences.
- End with the exact CTA: "That's a wrap." (own line) → 1-2 sentences about @GeniusGTX → "We are ONE genius away." (last line)
- NEVER end with "Follow @GeniusGTX for more."

The first words of your response ARE the first words of the post."""

    user_content = "\n\n".join(parts) + instruction

    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_content})

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text


def process_feedback(feedback: str, conversation_history: list) -> str:
    """Process user feedback on a thread and return improved version."""
    skill_context = load_skill_files()
    system_prompt = build_system_prompt(skill_context)

    messages = list(conversation_history)
    messages.append({
        "role": "user",
        "content": f"""FEEDBACK: {feedback}

Instructions:
1. Identify which tweet(s) the feedback targets.
2. Extract the specific rule implied by this feedback.
3. Apply it immediately. Rewrite the affected section.
4. Present the mutation log entry:

MUTATION LOG
Original line: [what was written]
Feedback: [exact words]
Rule extracted: [the new guideline]
Status: TESTING

5. Present the improved section."""
    })

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text


def revise_post(original_text: str, feedback: str) -> str:
    """
    Apply targeted feedback to an existing post and return ONLY the revised text.

    Unlike process_feedback(), this function:
    - Returns ONLY the final post text — no explanations, no mutation logs, no commentary
    - Makes minimal changes — only fixes what the feedback asks for
    - Preserves the original structure, voice, and length

    This is used by the Telegram review bot to edit drafts in place.
    """
    skill_context = load_skill_files()
    system_prompt = build_system_prompt(skill_context)

    messages = [
        {"role": "assistant", "content": original_text},
        {"role": "user", "content": f"""REVISION FEEDBACK: {feedback}

RULES:
- Apply ONLY the changes requested in the feedback above.
- Keep everything else EXACTLY as it is — same structure, same voice, same length.
- If the feedback targets specific lines, only change those lines.
- Do NOT add, remove, or rearrange sections that weren't mentioned.
- Do NOT add any explanations, notes, or commentary.

OUTPUT:
Return ONLY the revised post text. Nothing else. No "Here's the revised version:" prefix.
No "I changed X because Y" suffix. Just the post, ready to publish."""},
    ]

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text.strip()


def load_mutation_log() -> list:
    if MUTATION_LOG_PATH.exists():
        return json.loads(MUTATION_LOG_PATH.read_text(encoding="utf-8"))
    return []


def save_mutation_log(log: list):
    MUTATION_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


# --- CLI interface ---

def main():
    print("=" * 60)
    print("MAYA — GeniusGTX Writer")
    print("=" * 60)
    print("Commands:")
    print("  'write: [hook or topic]' — write a thread")
    print("  'feedback: ...' — give feedback on the last thread")
    print("  Anything else — just chat")
    print("  'quit' — exit")
    print("=" * 60)

    conversation_history = []

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Maya signing off.")
            break

        if user_input.lower().startswith("feedback:"):
            feedback_text = user_input[len("feedback:"):].strip()
            print("\nMaya is revising...\n")
            response = process_feedback(feedback_text, conversation_history)
            conversation_history.append({"role": "user", "content": f"FEEDBACK: {feedback_text}"})
            conversation_history.append({"role": "assistant", "content": response})

        elif user_input.lower().startswith("write:"):
            content = user_input[len("write:"):].strip()
            print("\nMaya is writing...\n")
            response = write_thread(hook=content)
            conversation_history = [
                {"role": "user", "content": f"Write thread for: {content}"},
                {"role": "assistant", "content": response},
            ]

        else:
            response = chat(user_input, conversation_history=conversation_history if conversation_history else None)
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": response})
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]

        print(response)


if __name__ == "__main__":
    main()
