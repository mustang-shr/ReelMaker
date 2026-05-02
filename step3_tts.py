"""
STEP 3 — Text to Speech using NVIDIA Magpie TTS Multilingual
Model used:
  - nvidia/magpie-tts-multilingual  → Natural dual-host voices (Aria + Jason)
  - gTTS fallback if API unavailable
"""

import requests
import os
import time
import json
from pydub import AudioSegment
from pydub.effects import normalize
from dotenv import load_dotenv

load_dotenv()
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# ─────────────────────────────────────────────
# VOICE CONFIGURATION
# ─────────────────────────────────────────────

# Magpie TTS voices (from NVIDIA NIM Speech catalog)
MAGPIE_VOICES = {
    "ALEX": "Magpie-Multilingual.EN-US.Jason",   # male, energetic
    "MAYA": "Magpie-Multilingual.EN-US.Aria",    # female, warm
}

# Fallback gTTS config
GTTS_CONFIG = {
    "ALEX": {"lang": "en", "tld": "com.au"},     # Australian male-ish
    "MAYA": {"lang": "en", "tld": "co.uk"},      # British female-ish
}

# SSML emphasis for more dramatic delivery
SSML_TEMPLATES = {
    "ALEX": '<speak><prosody rate="105%" pitch="+2st">{text}</prosody></speak>',
    "MAYA": '<speak><prosody rate="95%" pitch="-1st">{text}</prosody></speak>',
}


# ─────────────────────────────────────────────
# NVIDIA MAGPIE TTS
# ─────────────────────────────────────────────

def tts_magpie(text, voice_name, output_path):
    """
    Call NVIDIA Magpie TTS Multilingual API.
    Endpoint: https://integrate.api.nvidia.com/v1/audio/speech
    """
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "magpie-tts-multilingual",
        "input": text,
        "voice": voice_name,
        "response_format": "wav",
        "sample_rate": 22050,
    }

    url = "https://integrate.api.nvidia.com/v1/audio/speech"

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return output_path

        # Try alternate payload format
        payload2 = {
            "text": text,
            "voice": voice_name,
            "encoding": "LINEAR_PCM",
            "sample_rate_hz": 22050,
            "language_code": "en-US",
        }
        response2 = requests.post(url, headers=headers, json=payload2, timeout=60)
        if response2.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response2.content)
            return output_path

        print(f"  ⚠️  Magpie TTS error {response.status_code}: {response.text[:200]}")
        return None

    except Exception as e:
        print(f"  ⚠️  Magpie TTS exception: {e}")
        return None


# ─────────────────────────────────────────────
# FALLBACK: gTTS (Google TTS — free, no API)
# ─────────────────────────────────────────────

def tts_gtts_fallback(text, speaker, output_path):
    """Use gTTS as fallback when NVIDIA TTS is unavailable."""
    try:
        from gtts import gTTS
        cfg = GTTS_CONFIG.get(speaker, {"lang": "en", "tld": "com"})
        tts = gTTS(text=text, lang=cfg["lang"], tld=cfg["tld"], slow=False)
        tts.save(output_path)
        return output_path
    except ImportError:
        print("  ⚠️  gTTS not installed. Run: pip install gtts")
        return None
    except Exception as e:
        print(f"  ⚠️  gTTS error: {e}")
        return None


# ─────────────────────────────────────────────
# SMART TTS (tries Magpie → falls back to gTTS)
# ─────────────────────────────────────────────

def synthesize_line(text, speaker, output_path, prefer_nvidia=True):
    """
    Synthesize a single line of dialogue.
    Tries NVIDIA Magpie first, falls back to gTTS.
    Returns path to .wav or .mp3 file.
    """
    voice = MAGPIE_VOICES.get(speaker, MAGPIE_VOICES["MAYA"])

    if prefer_nvidia:
        result = tts_magpie(text, voice, output_path)
        if result and os.path.exists(result):
            return result

    # Fallback
    print(f"  ↩️  Using gTTS fallback for {speaker}")
    fallback_path = output_path.replace('.wav', '.mp3')
    return tts_gtts_fallback(text, speaker, fallback_path)


# ─────────────────────────────────────────────
# BUILD FULL AUDIO FROM PARSED SCRIPT
# ─────────────────────────────────────────────

def build_audio_from_script(parsed_script, output_dir="output", bg_music_path=None):
    """
    Convert a parsed script (list of tuples) into a merged audio file.
    
    Args:
        parsed_script: list of (speaker, line) tuples
        output_dir: where to save audio files
        bg_music_path: optional path to background music mp3
    
    Returns: path to final merged mp3
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f"{output_dir}/segments", exist_ok=True)

    audio_segments = []
    timing_map = []   # [{speaker, text, start_ms, end_ms}] for caption sync
    current_ms = 0

    print(f"\n🎙️ Converting {len(parsed_script)} script lines to audio...")

    for i, (speaker, line) in enumerate(parsed_script):

        # ── PAUSE: add silence ──
        if speaker == "PAUSE":
            silence_ms = 700
            audio_segments.append(AudioSegment.silent(duration=silence_ms))
            current_ms += silence_ms
            print(f"  [{i:02d}] [PAUSE] — {silence_ms}ms silence")
            continue

        # ── MUSIC_UP: flag it (handled during video assembly) ──
        if speaker == "MUSIC_UP":
            timing_map.append({
                "speaker": "MUSIC_UP", "text": "",
                "start_ms": current_ms, "end_ms": current_ms
            })
            continue

        if not line:
            continue

        # ── Generate speech ──
        seg_path = f"{output_dir}/segments/seg_{i:03d}_{speaker}.wav"
        print(f"  [{i:02d}] {speaker}: {line[:55]}{'...' if len(line) > 55 else ''}")

        result = synthesize_line(line, speaker, seg_path)

        if result and os.path.exists(result):
            try:
                seg_audio = AudioSegment.from_file(result)
                seg_audio = normalize(seg_audio)  # normalize volume

                # Record timing
                seg_duration = len(seg_audio)
                timing_map.append({
                    "speaker": speaker,
                    "text": line,
                    "start_ms": current_ms,
                    "end_ms": current_ms + seg_duration
                })

                audio_segments.append(seg_audio)
                current_ms += seg_duration

                # Natural inter-speaker gap (250ms)
                gap = AudioSegment.silent(duration=250)
                audio_segments.append(gap)
                current_ms += 250

            except Exception as e:
                print(f"  ⚠️  Could not load audio segment: {e}")
        else:
            print(f"  ❌ No audio generated for line {i}")

        time.sleep(0.3)  # be polite to API rate limits

    if not audio_segments:
        print("❌ No audio segments generated!")
        return None, []

    # ── Merge all segments ──
    print("\n🎵 Merging audio segments...")
    merged = audio_segments[0]
    for seg in audio_segments[1:]:
        merged += seg

    # ── Add background music if provided ──
    if bg_music_path and os.path.exists(bg_music_path):
        print(f"🎶 Mixing background music: {bg_music_path}")
        bg = AudioSegment.from_file(bg_music_path)
        # Loop background music to match podcast length
        while len(bg) < len(merged):
            bg = bg + bg
        bg = bg[:len(merged)]
        # Lower bg music volume by 18dB
        bg = bg - 18
        merged = merged.overlay(bg)

    # ── Export final audio ──
    final_path = f"{output_dir}/podcast_audio.mp3"
    merged.export(final_path, format="mp3", bitrate="192k")

    duration_sec = len(merged) / 1000
    print(f"✅ Final audio: {final_path}")
    print(f"   Duration: {duration_sec:.1f}s ({int(duration_sec//60)}m {int(duration_sec%60)}s)")

    # ── Save timing map ──
    timing_path = f"{output_dir}/timing.json"
    with open(timing_path, 'w') as f:
        json.dump(timing_map, f, indent=2)
    print(f"✅ Caption timing saved: {timing_path}")

    return final_path, timing_map


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    test_script = [
        ("ALEX", "Wait — octopuses actually dream? That is wild."),
        ("MAYA", "Not only that. They change color while dreaming."),
        ("PAUSE", ""),
        ("ALEX", "So they're basically reliving their day?"),
        ("MAYA", "Scientists think so. And here's the craziest part."),
        ("MUSIC_UP", ""),
        ("ALEX", "Tell me everything right now."),
        ("MAYA", "One octopus literally escaped from an aquarium. Crawled across the floor. Down a drainpipe. To the ocean."),
        ("ALEX", "That is the most unhinged thing I have ever heard."),
        ("MAYA", "Nature does not miss. Follow for more facts that break your brain."),
    ]

    audio, timing = build_audio_from_script(test_script)
    if audio:
        print(f"\nAudio: {audio}")
        print(f"Timing entries: {len(timing)}")