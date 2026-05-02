"""
STEP 2 — Generate Storytelling Script from raw text
Models used:
  - meta/llama-3.1-70b-instruct   → Draft the initial storytelling script
  - meta/llama-3.1-70b-instruct   → Polish & punch it up (Nemotron fallback)

NOTE: nvidia/nemotron-super-49b-v1 and nvidia/llama-3.1-nemotron-70b-instruct
require specific NIM account entitlements. This file uses llama-3.1-70b for
both passes with different system prompts, which works on all NIM free tiers.
If you have Nemotron access, set NEMOTRON_MODEL in your .env to override.
"""

from openai import OpenAI
from dotenv import load_dotenv
import os
import re

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

# Use env override if you have Nemotron access, else safe default
POLISH_MODEL = os.getenv("NEMOTRON_MODEL", "meta/llama-3.1-70b-instruct")
DRAFT_MODEL  = "meta/llama-3.1-70b-instruct"


# ─────────────────────────────────────────────
# STAGE 1: Draft Script with Llama 3.1 70B
# ─────────────────────────────────────────────

def generate_draft_script(raw_text, topic_focus="", duration_seconds=90):
    """
    Use Llama 3.1 70B to convert raw text into a 2-host podcast script.
    Duration guide: 90 sec ≈ 200-230 words, 60 sec ≈ 130-150 words
    """
    max_chars = 10000
    if len(raw_text) > max_chars:
        half = max_chars // 2
        trimmed = raw_text[:half] + "\n...[middle trimmed]...\n" + raw_text[-half:]
    else:
        trimmed = raw_text

    word_target = int((duration_seconds / 90) * 220)
    focus_line = f"\nFocus especially on: {topic_focus}" if topic_focus else ""

    prompt = f"""You are a viral short-form content creator specializing in educational storytelling reels.

Transform the content below into a gripping 2-host podcast/reel script.

HOSTS:
- ALEX: The curious one. Energetic, asks punchy questions, reacts with surprise/shock.
- MAYA: The expert. Calm but passionate, drops knowledge bombs, builds suspense.

RULES (follow these EXACTLY):
1. First line MUST be a HOOK — start with something shocking, controversial, or emotional
2. Use SHORT sentences. Max 15 words per line.
3. Write [PAUSE] on its own line for dramatic effect (use 2-3 times)
4. Write [MUSIC_UP] once at the most exciting moment
5. End with either a cliffhanger OR a strong call-to-action
6. Target {word_target} words total (for ~{duration_seconds} sec audio)
7. Make it feel like a STORY — not a lecture or summary
8. Every 3-4 lines, include a "did you know" style fact bomb{focus_line}

OUTPUT FORMAT (exactly this, no preamble):
ALEX: [line]
MAYA: [line]
[PAUSE]
ALEX: [line]
...

CONTENT TO TRANSFORM:
{trimmed}

Begin the script:"""

    print(f"🤖 Stage 1: Drafting with {DRAFT_MODEL}...")

    response = client.chat.completions.create(
        model=DRAFT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
        temperature=0.88,
        top_p=0.95,
    )

    draft = response.choices[0].message.content.strip()
    print(f"✅ Draft script: {len(draft.split())} words")
    return draft


# ─────────────────────────────────────────────
# STAGE 2: Polish (Nemotron if available, else Llama with editor prompt)
# ─────────────────────────────────────────────

def polish_script_with_nemotron(draft_script):
    """
    Polish the script for maximum engagement.
    Uses POLISH_MODEL (env-configurable). Defaults to llama-3.1-70b with
    a dedicated editor persona when Nemotron isn't available on the account.
    """
    prompt = f"""You are an expert viral content editor. Your job is to take a good podcast script 
and make it GREAT — punchy, addictive, and impossible to stop listening to.

EDITING RULES:
1. Keep the ALEX / MAYA / [PAUSE] / [MUSIC_UP] format exactly
2. Make the opening hook MORE shocking or emotional (rewrite if needed)
3. Shorten any line longer than 15 words
4. Replace any boring/academic word with a simple vivid one
5. Add ONE "Wait... what?" moment if it doesn't already have one
6. Make the ending hit harder — cliffhanger or powerful call to action
7. Do NOT add new facts — only improve the language and pacing
8. Keep total word count roughly the same

DRAFT SCRIPT TO POLISH:
{draft_script}

Return ONLY the polished script, no explanations:"""

    print(f"✨ Stage 2: Polishing with {POLISH_MODEL}...")

    try:
        response = client.chat.completions.create(
            model=POLISH_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.7,
            top_p=0.9,
        )
        polished = response.choices[0].message.content.strip()
        print(f"✅ Polished script: {len(polished.split())} words")
        return polished

    except Exception as e:
        # If the configured polish model fails (e.g. account entitlement),
        # fall back to the draft model which is confirmed working.
        print(f"⚠️  Polish model failed ({e}), falling back to {DRAFT_MODEL} for polish pass...")
        response = client.chat.completions.create(
            model=DRAFT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.7,
            top_p=0.9,
        )
        polished = response.choices[0].message.content.strip()
        print(f"✅ Polished script (fallback): {len(polished.split())} words")
        return polished


# ─────────────────────────────────────────────
# GENERATE TITLE & HASHTAGS
# ─────────────────────────────────────────────

def generate_title_and_hashtags(script_text):
    """Generate a viral title + hashtags for the reel."""
    prompt = f"""Based on this podcast script, generate:
1. A viral reel title (max 10 words, use numbers/power words)
2. A one-line hook for the caption (max 20 words)
3. 10 relevant hashtags

Script:
{script_text[:1500]}

Respond in this exact JSON format:
{{
  "title": "...",
  "caption_hook": "...",
  "hashtags": ["#tag1", "#tag2", ...]
}}"""

    response = client.chat.completions.create(
        model=DRAFT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()

    try:
        raw = re.sub(r'```json|```', '', raw).strip()
        import json
        data = json.loads(raw)
        print(f"✅ Title: {data.get('title', '')}")
        return data
    except Exception:
        print("⚠️  Could not parse title JSON, using defaults")
        return {
            "title": "You Won't Believe This",
            "caption_hook": "The facts they never taught you in school...",
            "hashtags": ["#AI", "#podcast", "#education", "#facts", "#viral"]
        }


# ─────────────────────────────────────────────
# PARSE SCRIPT
# ─────────────────────────────────────────────

def parse_script(script_text):
    """
    Parse the raw script string into a structured list.
    Returns: list of tuples like:
      ("ALEX", "Did you know AI can read your emotions?")
      ("MAYA", "Not only that — it can predict your next move.")
      ("PAUSE", "")
      ("MUSIC_UP", "")
    """
    lines = []
    for raw_line in script_text.strip().split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("ALEX:"):
            content = line[5:].strip()
            if content:
                lines.append(("ALEX", content))

        elif line.startswith("MAYA:"):
            content = line[5:].strip()
            if content:
                lines.append(("MAYA", content))

        elif '[PAUSE]' in line:
            lines.append(("PAUSE", ""))

        elif '[MUSIC_UP]' in line:
            lines.append(("MUSIC_UP", ""))

    return lines


def script_to_plain_text(parsed_lines):
    """Convert parsed script back to plain readable text (for logging/saving)."""
    output = []
    for speaker, line in parsed_lines:
        if speaker in ("PAUSE", "MUSIC_UP"):
            output.append(f"\n[{speaker}]\n")
        else:
            output.append(f"{speaker}: {line}")
    return '\n'.join(output)


# ─────────────────────────────────────────────
# FULL PIPELINE
# ─────────────────────────────────────────────

def generate_full_script(raw_text, topic_focus="", duration_seconds=90, output_dir="output"):
    """
    Full 2-stage script generation pipeline.
    Returns: (parsed_script_list, metadata_dict)
    """
    os.makedirs(output_dir, exist_ok=True)

    draft = generate_draft_script(raw_text, topic_focus, duration_seconds)
    polished = polish_script_with_nemotron(draft)
    metadata = generate_title_and_hashtags(polished)
    parsed = parse_script(polished)

    if not parsed:
        print("⚠️  Parsing failed, falling back to draft...")
        parsed = parse_script(draft)

    with open(f"{output_dir}/script_draft.txt", 'w', encoding='utf-8') as f:
        f.write(draft)
    with open(f"{output_dir}/script_final.txt", 'w', encoding='utf-8') as f:
        f.write(polished)

    import json
    with open(f"{output_dir}/metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n📝 Script saved ({len(parsed)} lines parsed)")
    return parsed, metadata


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    sample_text = """
    In 2024, researchers at MIT discovered that octopuses dream — 
    and they actually change color while dreaming, suggesting they may be 
    replaying experiences from their day. Octopuses have three hearts and 
    blue blood. Their intelligence rivals that of a 5-year-old child. 
    They can unscrew jars, use tools, and even recognize individual human faces.
    One octopus named Inky escaped from the National Aquarium of New Zealand 
    by squeezing through a gap, sliding 8 feet across the floor, 
    and escaping down a drainpipe to the ocean.
    """

    parsed, meta = generate_full_script(
        sample_text,
        topic_focus="how intelligent octopuses really are",
        duration_seconds=75
    )

    print("\n📋 PARSED SCRIPT:")
    print("─" * 50)
    for speaker, line in parsed:
        if speaker in ("PAUSE", "MUSIC_UP"):
            print(f"  [{speaker}]")
        else:
            print(f"  {speaker}: {line}")

    print("\n📊 METADATA:")
    import json
    print(json.dumps(meta, indent=2))