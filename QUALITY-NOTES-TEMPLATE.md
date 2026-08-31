# Quality Notes — read this before consuming these transcripts
**For:** any bot or human building on this corpus · **Course:** [name] · **Extracted:** [date]

## Provenance
These are the course's own auto-generated (ASR) English captions, extracted verbatim from the video player's subtitle tracks and cleaned only mechanically (cue timestamps stripped, rolling-caption duplicate lines removed). Nothing has been paraphrased — the words are whatever the speech recognizer heard, including its mistakes.

**Policy: these files stay verbatim.** They are the source of truth. Apply corrections at consumption time, or generate a corrected copy with `tools/apply_corrections.py` — never edit the originals in place.

## Known ASR artifacts
| You will read | The speaker actually said | Confidence |
|---------------|---------------------------|------------|
| `cloud code` | Claude Code | certain |
| `clod .ai`, `cloud .ai` | claude.ai | certain |
| `clod` (standalone) | Claude | near-certain in context |
| `AI -assisted` (space before hyphen) | AI-assisted | certain — caption line-wrap artifact |
| `3 a .m.` (space before period) | 3 a.m. | certain — same artifact |
| Product names generally | may be mangled | check before quoting |

[Add course-specific rows as you find them, and mirror them into corrections.json.]

## How to correct (for the next bot)
1. **Deterministic pass:** `python tools/apply_corrections.py --dir <transcripts> --out <transcripts-clean>` (dry-run first; `--write` to apply; `--risky` for the review-needed tier). Corrected copies go to a separate folder; originals stay untouched.
2. **Judgment calls:** fix unglossaried artifacts only when context makes intent unambiguous — and prefer fixing at the point of use over editing the corpus.
3. **Never "correct" meaning.** If a sentence reads wrong and context doesn't resolve it, check the actual lecture video (lecture ID is in each filename: `id-<lectureId>`) or flag it — don't guess.

## Licensing reminder
This corpus is an internal study aid for content the owner has legitimate access to. Don't republish transcript text in any deliverable — derivative material must be original writing that cites the course.
