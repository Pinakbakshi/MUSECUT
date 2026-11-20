# MUSECUT

Your music. Your moments. Automatically.

MUSECUT is a mobile-first music-video repurposing studio. Upload a music video and provide the lyrics; the processing worker creates vertical short-form MP4 clips with lyric captions.

## MVP scope
- Local MP4/MOV/WebM upload.
- User-provided lyrics and timed SRT/LRC lyric files.
- FFmpeg rendering to 1080x1920 H.264/AAC.
- Multiple candidate clips and downloadable ZIP.
- Responsive creator workspace and FastAPI worker.

Current limitation: this first renderer requires timestamped SRT or LRC lyrics. Plain-text forced alignment, multilingual ASR/alignment, beat/chorus analysis, scene-semantic matching, face-aware reframing and trend integrations are not implemented yet. Candidate selection currently uses timed lyric cue density and non-overlap heuristics; it does not predict virality.

## Run locally
Requirements: Node 20+, Python 3.11+, FFmpeg and FFprobe.

Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (from repository root):
```bash
npm install
cp .env.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_MUSECUT_API_URL=http://localhost:8000`. Open http://localhost:3000.

## Docker worker
```bash
cd backend
docker build -t musecut-worker .
docker run --rm -p 8000:8000 -e CORS_ORIGINS=http://localhost:3000 musecut-worker
```

## API
`POST /api/generate` multipart fields: `video`, `lyrics`, `timed_lyrics` (.srt or .lrc), `clip_count` (3-10), `caption_style`. Returns `musecut-reels.zip`.

## GitHub Pages deployment
The static frontend is deployed from `main` by GitHub Actions using `.github/workflows/pages.yml`.

Website: https://pinakbakshi.github.io/MUSECUT/

GitHub Pages hosts only the static frontend. It cannot execute the FastAPI/FFmpeg rendering worker. To enable the Generate button on the hosted site, deploy the worker to a separate service and add a repository Actions variable named `MUSECUT_API_URL` containing its HTTPS base URL (no trailing slash). The workflow injects this value as `NEXT_PUBLIC_MUSECUT_API_URL`. The worker must allow the Pages origin in `CORS_ORIGINS`.

For local rendering, set `NEXT_PUBLIC_MUSECUT_API_URL=http://localhost:8000` for a local development build. No paid AI API is required by this MVP.

## Privacy
Uploads are written to per-job temporary directories. Configure `MAX_UPLOAD_MB` and `CORS_ORIGINS`. Add authentication, rate limiting, durable job storage and scheduled temporary-file cleanup before multi-user public launch. Only process media you own or are licensed to use.

## Next milestones
1. Plain-text lyric forced alignment with WhisperX and language-aware aligners.
2. Beat, downbeat, chorus and vocal-activity analysis.
3. Scene understanding and face/subject-aware reframing.
4. Lyric-to-visual semantic matching and editable clip review.
5. Lawful public trend signals with explainable recommendations.
6. Persistent projects, authentication, quotas and secure cloud worker.
