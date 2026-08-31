"""Queue watcher: converts harvested Hotmart stream URLs into clean transcript markdown.

transcript_receiver.py's /urls endpoint drops {name, master, child} JSON files into the
queue folder. This worker picks each up, uses yt-dlp to download the English subtitle
track from the HLS master URL, cleans the VTT (timestamps out, rolling-caption duplicate
lines deduped), and writes <out>/<slug>.md.

IMPORTANT: master-URL tokens (hdnts) expire ~8 minutes after the lecture page loaded, so
run this DURING harvesting, not after. Jobs that fail (expired token, CDN refusal, empty
captions) are shelved as *.failed so the queue drains — re-harvest those lectures fresh.

Usage:  python tools/hotmart_captions.py [--queue queue] [--out transcripts]
                                         [--idle-exit 300] [--sub-langs "en.*,eng"]
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERER = "https://player.hotmart.com/"


def clean_vtt(vtt_text: str) -> str:
    raw = []
    for line in vtt_text.splitlines():
        t = line.strip()
        if (not t or t == "WEBVTT" or t.startswith(("X-TIMESTAMP", "NOTE", "STYLE"))
                or re.fullmatch(r"\d+", t) or "-->" in t):
            continue
        t = re.sub(r"</?[^>]+>", "", t)  # strip cue tags
        raw.append(t)
    kept = []
    for line in raw:  # rolling captions repeat lines across cue boundaries
        if kept and (line == kept[-1] or (len(kept) > 1 and line == kept[-2])):
            continue
        kept.append(line)
    return "\n".join(kept)


def process(job_file: Path, out_dir: Path, sub_langs: str) -> str:
    data = json.loads(job_file.read_text(encoding="utf-8"))
    name, master = data["name"], data["master"]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()[:120]
    out_md = out_dir / f"{slug}.md"
    if out_md.exists():
        job_file.unlink()
        return f"skip (exists): {out_md.name}"

    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "cap"
        cmd = [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-subs",
               "--sub-langs", sub_langs, "--referer", REFERER,
               "-o", str(base), "--no-warnings", "--quiet", master]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        vtts = list(Path(td).glob("*.vtt"))
        if not vtts:
            # expired token or CDN refusal — shelve so the queue drains; re-harvest to retry
            job_file.rename(job_file.with_suffix(".failed"))
            return f"FAIL {name}: rc={r.returncode} {r.stderr.strip()[:300]}"
        text = clean_vtt(vtts[0].read_text(encoding="utf-8"))
        if len(text) < 200:
            job_file.rename(job_file.with_suffix(".failed"))
            return f"FAIL {name}: transcript too short ({len(text)} chars)"
        out_md.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
        job_file.unlink()
        return f"saved {out_md.name} ({len(text)} chars)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default="queue")
    ap.add_argument("--out", default="transcripts")
    ap.add_argument("--idle-exit", type=int, default=300, help="exit after this many idle seconds")
    ap.add_argument("--sub-langs", default="en.*,eng")
    args = ap.parse_args()
    queue_dir = (ROOT / args.queue).resolve()
    out_dir = (ROOT / args.out).resolve()
    queue_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    idle = 0.0
    print(f"watching {queue_dir} -> {out_dir}")
    while idle < args.idle_exit:
        jobs = sorted(queue_dir.glob("*.json"))
        if not jobs:
            time.sleep(5)
            idle += 5
            continue
        idle = 0.0
        for job in jobs:
            try:
                print(process(job, out_dir, args.sub_langs), flush=True)
            except Exception as e:  # noqa: BLE001 - keep the watcher alive
                print(f"ERROR {job.name}: {e}", flush=True)
                job.rename(job.with_suffix(".failed"))
    print(f"idle {args.idle_exit}s, exiting")


if __name__ == "__main__":
    main()
