"""Copy legacy ~/.nash/audio files into data/audio and register missing ones in diary."""

import shutil
from pathlib import Path

import structlog

from backend.audio.brief_summary import brief_summary_spanish
from backend.audio.transcriber import transcribe
from backend.config import AUDIO_DB_PREFIX, AUDIO_DIR, LEGACY_AUDIO_DIR
from backend.db.schema import (
    delete_diary_entry,
    get_registered_audio_basenames,
    insert_diary_entry,
    link_audio_if_transcript_matches,
    update_diary_transcript_summary,
)

log = structlog.get_logger()

_AUDIO_SUFFIXES = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".opus", ".mp4", ".flac"}


def _is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in _AUDIO_SUFFIXES


def audio_rel_path(filename: str) -> str:
    return f"{AUDIO_DB_PREFIX}/{filename}"


def copy_legacy_files_to_data_audio() -> int:
    """Copy files from ~/.nash/audio into repo data/audio. Returns count copied."""
    if not LEGACY_AUDIO_DIR.is_dir():
        return 0
    n = 0
    for src in LEGACY_AUDIO_DIR.iterdir():
        if not src.is_file() or not _is_audio_file(src):
            continue
        dest = AUDIO_DIR / src.name
        if dest.exists():
            continue
        try:
            shutil.copy2(src, dest)
            n += 1
            log.info("legacy_audio_copied", from_=str(src), to=str(dest))
        except OSError as e:
            log.warning("legacy_audio_copy_failed", path=str(src), error=str(e))
    return n


def ingest_orphan_audio_files() -> int:
    """
    For each file in data/audio with no diary row referencing that basename,
    transcribe, summarize, and insert a spontaneous diary entry.

    The diary row is inserted BEFORE transcription so that a hard crash mid-
    transcription (OOM, signal, etc.) won't cause the same file to be retried
    on every subsequent server restart.
    """
    registered = get_registered_audio_basenames()
    count = 0
    for path in sorted(AUDIO_DIR.iterdir(), key=lambda p: p.name):
        if not path.is_file() or not _is_audio_file(path):
            continue
        if path.name in registered:
            continue
        rel = audio_rel_path(path.name)
        # Register the file first with a placeholder so restarts won't retry.
        entry_id = insert_diary_entry(
            entry_type="spontaneous",
            raw_transcript="",
            summary="(pendiente de transcripción)",
            audio_path=rel,
            duration_s=None,
        )
        registered.add(path.name)
        log.info("ingest_audio_registered", file=path.name, entry_id=entry_id)
        try:
            result = transcribe(path)
            transcript = (result.get("text") or "").strip()
            if transcript:
                summary = brief_summary_spanish(transcript)
                # Try to merge with an existing row that already has this transcript.
                if link_audio_if_transcript_matches(transcript, rel, summary):
                    # A better match was found; remove the placeholder row we just added.
                    delete_diary_entry(entry_id)
                else:
                    update_diary_transcript_summary(entry_id, transcript, summary)
            else:
                log.info("ingest_empty_transcript", file=path.name)
                update_diary_transcript_summary(entry_id, "", "(Sin transcripción detectada)")
            count += 1
        except Exception as e:
            log.error("ingest_audio_transcription_failed", file=path.name, entry_id=entry_id, error=str(e))
            # Entry was already registered; transcription can be retried manually later.
    return count


def run_audio_migration() -> dict:
    """Copy legacy folder, then backfill diary rows for orphan files."""
    copied = copy_legacy_files_to_data_audio()
    ingested = ingest_orphan_audio_files()
    return {"legacy_copied": copied, "ingested": ingested, "audio_dir": str(AUDIO_DIR.resolve())}
