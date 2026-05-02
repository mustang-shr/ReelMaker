"""
STEP 1 — Extract text from PDF or YouTube
Models: parakeet-ctc-1.1b-asr, parakeet-tdt-0.6b-v2
         meta/llama-3.2-90b-vision-instruct (vision OCR for image-based PDFs)
"""

import fitz  # PyMuPDF
import yt_dlp
import requests
import os
import re
import base64
import json
from dotenv import load_dotenv

load_dotenv()
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")


# ─────────────────────────────────────────────
# PDF EXTRACTION
# ─────────────────────────────────────────────

def extract_from_pdf(pdf_path):
    """
    Extract all text from a PDF file.

    Strategy (no poppler/tesseract needed):
      1. PyMuPDF text layer extraction — instant, works for text-based PDFs.
      2. If avg < 100 chars/page (image/slide deck PDF), render each page
         to PNG via PyMuPDF and OCR with NVIDIA vision LLM — zero extra installs.
    """
    doc = fitz.open(pdf_path)
    num_pages = doc.page_count
    full_text = ""

    for page_num in range(num_pages):
        page = doc[page_num]
        full_text += f"\n[Page {page_num+1}]\n"
        full_text += page.get_text()

    chars_per_page = len(full_text.strip()) / max(num_pages, 1)
    print(f"   PyMuPDF extracted {len(full_text):,} chars ({chars_per_page:.0f}/page)")

    if chars_per_page < 100:
        print("⚠️  Image-based PDF detected — switching to Vision LLM OCR (no poppler needed)...")
        vision_text = _ocr_pdf_with_vision(doc, num_pages)
        doc.close()
        if vision_text and len(vision_text.strip()) > len(full_text.strip()):
            full_text = vision_text
    else:
        doc.close()

    if len(full_text.strip()) < 50:
        raise ValueError(
            f"Could not extract readable text from '{pdf_path}'.\n"
            "  • Check that NVIDIA_API_KEY is valid.\n"
            "  • Make sure the PDF is not password-protected."
        )

    print(f"✅ Extracted {len(full_text):,} characters from PDF ({num_pages} pages)")
    return full_text


def _ocr_pdf_with_vision(doc, num_pages):
    """
    Render each PDF page to PNG using PyMuPDF (built-in, zero extra deps),
    then send to NVIDIA Llama 3.2 Vision for text extraction.
    Works for: slide decks, scanned docs, image-only PDFs, NotebookLM exports.
    """
    VISION_MODEL = "meta/llama-3.2-90b-vision-instruct"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    full_text = ""
    print(f"   Vision model: {VISION_MODEL} | Pages: {num_pages}")

    for page_num in range(num_pages):
        page = doc[page_num]

        # Render at 2x scale for better OCR accuracy
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")

        payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract ALL text visible in this image exactly as it appears. "
                                "Include titles, headings, bullet points, labels, captions, "
                                "table content, and diagram annotations. "
                                "Preserve reading order top-to-bottom, left-to-right. "
                                "Output ONLY the extracted text — no explanations, no commentary."
                            )
                        }
                    ]
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.1,
        }

        try:
            resp = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                page_text = resp.json()["choices"][0]["message"]["content"].strip()
                full_text += f"\n[Page {page_num+1}]\n{page_text}\n"
                print(f"   ✅ Page {page_num+1}/{num_pages}: {len(page_text)} chars")
            else:
                print(f"   ⚠️  Page {page_num+1} — vision API {resp.status_code}: {resp.text[:120]}")
                full_text += f"\n[Page {page_num+1}]\n[vision extraction failed]\n"
        except Exception as e:
            print(f"   ⚠️  Page {page_num+1} exception: {e}")
            full_text += f"\n[Page {page_num+1}]\n[vision extraction failed]\n"

    return full_text


# ─────────────────────────────────────────────
# YOUTUBE: Try subtitles first
# ─────────────────────────────────────────────

def get_youtube_subtitles(url, output_dir="output"):
    """Try to get existing YouTube auto-subtitles (fast, no ASR needed)."""
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'skip_download': True,
        'outtmpl': f'{output_dir}/yt_%(id)s',
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info['id']
        title = info.get('title', 'YouTube Video')

    sub_file = f"{output_dir}/yt_{video_id}.en.vtt"
    if os.path.exists(sub_file):
        with open(sub_file, 'r', encoding='utf-8') as f:
            raw = f.read()
        text = re.sub(r'WEBVTT.*?\n\n', '', raw, flags=re.DOTALL)
        text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}.*\n', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{2,}', ' ', text)
        text = ' '.join(text.split())
        print(f"✅ Got YouTube subtitles: {title}")
        return text, title, video_id

    return None, title, None


# ─────────────────────────────────────────────
# YOUTUBE: Download Audio for ASR
# ─────────────────────────────────────────────

def download_youtube_audio(url, output_dir="output"):
    """Download YouTube audio as mp3."""
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/yt_%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info['id']
        title = info.get('title', 'YouTube Video')

    audio_path = f"{output_dir}/yt_{video_id}.mp3"
    if os.path.exists(audio_path):
        print(f"✅ Audio downloaded: {audio_path}")
        return audio_path, title, video_id
    raise FileNotFoundError(f"Audio file not found: {audio_path}")


# ─────────────────────────────────────────────
# PARAKEET ASR
# ─────────────────────────────────────────────

def transcribe_with_parakeet(audio_path, model="nvidia/parakeet-ctc-1.1b-asr"):
    """Transcribe audio using NVIDIA Parakeet ASR."""
    print(f"\n🎤 Transcribing with {model}...")

    with open(audio_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": audio_b64,
        "encoding": "mp3",
        "sample_rate_hertz": 16000,
        "language_code": "en-US",
    }

    try:
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/audio/transcriptions",
            headers=headers, json=payload, timeout=120
        )
        if response.status_code == 200:
            result = response.json()
            transcript = result.get('text', '') or result.get('transcript', '')
            print(f"✅ Transcript: {len(transcript):,} characters")
            return transcript
        else:
            print(f"⚠️  Parakeet error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"⚠️  Parakeet request failed: {e}")
        return None


def transcribe_with_timestamps(audio_path):
    """Get word-level timestamps using parakeet-tdt-0.6b-v2."""
    print(f"\n🕐 Getting word timestamps...")

    with open(audio_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "nvidia/parakeet-tdt-0.6b-v2",
        "input": audio_b64,
        "encoding": "mp3",
        "sample_rate_hertz": 16000,
        "language_code": "en-US",
        "timestamps": "word",
    }

    try:
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/audio/transcriptions",
            headers=headers, json=payload, timeout=120
        )
        if response.status_code == 200:
            words = response.json().get('words', [])
            print(f"✅ Got {len(words)} word timestamps")
            return words
        else:
            print(f"⚠️  Timestamp error {response.status_code}")
            return []
    except Exception as e:
        print(f"⚠️  Timestamp request failed: {e}")
        return []


# ─────────────────────────────────────────────
# SMART YOUTUBE EXTRACTOR
# ─────────────────────────────────────────────

def extract_from_youtube(url, output_dir="output", use_asr=True):
    """
    Try subtitles first → fallback to Parakeet ASR.
    Returns: (transcript_text, title, word_timestamps)
    """
    print(f"\n📺 Processing: {url}")

    # Try subtitles first (fast)
    text, title, vid_id = get_youtube_subtitles(url, output_dir)
    if text and len(text) > 200:
        return text, title, []

    # Fallback: download audio + ASR
    print("⚠️  No subtitles → using Parakeet ASR...")
    audio_path, title, vid_id = download_youtube_audio(url, output_dir)

    if not use_asr:
        return "", title, []

    transcript = transcribe_with_parakeet(audio_path)
    word_timestamps = transcribe_with_timestamps(audio_path)

    if transcript:
        with open(f"{output_dir}/transcript_{vid_id}.txt", 'w', encoding='utf-8') as f:
            f.write(transcript)
    if word_timestamps:
        with open(f"{output_dir}/timestamps_{vid_id}.json", 'w') as f:
            json.dump(word_timestamps, f, indent=2)

    return transcript or "", title, word_timestamps


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        src = sys.argv[1]
        if src.endswith('.pdf'):
            print(extract_from_pdf(src)[:500])
        else:
            text, title, ts = extract_from_youtube(src)
            print(f"Title: {title}\nText: {text[:300]}")
    else:
        print("Usage: python step1_extract.py <file.pdf or youtube_url>")