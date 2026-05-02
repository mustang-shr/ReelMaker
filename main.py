"""
main.py — NVIDIA NIM Storytelling Reel Generator (Fixed for Windows)
"""

import argparse
import os
import sys
import traceback
from datetime import datetime


def check_environment():
    print("\n🔍 Checking environment...")
    ok = True

    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("NVIDIA_API_KEY")
    if not key or "YOUR_KEY" in key:
        print("  ❌ NVIDIA_API_KEY missing in .env")
        ok = False
    else:
        print(f"  ✅ API Key: {key[:15]}...")

    packages = {'fitz':'PyMuPDF','openai':'openai','pydub':'pydub',
                'moviepy':'moviepy','requests':'requests','yt_dlp':'yt-dlp','gtts':'gtts'}
    for mod, pip_name in packages.items():
        try:
            __import__(mod)
            print(f"  ✅ {pip_name}")
        except ImportError:
            print(f"  ❌ {pip_name} — run: pip install {pip_name}")
            ok = False

    import shutil
    if shutil.which("ffmpeg"):
        print("  ✅ ffmpeg found")
    else:
        print("  ❌ ffmpeg NOT in PATH — close terminal, reopen, try again")
        ok = False

    return ok


BANNER = """
╔══════════════════════════════════════════════════════╗
║      🎬  NVIDIA NIM — Storytelling Reel Generator    ║
║  Llama 3.1 70B + Nemotron 70B + Magpie TTS + Parakeet ║
╚══════════════════════════════════════════════════════╝
"""


def run_pipeline(source_type, source_value, topic_focus="", duration_seconds=90):
    print(BANNER)

    if not check_environment():
        print("\n❌ Fix issues above then CLOSE this terminal, open a NEW one, and re-run.")
        sys.exit(1)

    print("\n✅ All checks passed — starting!\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"output/reel_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 Output: {os.path.abspath(output_dir)}\n")

    try:
        print("📦 Loading pipeline modules...")
        from step1_extract import extract_from_pdf, extract_from_youtube
        from step2_script import generate_full_script
        from step3_tts import build_audio_from_script
        from step4_assemble import create_reel_video
        print("  ✅ All modules loaded\n")
    except Exception as e:
        print(f"\n❌ Import error: {e}")
        traceback.print_exc()
        sys.exit(1)

    # STEP 1
    print("=" * 55)
    print("STEP 1 ▶  Extracting content...")
    print("=" * 55)
    try:
        word_timestamps = []
        if source_type == "pdf":
            if not os.path.exists(source_value):
                print(f"❌ PDF not found: {os.path.abspath(source_value)}")
                sys.exit(1)
            raw_text = extract_from_pdf(source_value)
            title = os.path.splitext(os.path.basename(source_value))[0]
        else:
            raw_text, title, word_timestamps = extract_from_youtube(source_value, output_dir=output_dir)
    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    if not raw_text or len(raw_text) < 50:
        print("❌ Not enough text extracted.")
        sys.exit(1)

    print(f"\n✅ Extracted {len(raw_text):,} characters")
    with open(f"{output_dir}/raw_content.txt", 'w', encoding='utf-8') as f:
        f.write(raw_text)

    # STEP 2
    print("\n" + "=" * 55)
    print("STEP 2 ▶  Generating script (Llama 70B + Nemotron 49B)...")
    print("=" * 55)
    try:
        parsed_script, metadata = generate_full_script(
            raw_text, topic_focus=topic_focus or title,
            duration_seconds=duration_seconds, output_dir=output_dir)
    except Exception as e:
        print(f"\n❌ Script generation failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    if not parsed_script:
        print("❌ Script empty.")
        sys.exit(1)

    print(f"\n✅ Script: {sum(1 for s,_ in parsed_script if s not in ('PAUSE','MUSIC_UP'))} lines")
    print(f"   Title: {metadata.get('title','N/A')}")

    # STEP 3
    print("\n" + "=" * 55)
    print("STEP 3 ▶  Generating audio (Magpie TTS)...")
    print("=" * 55)
    try:
        audio_path, timing_map = build_audio_from_script(parsed_script, output_dir=output_dir)
    except Exception as e:
        print(f"\n❌ Audio failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    if not audio_path or not os.path.exists(audio_path):
        print("❌ Audio not created.")
        sys.exit(1)
    print(f"\n✅ Audio: {audio_path}")

    # STEP 4
    print("\n" + "=" * 55)
    print("STEP 4 ▶  Assembling video...")
    print("=" * 55)
    try:
        video_path = f"{output_dir}/reel_{timestamp}.mp4"
        result = create_reel_video(
            audio_path=audio_path, parsed_script=parsed_script,
            timing_map=timing_map or [], metadata=metadata, output_path=video_path)
    except Exception as e:
        print(f"\n❌ Video assembly failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "═" * 55)
    print("🎉  DONE!")
    print("═" * 55)
    if result and os.path.exists(result):
        print(f"\n  📹  {os.path.abspath(result)}")
        tags = metadata.get("hashtags", [])
        print(f"  🏷️   {' '.join(tags[:5])}")
        print(f"  💬  {metadata.get('caption_hook','')}")
    print("═" * 55)


def main():
    parser = argparse.ArgumentParser(description="NVIDIA NIM Reel Generator")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", metavar="PATH")
    src.add_argument("--youtube", metavar="URL")
    parser.add_argument("--focus", default="")
    parser.add_argument("--duration", type=int, default=90)
    args = parser.parse_args()

    try:
        if args.pdf:
            run_pipeline("pdf", args.pdf, args.focus, args.duration)
        else:
            run_pipeline("youtube", args.youtube, args.focus, args.duration)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n💥 Unexpected crash: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()