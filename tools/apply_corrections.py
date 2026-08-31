"""Apply the ASR-correction glossary to a transcript folder, into a clean copy.

Originals are never modified — corrected copies land in --out. Default is a dry-run
report (per-pattern hit counts, per-file totals); add --write to actually write.

Usage:
  python tools/apply_corrections.py --dir transcripts --out transcripts-clean            # dry run
  python tools/apply_corrections.py --dir transcripts --out transcripts-clean --write
  python tools/apply_corrections.py --dir transcripts --out transcripts-clean --write --risky
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_rules(glossary: Path, include_risky: bool):
    data = json.loads(glossary.read_text(encoding="utf-8"))
    entries = list(data.get("safe", []))
    if include_risky:
        entries += list(data.get("risky", []))
    rules = []
    for e in entries:
        flags = 0 if e.get("case_sensitive") else re.IGNORECASE
        rules.append((re.compile(e["pattern"], flags), e["replacement"], e["pattern"]))
    return rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="transcripts")
    ap.add_argument("--out", default="transcripts-clean")
    ap.add_argument("--glossary", default="corrections.json")
    ap.add_argument("--write", action="store_true", help="write corrected copies (default: dry-run report)")
    ap.add_argument("--risky", action="store_true", help="also apply the 'risky' glossary tier")
    args = ap.parse_args()

    src = (ROOT / args.dir).resolve()
    dst = (ROOT / args.out).resolve()
    rules = load_rules((ROOT / args.glossary).resolve(), args.risky)
    if not src.is_dir():
        raise SystemExit(f"no such folder: {src}")

    pattern_hits = Counter()
    files = sorted(src.glob("*.md"))
    changed_files = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        original = text
        for rx, repl, key in rules:
            text, n = rx.subn(repl, text)
            pattern_hits[key] += n
        if text != original:
            changed_files += 1
        if args.write:
            dst.mkdir(parents=True, exist_ok=True)
            (dst / f.name).write_text(text, encoding="utf-8")

    mode = "WROTE" if args.write else "DRY-RUN"
    print(f"[{mode}] {len(files)} files scanned, {changed_files} with changes"
          + (f", clean copies in {dst}" if args.write else " (use --write to apply)"))
    for key, n in pattern_hits.most_common():
        if n:
            print(f"  {n:6d}  {key}")


if __name__ == "__main__":
    main()
