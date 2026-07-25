"""
Transcribe audio entries that are registered in the diary but not yet transcribed.

Usage (from repo root, venv active):

  List pending entries:
      python scripts/transcribe_entry.py --list

  Process all pending entries one by one:
      python scripts/transcribe_entry.py --all

  Process a single entry by id:
      python scripts/transcribe_entry.py <entry_id>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.audio.brief_summary import brief_summary_spanish
from backend.audio.transcriber import transcribe
from backend.config import AUDIO_DIR, DB_PATH
from backend.db.schema import update_diary_transcript_summary

import sqlite3


def get_pending() -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, timestamp, audio_path, summary
           FROM diary_entries
           WHERE (summary = '(pendiente de transcripción)' OR TRIM(raw_transcript) = '')
             AND audio_path IS NOT NULL AND TRIM(audio_path) != ''
           ORDER BY timestamp"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def process_entry(entry: dict) -> bool:
    audio_path = AUDIO_DIR.parent.parent / entry["audio_path"]  # repo root / data/audio/...
    # Fallback: try AUDIO_DIR directly if the path doesn't exist
    if not audio_path.exists():
        audio_path = AUDIO_DIR / Path(entry["audio_path"]).name

    if not audio_path.exists():
        print(f"  ERROR: audio file not found: {entry['audio_path']}")
        return False

    size_mb = audio_path.stat().st_size / 1_048_576
    print(f"  Transcribing {audio_path.name} ({size_mb:.1f} MB) …")
    result = transcribe(audio_path)
    transcript = (result.get("text") or "").strip()
    print(f"  Done — {result.get('word_count', 0)} words in {result.get('duration_ms', 0) / 1000:.1f}s")

    if not transcript:
        summary = "(Sin transcripción detectada)"
        print("  WARNING: empty transcript")
    else:
        print("  Generating summary …")
        summary = brief_summary_spanish(transcript)
        print(f"  Summary: {summary}")

    update_diary_transcript_summary(entry["id"], transcript, summary)
    print(f"  Entry #{entry['id']} updated.")
    return True


def main():
    args = sys.argv[1:]

    if not args or args[0] == "--list":
        pending = get_pending()
        if not pending:
            print("No pending entries.")
            return
        print(f"{len(pending)} pending entr{'y' if len(pending) == 1 else 'ies'}:")
        for e in pending:
            print(f"  #{e['id']}  {e['timestamp']}  {e['audio_path']}")
        if args and args[0] == "--list":
            return
        # No args: just print list and exit
        return

    if args[0] == "--all":
        pending = get_pending()
        if not pending:
            print("No pending entries.")
            return
        print(f"Processing {len(pending)} entr{'y' if len(pending) == 1 else 'ies'} …\n")
        for i, entry in enumerate(pending, 1):
            print(f"[{i}/{len(pending)}] Entry #{entry['id']}  {entry['timestamp']}")
            process_entry(entry)
            print()
        print("Done.")
        return

    # Single entry by id
    try:
        entry_id = int(args[0])
    except ValueError:
        print(__doc__)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id, timestamp, audio_path, summary FROM diary_entries WHERE id = ?", (entry_id,)).fetchone()
    conn.close()

    if not row:
        print(f"ERROR: entry #{entry_id} not found in DB.")
        sys.exit(1)

    entry = dict(row)
    if not entry.get("audio_path"):
        print(f"ERROR: entry #{entry_id} has no audio_path.")
        sys.exit(1)

    print(f"Entry #{entry_id}  {entry['timestamp']}")
    process_entry(entry)


if __name__ == "__main__":
    main()
