import os
import sys
from dotenv import load_dotenv
load_dotenv()

print("=== NVIDIA NIM Reel Generator ===")

# STEP 1
print("\nStep 1: Extracting PDF...")
from step1_extract import extract_from_pdf
text = extract_from_pdf("input/The_Auth_Blueprint.pdf")
print(f"Got {len(text)} characters")

# STEP 2
print("\nStep 2: Generating script...")
from step2_script import generate_full_script
parsed, meta = generate_full_script(
    text,
    topic_focus="key insights",
    duration_seconds=90,
    output_dir="output"
)
print(f"Script: {len(parsed)} lines")
print(f"Title: {meta.get('title')}")

# STEP 3
print("\nStep 3: Generating audio...")
from step3_tts import build_audio_from_script
audio, timing = build_audio_from_script(parsed, output_dir="output")
print(f"Audio: {audio}")

# STEP 4
print("\nStep 4: Assembling video...")
from step4_assemble import create_reel_video
video = create_reel_video(
    audio, parsed, timing, meta,
    output_path="output/final_reel.mp4"
)
print(f"DONE! Video: {video}")