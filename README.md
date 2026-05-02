NVIDIA NIM · build.nvidia.com
Storytelling
Reel Generator
Transform any PDF or YouTube video into a viral podcast-style short-form reel — powered entirely by NVIDIA NIM AI models.

(venv) $ python main.py --pdf input/report.pdf --focus "shocking facts" --duration 90
Pipeline
01
Extract Content
PDF text extraction via PyMuPDF. YouTube: auto-subtitles first, falls back to Parakeet ASR transcription with word-level timestamps.
parakeet-ctc-1.1b-asr parakeet-tdt-0.6b-v2
02
Generate Script
Two-stage pipeline: Llama 3.1 70B drafts a 2-host storytelling dialogue. Nemotron Super 49B polishes hooks, punchlines, and pacing for virality.
llama-3.1-70b-instruct nemotron-super-49b-v1
03
Synthesize Audio
Dual-voice generation: ALEX (Jason voice) and MAYA (Aria voice) using Magpie TTS Multilingual. Falls back to gTTS if API unavailable. Timing map saved for caption sync.
magpie-tts-multilingual
04
Assemble Video
MoviePy composites a 1080×1920 (9:16) vertical reel with color-coded speaker captions, animated title, NVIDIA branding, and optional background music.
moviepy 2.x ffmpeg
Models Used
All models accessed via one nvapi- key from build.nvidia.com/settings/api-keys

meta/llama-3.1-70b-instruct
Script Drafter
Converts raw text into a 2-host storytelling dialogue with hooks, pauses, and fact bombs.
nvidia/nemotron-super-49b-v1
Script Polisher
Punches up the draft — sharpens hooks, cuts bloat, maximises virality.
nvidia/magpie-tts-multilingual
Dual Voice TTS
Aria (MAYA) + Jason (ALEX) voices. Natural, expressive, multilingual synthesis.
nvidia/parakeet-ctc-1.1b-asr
YouTube Transcription
Record-setting English ASR accuracy. Transcribes YouTube audio when no subtitles exist.
nvidia/parakeet-tdt-0.6b-v2
Word Timestamps
Provides word-level timestamps used to sync captions frame-accurately to audio.
gTTS (fallback)
TTS Fallback
Free Google TTS fallback — activates automatically if Magpie API is unavailable.
Setup
1
Install ffmpeg
Required for all audio/video processing
# Windows (run in PowerShell)
winget install ffmpeg
# Then CLOSE terminal and open a NEW one

# Mac
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg
2
Create Virtual Environment & Install Packages
Python 3.10+ recommended
python -m venv venv

# Windows
venv\Scripts\Activate.ps1

# Mac / Linux
source venv/bin/activate

pip install -r requirements.txt
3
Add Your API Key
Get free key at build.nvidia.com/settings/api-keys
# Create .env file in project root
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx

# Verify it loads correctly
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('NVIDIA_API_KEY')[:15])"
Usage Examples
From PDF
python main.py --pdf input/report.pdf --focus "most shocking facts"
From PDF · Custom Duration
python main.py --pdf input/book.pdf --focus "key takeaways" --duration 60
From YouTube
python main.py --youtube "https://youtube.com/watch?v=VIDEO_ID"
From YouTube · With Focus
python main.py --youtube "https://youtu.be/VIDEO_ID" --focus "AI breakthroughs" --duration 90

Available flags: --pdf or --youtube (required) · --focus topic hint · --duration seconds (default 90)

Output Structure
Each run creates a timestamped folder inside output/

output/
  reel_20260429_160102/
    ★ reel_20260429_160102.mp4  ← your final video
    podcast_audio.mp3  ← audio only
    script_draft.txt  ← Llama 70B output
    script_final.txt  ← Nemotron polished
    metadata.json  ← title + hashtags + caption
    timing.json  ← caption timestamps
    raw_content.txt  ← extracted source text
    segments/  ← individual audio clips

Output format: 1080×1920 vertical (9:16) · 30fps · H.264 + AAC · Ready for Instagram Reels, TikTok, YouTube Shorts

Troubleshooting
ModuleNotFoundError: No module named 'pkg_resources'
moviepy version conflict. Fix: pip uninstall moviepy imageio imageio-ffmpeg -y then pip install moviepy==2.1.1
ValueError: document closed
PyMuPDF bug — fixed in latest step1_extract.py. Make sure you have the latest version of the file.
Couldn't find ffmpeg or avconv
After installing ffmpeg with winget, you must close the terminal and open a new one. Then verify with ffmpeg -version
API Key found: NO — CHECK YOUR .env FILE
The .env file is empty or unsaved. In PowerShell run: Set-Content -Path ".env" -Value "NVIDIA_API_KEY=nvapi-YOUR_KEY" -NoNewline
Magpie TTS error 404 / 422
Normal — script automatically falls back to gTTS (Google TTS). Audio will still be generated. Magpie may require self-hosted NIM containers for some endpoints.
NVIDIA NIM · build.nvidia.com
One API key · Five models · Infinite reels
