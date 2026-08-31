# course-transcript-extractor

Extract clean English markdown transcripts from a **Teachable course that uses the Hotmart video player** (e.g. Zero To Mastery Academy), end to end: enumerate the curriculum, harvest each lecture's stream URLs from a signed-in browser, download the caption track with yt-dlp, and clean the VTT into one markdown file per lecture.

Built 2026-08-31 to capture the ZTM "Claude Code Bootcamp" (77 videos, ~125k words) for the Megabot Learn onboarding project. Everything learned the hard way is baked in — read [AGENT-GUIDE.md](AGENT-GUIDE.md) for the drive-it-with-Claude runbook and the troubleshooting table.

## Why this architecture

Naive approaches fail. In-browser caption fetching gets intermittent Akamai 403s; Chrome cookie export for yt-dlp is broken on Windows (app-bound encryption); course platforms sign every stream URL per page-load. The pattern that works — same split used by Teachable-dl, tcdown, and OmniGet — is:

> **The browser only harvests. Deterministic local tools do the fetching.**

```
┌──────────────────────┐  POST /urls   ┌─────────────────────┐  watches   ┌──────────────────────┐
│ Signed-in Chrome     │ ─────────────▶│ transcript_receiver  │ ──────────▶│ hotmart_captions.py  │
│ (Claude drives it):  │  {name,       │ 127.0.0.1:8765       │  queue/    │ yt-dlp downloads the │
│ per lecture, read the│   master,     │ writes queue jobs +  │            │ eng .vtt from the    │
│ HLS master m3u8 URL  │   child}      │ finished transcripts │            │ HLS master, cleans   │
│ from performance API │               └─────────────────────┘            │ VTT → markdown       │
└──────────────────────┘                                                  └──────────────────────┘
```

- ~13 seconds of browser time per lecture; yt-dlp does the heavy lifting with proper retries.
- Signed URLs never pass through the AI model (browser extensions redact them anyway) — the page POSTs them straight to localhost.

## Prerequisites

- Windows/macOS/Linux with **Python 3.10+** and `pip install yt-dlp`
- **Chrome with the [Claude extension](https://chromewebstore.google.com/detail/fcoeoabgfenejglbffodgkkbkcdhcgfn)** connected to a Claude Code session (or drive the browser steps manually with DevTools — the JS payloads in AGENT-GUIDE.md work either way)
- A Chrome profile **signed into the course** (you must have legitimate paid/free access)

## Quickstart

```bash
# terminal 1 — receiver (writes transcripts/ and queue/ in the repo root by default)
python tools/transcript_receiver.py

# terminal 2 — worker (converts queued jobs as they arrive; exits after 5 idle minutes)
python tools/hotmart_captions.py
```

Then follow [AGENT-GUIDE.md](AGENT-GUIDE.md) to drive the browser: scrape the curriculum once, then loop the per-lecture harvest payload. Audit at the end against the curriculum; re-harvest anything shelved as `.failed` (tokens expire ~8 minutes after page load — that's normal, just re-run those lectures).

## Quality pass (ASR artifacts)

Course captions are auto-generated speech recognition. Known artifacts and the correction policy live in [QUALITY-NOTES-TEMPLATE.md](QUALITY-NOTES-TEMPLATE.md) — copy it into your output folder. To generate corrected copies (originals stay verbatim):

```bash
python tools/apply_corrections.py --dir transcripts --out transcripts-clean          # dry-run report
python tools/apply_corrections.py --dir transcripts --out transcripts-clean --write  # write clean copies
```

Edit [corrections.json](corrections.json) to add course-specific fixes (e.g. this repo ships the "cloud code" → "Claude Code" glossary from the Claude Code Bootcamp).

## Legal / intended use

For **personal study aids of content you have legitimate access to**. Transcripts are internal reference material: do not republish course text, and write any derivative training/onboarding material in your own words, citing the course. Respect the platform's terms of service.

## Repo map

| Path | What |
|------|------|
| `tools/transcript_receiver.py` | localhost HTTP receiver: `/save` (write transcript md), `/urls` (queue a job), `/list` |
| `tools/hotmart_captions.py` | queue watcher: yt-dlp subtitle download → VTT cleanup → markdown |
| `tools/apply_corrections.py` | dry-run/apply ASR-glossary corrections into a clean copy folder |
| `corrections.json` | regex glossary (safe + risky tiers) |
| `AGENT-GUIDE.md` | the full runbook: browser payloads, audit loop, troubleshooting |
| `QUALITY-NOTES-TEMPLATE.md` | drop into your output folder so the next consumer knows what they're reading |
