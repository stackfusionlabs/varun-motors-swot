# Varun Motors SWOT — Blindspot Dashboard

Single-page review intelligence + Vahan registration dashboard for Varun Motors
(Maruti Suzuki dealer group, AP & TG), with **Drishti** — a conversational AI bot
that runs 100% offline in the browser.

## Live

Deployed on Vercel — root URL serves `index.html`. Public browsers fall back to
CDN model URLs; the pitch laptop serves everything locally.

## Files

- `index.html` — the SPA (HTML + inline CSS + Leaflet + Chart.js via CDN)
- `dashboard_data.js` — precomputed bundle (`const DASHBOARD_DATA = {...}`)
- `ap_boundary.js` — AP state boundary overlay
- `download_drishti_models.py` — one-time bootstrap for Drishti's offline assets

## First-time setup (pitch laptop)

Drishti's speech + intent + LLM models are ~920 MB total. They live on disk in
`models/` and `js/vendor/` — both gitignored so they don't pollute the repo.

```bash
git clone git@github.com:stackfusionlabs/varun-motors-swot.git
cd varun-motors-swot
python download_drishti_models.py     # one-time, ~5-10 min on decent wifi
```

The script is idempotent — re-run any time to fill in missing files.

## Running locally (demo mode, fully offline)

```bash
python -m http.server 3020
open http://localhost:3020
```

Browsers only allow the microphone on `http://localhost` (or HTTPS). Use
`localhost`, not the LAN IP.

After the first page load caches the models, **airplane mode works** — the
whole speech loop (STT → intent → response → TTS) is on-device.

## Updating data

Regenerate `dashboard_data.js` locally (the ETL scripts live outside this repo),
commit it, and push — Vercel redeploys on push to `main`.

## Drishti architecture

Drishti is a **fully offline, deterministic** voice analyst — no LLM, zero
hallucination, instant answers. Everything runs in the browser:

- **STT:** WebSpeech (online, instant) or `Xenova/whisper-base.en` quantized (~90 MB, offline)
- **Understanding:** a rule + fuzzy-match engine (Jaro-Winkler name resolution) that
  parses intents — outlet/city lookup, best/worst/top-N ranking, counts (city &
  state), compare two outlets, "which city is X", aspect feedback (staff/service/
  delivery/pricing/ambiance/followup), complaints, strengths — with conversational
  memory ("best in Vizag" → "and the worst?")
- **TTS:** the browser's `SpeechSynthesis` (OS voices, zero download)

Every number comes straight from `dashboard_data.js`, so answers are exact.

An offline LLM (Llama-3.2-1B via WebLLM) was prototyped but dropped: a 1B model
hallucinated numbers and was too slow (~5–9 s/answer) for a live pitch. The
deterministic engine answers in 0 ms.
