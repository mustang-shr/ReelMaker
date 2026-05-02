"""
STEP 4 — Assemble the Final Reel Video
Updated for moviepy 2.x
"""

import os
import json

# moviepy 2.x imports
from moviepy import (
    AudioFileClip,
    ColorClip,
    TextClip,
    CompositeVideoClip,
)

# ─────────────────────────────────────────────
# DESIGN CONFIG
# ─────────────────────────────────────────────

W, H = 1080, 1920  # 9:16 vertical reel

COLORS = {
    "bg":      (8, 8, 18),
    "alex":    "#00d4ff",
    "maya":    "#ff6eb4",
    "caption": "white",
    "nvidia":  "#76b900",
}


def make_text(text, fontsize, color, font="Arial", max_width=None):
    """Safe TextClip creator for moviepy 2.x."""
    try:
        kwargs = dict(font_size=fontsize, color=color, font=font)
        if max_width:
            kwargs["size"] = (max_width, None)
            kwargs["method"] = "caption"
        return TextClip(text, **kwargs)
    except Exception:
        try:
            kwargs2 = dict(font_size=fontsize, color=color)
            if max_width:
                kwargs2["size"] = (max_width, None)
                kwargs2["method"] = "caption"
            return TextClip(text, **kwargs2)
        except Exception as e:
            print(f"  ⚠️  TextClip failed for '{text[:30]}': {e}")
            return None


def build_caption_clips_evenly(parsed_script, total_duration):
    """Distribute captions evenly across video duration."""
    clips = []
    dialogue_lines = [
        (spk, txt) for spk, txt in parsed_script
        if spk not in ("PAUSE", "MUSIC_UP") and txt
    ]
    if not dialogue_lines:
        return []

    time_per_line = total_duration / len(dialogue_lines)
    current_time = 0.0

    for speaker, text in dialogue_lines:
        color = COLORS["alex"] if speaker == "ALEX" else COLORS["maya"]
        duration = time_per_line

        # Speaker label
        label = make_text(speaker, 46, color, "Arial")
        if label:
            clips.append(
                label.with_position(("center", H - 480))
                     .with_start(current_time)
                     .with_duration(duration)
            )

        # Caption text
        caption = make_text(text, 54, COLORS["caption"], "Arial", max_width=W - 100)
        if caption:
            clips.append(
                caption.with_position(("center", H - 400))
                       .with_start(current_time)
                       .with_duration(duration)
            )

        current_time += time_per_line

    return clips


def build_caption_clips_from_timing(timing_map, total_duration):
    """Build captions using precise timing map from TTS."""
    clips = []
    for entry in timing_map:
        speaker = entry.get("speaker", "")
        text = entry.get("text", "")
        start_s = entry.get("start_ms", 0) / 1000.0
        end_s = entry.get("end_ms", 0) / 1000.0
        duration = max(end_s - start_s, 0.5)

        if speaker in ("PAUSE", "MUSIC_UP") or not text:
            continue

        color = COLORS["alex"] if speaker == "ALEX" else COLORS["maya"]

        label = make_text(speaker, 46, color, "Arial")
        if label:
            clips.append(
                label.with_position(("center", H - 480))
                     .with_start(start_s)
                     .with_duration(duration)
            )

        caption = make_text(text, 54, COLORS["caption"], "Arial", max_width=W - 100)
        if caption:
            clips.append(
                caption.with_position(("center", H - 400))
                       .with_start(start_s)
                       .with_duration(duration)
            )

    return clips


def create_reel_video(audio_path, parsed_script, timing_map=None,
                      metadata=None, output_path="output/reel.mp4"):
    """
    Assemble the final vertical reel video.
    """
    print("\n🎬 Assembling reel video...")

    if not os.path.exists(audio_path):
        print(f"❌ Audio not found: {audio_path}")
        return None

    os.makedirs(os.path.dirname(output_path) or "output", exist_ok=True)

    # Load audio
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    print(f"   Audio duration: {total_duration:.1f}s")

    # Background
    bg = ColorClip(size=(W, H), color=COLORS["bg"], duration=total_duration)

    # Top accent bar
    accent = ColorClip(size=(W, 8), color=(0, 180, 255), duration=total_duration)\
             .with_position((0, 0))

    # Caption background bar at bottom
    cap_bg = ColorClip(size=(W, 580), color=(0, 0, 0), duration=total_duration)\
             .with_opacity(0.55)\
             .with_position((0, H - 560))

    # Title
    title_text = (metadata or {}).get("title", "AI Explains")
    title_clip = make_text(f"🎙 {title_text}", 72, "white", "Arial", max_width=W - 80)

    # Credit line
    credit_clip = make_text(
        "Powered by NVIDIA NIM  ·  build.nvidia.com",
        30, COLORS["nvidia"], "Arial"
    )

    # Speaker legend
    alex_leg = make_text("● ALEX", 28, COLORS["alex"], "Arial")
    maya_leg = make_text("● MAYA", 28, COLORS["maya"], "Arial")

    # Caption clips
    if timing_map and len(timing_map) > 0:
        print("   Using timing-synced captions")
        caption_clips = build_caption_clips_from_timing(timing_map, total_duration)
    else:
        print("   Using evenly-distributed captions")
        caption_clips = build_caption_clips_evenly(parsed_script, total_duration)

    print(f"   {len(caption_clips)} caption clips generated")

    # Assemble layers
    all_clips = [bg, accent, cap_bg]

    if title_clip:
        all_clips.append(
            title_clip.with_position(("center", 90)).with_duration(total_duration)
        )
    if credit_clip:
        all_clips.append(
            credit_clip.with_position(("center", 200)).with_duration(total_duration)
        )
    if alex_leg:
        all_clips.append(
            alex_leg.with_position((W - 200, 90)).with_duration(total_duration)
        )
    if maya_leg:
        all_clips.append(
            maya_leg.with_position((W - 200, 125)).with_duration(total_duration)
        )

    all_clips.extend(caption_clips)

    # Compose
    print("   Compositing...")
    video = CompositeVideoClip(all_clips, size=(W, H))
    video = video.with_audio(audio)

    # Render
    print(f"   Rendering → {output_path}")
    print("   ⏳ This takes 2-4 minutes on CPU, please wait...")

    video.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="medium",
        threads=4,
        logger="bar",   # shows progress bar
    )

    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n✅ Video saved: {output_path} ({size_mb:.1f} MB)")
        return output_path
    else:
        print("❌ Video file not found after rendering")
        return None


if __name__ == "__main__":
    print("Run main.py to test the full pipeline.")