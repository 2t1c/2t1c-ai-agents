"""
Jordan — Hook Writing Agent for GeniusGTX
Takes a topic + raw facts → produces 3 scroll-stopping hooks for X/Twitter
"""

import os
import json
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

SKILLS_DIR = PROJECT_ROOT / "skills" / "hook-writing-system"
MUTATION_LOG_PATH = Path(__file__).resolve().parent / "mutation_log.json"

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


def load_skill_files() -> str:
    """Load all skill files into a single context string for the system prompt."""
    files = {
        "SKILL.md": SKILLS_DIR / "SKILL.md",
        "angle-finding.md": SKILLS_DIR / "references" / "angle-finding.md",
        "hook-anatomy.md": SKILLS_DIR / "references" / "hook-anatomy.md",
        "thread-types.md": SKILLS_DIR / "references" / "thread-types.md",
        "language-bank.md": SKILLS_DIR / "references" / "language-bank.md",
        "viral-hooks-swipe-file.md": SKILLS_DIR / "references" / "viral-hooks-swipe-file.md",
    }
    context_parts = []
    for name, path in files.items():
        content = path.read_text(encoding="utf-8")
        context_parts.append(f"--- BEGIN {name} ---\n{content}\n--- END {name} ---")
    return "\n\n".join(context_parts)


def build_system_prompt(skill_context: str) -> str:
    """Build Jordan's full system prompt with skill files embedded."""
    return f"""You are Jordan, the lead hook writer for GeniusGTX.

Your job: take a topic (and optionally raw facts) and produce 3 scroll-stopping hooks for X/Twitter.

You follow the complete hook writing system below. This is your brain — every rule, every reference, every example. You do not deviate.

CRITICAL RULES:
- Run the Autoresearch loop INTERNALLY. Never show the loop. Only show final output.
- Always run angle-finding FIRST before writing any hook.
- Score every hook against the 4-layer baseline rubric before presenting.
- Attach a certainty map to every hook.
- End with the feedback request prompt.
- Platform: X/Twitter ONLY.
- No em dashes — ever. Split into new sentences.
- One sentence per line.

{skill_context}

CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}
"""


def load_mutation_log() -> list:
    """Load the persistent mutation log."""
    if MUTATION_LOG_PATH.exists():
        return json.loads(MUTATION_LOG_PATH.read_text(encoding="utf-8"))
    return []


def save_mutation_log(log: list):
    """Save the mutation log to disk."""
    MUTATION_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def add_mutation(original_line: str, feedback: str, rule_extracted: str):
    """Add a mutation entry to the log."""
    log = load_mutation_log()
    entry = {
        "date": datetime.now().isoformat(),
        "original_line": original_line,
        "feedback": feedback,
        "rule_extracted": rule_extracted,
        "status": "TESTING",
        "approvals": 0,
    }
    log.append(entry)
    save_mutation_log(log)
    return entry


CHAT_SYSTEM_PROMPT = """You are Jordan, the lead hook writer on the GeniusGTX content team.

You're a real teammate. When someone messages you, just talk normally. Be direct, friendly, sharp. You have opinions about content, writing, and the GeniusGTX brand.

Your specialty is writing scroll-stopping hooks for X/Twitter, but you don't do that unless someone explicitly asks you to write hooks (e.g. "hook me", "write hooks about", "give me hooks for", "write a hook").

When you're NOT writing hooks:
- Just chat like a normal person. Short, natural replies.
- You can discuss topics, brainstorm ideas, give opinions on content strategy, talk about angles.
- Keep it conversational. No need for formal structure.
- You know the GeniusGTX brand deeply: ancient civilizations, systemic shifts, hidden figures, cognitive science, business strategy.

When someone DOES ask for hooks, you switch into full hook-writing mode with the complete system.
"""


def chat(message: str, conversation_history: list = None) -> str:
    """Have a normal conversation as Jordan without loading the full hook system."""
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


def generate_hooks(topic: str, raw_facts: str = "", conversation_history: list = None) -> str:
    """
    Generate 3 hooks for a given topic.

    Args:
        topic: The topic to write hooks about.
        raw_facts: Optional raw facts/research to inform the hooks.
        conversation_history: Optional prior messages for feedback continuity.

    Returns:
        Jordan's response with 3 hooks + certainty maps.
    """
    skill_context = load_skill_files()
    system_prompt = build_system_prompt(skill_context)

    # Build the user message
    user_content = f"Topic: {topic}"
    if raw_facts:
        user_content += f"\n\nRaw facts/research:\n{raw_facts}"

    # Build messages list
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
    """
    Process user feedback on hooks and return improved version.

    Args:
        feedback: The user's feedback text.
        conversation_history: Full conversation history including prior hooks.

    Returns:
        Jordan's response with improved hook + mutation log entry.
    """
    skill_context = load_skill_files()
    system_prompt = build_system_prompt(skill_context)

    messages = list(conversation_history)
    messages.append({
        "role": "user",
        "content": f"""FEEDBACK: {feedback}

Instructions:
1. Identify which hook and which line the feedback targets.
2. Extract the specific rule implied by this feedback.
3. Apply it immediately — rewrite the hook.
4. Present the mutation log entry in this format:

MUTATION LOG
Original line: [what was written]
Feedback: [user's exact words]
Rule extracted: [the new guideline]
Status: TESTING (becomes CONFIRMED after 3 approvals across different topics)

5. Present the improved hook with updated certainty map."""
    })

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text


# --- CLI interface for local testing ---

def main():
    """Run Jordan interactively in the terminal."""
    print("=" * 60)
    print("JORDAN — GeniusGTX Hook Writer")
    print("=" * 60)
    print("Commands:")
    print("  Type a topic to generate hooks")
    print("  Type 'feedback: ...' to give feedback on the last hooks")
    print("  Type 'quit' to exit")
    print("=" * 60)

    conversation_history = []

    while True:
        user_input = input("\nYou: ").strip()

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Jordan signing off.")
            break

        if user_input.lower().startswith("feedback:"):
            feedback_text = user_input[len("feedback:"):].strip()
            print("\nJordan is processing your feedback...\n")
            response = process_feedback(feedback_text, conversation_history)
            # Add to conversation history
            conversation_history.append({"role": "user", "content": f"FEEDBACK: {feedback_text}"})
            conversation_history.append({"role": "assistant", "content": response})
        else:
            # Treat as a new topic
            print("\nJordan is writing hooks...\n")
            response = generate_hooks(user_input, conversation_history=conversation_history if conversation_history else None)
            # Reset conversation for new topic, keep the exchange
            conversation_history = [
                {"role": "user", "content": f"Topic: {user_input}"},
                {"role": "assistant", "content": response},
            ]

        print(response)


if __name__ == "__main__":
    main()
