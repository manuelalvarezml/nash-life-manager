import tempfile
import time
from datetime import datetime
from pathlib import Path

import structlog

from backend.config import (
    ASR_BACKEND,
    ASR_CHUNK_LENGTH_S,
    ASR_HF_TOKEN,
    ASR_MODEL,
    ASR_REWIND_WORDS,
    ASR_STRIDE_LENGTH_S,
    AUDIO_DIR,
)

log = structlog.get_logger()

_asr_engine = None
_asr_backend = None
_asr_device = "cpu"


def _resolve_backend() -> str:
    configured = (ASR_BACKEND or "auto").strip().lower()
    if configured in {"transformers", "nemo"}:
        return configured
    model_value = str(ASR_MODEL).lower()
    if "parakeet-tdt" in model_value or Path(ASR_MODEL).suffix.lower() == ".nemo":
        return "nemo"
    return "transformers"


def _get_torch_device(torch_module):
    if torch_module.cuda.is_available():
        return torch_module.device("cuda"), torch_module.float16
    mps_backend = getattr(torch_module.backends, "mps", None)
    if mps_backend and mps_backend.is_available():
        return torch_module.device("mps"), torch_module.float32
    return torch_module.device("cpu"), torch_module.float32


def _load_transformers_asr():
    try:
        import torch
        from transformers import AutoModelForCTC, AutoProcessor, pipeline
    except Exception as e:
        raise RuntimeError(
            "ASR dependencies missing. Install with: pip install torch transformers sentencepiece"
        ) from e

    device, dtype = _get_torch_device(torch)
    log.info("asr_model_loading", model=ASR_MODEL, backend="transformers", device=str(device))
    start = time.time()

    load_kwargs = {}
    if ASR_HF_TOKEN:
        load_kwargs["token"] = ASR_HF_TOKEN

    try:
        processor = AutoProcessor.from_pretrained(ASR_MODEL, **load_kwargs)
        model = AutoModelForCTC.from_pretrained(
            ASR_MODEL,
            torch_dtype=dtype,
            **load_kwargs,
        )
    except Exception as e:
        error_text = str(e)
        auth_or_access_markers = (
            "401",
            "Invalid username or password",
            "private repository",
            "gated repo",
            "not a valid model identifier",
        )
        if not Path(ASR_MODEL).exists() and any(marker in error_text for marker in auth_or_access_markers):
            raise RuntimeError(
                f"ASR model '{ASR_MODEL}' is gated/private. Set HF_TOKEN (or HUGGINGFACE_HUB_TOKEN) "
                "or run 'hf auth login', or switch ASR_MODEL to a local/public model path."
            ) from e
        raise
    model.to(device)
    model.eval()

    pipe_kwargs = {
        "task": "automatic-speech-recognition",
        "model": model,
        "chunk_length_s": ASR_CHUNK_LENGTH_S,
        "stride_length_s": ASR_STRIDE_LENGTH_S,
    }

    tokenizer = getattr(processor, "tokenizer", None)
    feature_extractor = getattr(processor, "feature_extractor", None)
    if tokenizer is not None:
        pipe_kwargs["tokenizer"] = tokenizer
    if feature_extractor is not None:
        pipe_kwargs["feature_extractor"] = feature_extractor

    # Let pipeline use the same device type selected above.
    if device.type == "cuda":
        pipe_kwargs["device"] = 0
    elif device.type == "mps":
        pipe_kwargs["device"] = "mps"
    else:
        pipe_kwargs["device"] = -1

    asr_pipe = pipeline(**pipe_kwargs)
    backend = "transformers-parakeet"
    device_name = str(device)
    log.info("asr_model_ready", model=ASR_MODEL, backend=backend, device=device_name, duration_ms=int((time.time() - start) * 1000))
    return asr_pipe, backend, device_name


def _load_nemo_asr():
    try:
        import nemo.collections.asr as nemo_asr
    except Exception as e:
        raise RuntimeError(
            "NeMo ASR backend selected but nemo_toolkit[asr] is not installed. "
            "Install with: pip install \"nemo_toolkit[asr]\""
        ) from e

    log.info("asr_model_loading", model=ASR_MODEL, backend="nemo", device="cpu")
    start = time.time()
    model_path = Path(ASR_MODEL).expanduser()

    try:
        if model_path.exists():
            if model_path.is_file() and model_path.suffix.lower() == ".nemo":
                asr_model = nemo_asr.models.ASRModel.restore_from(str(model_path))
            elif model_path.is_dir():
                nemo_candidates = sorted(model_path.glob("*.nemo"))
                if nemo_candidates:
                    asr_model = nemo_asr.models.ASRModel.restore_from(str(nemo_candidates[0]))
                else:
                    asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=str(model_path))
            else:
                raise RuntimeError(f"Unsupported ASR_MODEL path: {ASR_MODEL}")
        else:
            asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=ASR_MODEL)
    except Exception as e:
        error_text = str(e)
        auth_or_access_markers = (
            "401",
            "Invalid username or password",
            "private repository",
            "gated repo",
            "not found",
            "does not exist",
        )
        if not model_path.exists() and any(marker in error_text for marker in auth_or_access_markers):
            raise RuntimeError(
                f"ASR model '{ASR_MODEL}' could not be downloaded via NeMo. "
                "Verify the model id, run 'hf auth login', or set ASR_MODEL to a local .nemo file."
            ) from e
        raise

    if hasattr(asr_model, "eval"):
        asr_model.eval()

    backend = "nemo-parakeet"
    device_name = "cpu"
    log.info("asr_model_ready", model=ASR_MODEL, backend=backend, device=device_name, duration_ms=int((time.time() - start) * 1000))
    return asr_model, backend, device_name


def _ensure_asr():
    global _asr_engine, _asr_backend, _asr_device
    if _asr_engine is not None:
        return

    if _resolve_backend() == "nemo":
        _asr_engine, _asr_backend, _asr_device = _load_nemo_asr()
    else:
        _asr_engine, _asr_backend, _asr_device = _load_transformers_asr()


def _convert_audio_to_wav_for_nemo(audio_path: str) -> tuple[str, str | None]:
    """NeMo is most stable with local mono wav; convert when needed."""
    source = Path(audio_path)
    if source.suffix.lower() == ".wav":
        return audio_path, None

    try:
        from pydub import AudioSegment
    except Exception as e:
        raise RuntimeError("pydub/ffmpeg are required to convert non-wav audio for NeMo backend.") from e

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_wav = f.name

    try:
        AudioSegment.from_file(str(source)).set_channels(1).set_frame_rate(16000).export(tmp_wav, format="wav")
    except Exception:
        Path(tmp_wav).unlink(missing_ok=True)
        raise
    return tmp_wav, tmp_wav


def _first_nemo_output(output):
    """Return the first hypothesis-like item from NeMo's varying return shapes."""
    if isinstance(output, tuple) and output:
        output = output[0]
    if isinstance(output, list) and output:
        return output[0]
    return output


def _extract_nemo_text(output) -> str:
    first = _first_nemo_output(output)
    if hasattr(first, "text"):
        return str(first.text or "").strip()
    if isinstance(first, dict):
        for key in ("text", "pred_text", "transcript"):
            value = first.get(key)
            if value:
                return str(value).strip()
    return str(first or "").strip()


def _extract_nemo_word_timestamps(output) -> list[dict]:
    """Extract word timestamps from a NeMo Hypothesis when available.

    NeMo usually returns `hypothesis.timestamp["word"]` with items shaped like:
    {"word": "...", "start": 12.34, "end": 12.56, ...}. We normalize just the
    fields this chunker needs and ignore malformed/unknown shapes.
    """
    first = _first_nemo_output(output)
    timestamp = getattr(first, "timestamp", None) or getattr(first, "timestep", None)
    if isinstance(first, dict):
        timestamp = timestamp or first.get("timestamp") or first.get("timestep")

    word_items = None
    if isinstance(timestamp, dict):
        word_items = timestamp.get("word") or timestamp.get("words") or timestamp.get("word_timestamps")
    elif isinstance(first, dict):
        word_items = first.get("word_timestamps") or first.get("words")

    if not isinstance(word_items, list):
        return []

    normalized: list[dict] = []
    for item in word_items:
        if isinstance(item, dict):
            word = str(item.get("word") or item.get("text") or "").strip()
            start = _coerce_timestamp_seconds(item.get("start"))
            end = _coerce_timestamp_seconds(item.get("end"))
            normalized.append({"word": word, "start": start, "end": end})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            word = str(item[0]).strip()
            start = _coerce_timestamp_seconds(item[1])
            end = _coerce_timestamp_seconds(item[2]) if len(item) >= 3 else None
            normalized.append({"word": word, "start": start, "end": end})

    return [item for item in normalized if item.get("start") is not None]


def _coerce_timestamp_seconds(value) -> float | None:
    try:
        if value is None:
            return None
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return seconds


def _transcribe_nemo_file(audio_path: str, timestamps: bool = False) -> tuple[str, list[dict]]:
    """Transcribe one prepared audio file, optionally requesting word timestamps."""
    if timestamps:
        try:
            output = _asr_engine.transcribe([audio_path], timestamps=True, verbose=False)
            return _extract_nemo_text(output), _extract_nemo_word_timestamps(output)
        except Exception as exc:
            log.warning("nemo_word_timestamps_unavailable", error=str(exc))

    output = _asr_engine.transcribe([audio_path], verbose=False)
    return _extract_nemo_text(output), []


def _deduplicate_boundary(prev_text: str, next_text: str, max_words: int = 32) -> str:
    """Strip words from the start of next_text that already appear at end of prev_text.

    Used to remove duplicate words that fall in the rewind window between adjacent
    chunks. Comparison is case-insensitive and strips punctuation so that "comí,"
    matches "comí".
    """
    prev_words = prev_text.split()
    next_words = next_text.split()

    def normalize(w: str) -> str:
        return w.lower().strip(".,!?¿¡;:\"'")

    for n in range(min(max_words, len(prev_words), len(next_words)), 0, -1):
        if [normalize(w) for w in prev_words[-n:]] == [normalize(w) for w in next_words[:n]]:
            return " ".join(next_words[n:])
    return next_text


def _next_offset_from_rewind_word(
    offset_ms: int,
    segment_duration_ms: int,
    text: str,
    word_timestamps: list[dict],
    rewind_words: int,
) -> int:
    """Return the next chunk start based on the -N word timestamp.

    When NeMo exposes word timestamps, we use the start time of word -N in the
    current segment. If timestamps are absent, estimate the same position from
    the transcript word count so the fallback still follows the word-rewind
    strategy instead of a fixed seconds overlap.
    """
    if rewind_words <= 0:
        return offset_ms + segment_duration_ms

    if len(word_timestamps) > rewind_words:
        start_s = word_timestamps[-rewind_words].get("start")
        if start_s is not None:
            return offset_ms + int(float(start_s) * 1000)

    words = text.split()
    if len(words) > rewind_words:
        rewind_position = max(0, len(words) - rewind_words)
        ratio = rewind_position / len(words)
        return offset_ms + int(segment_duration_ms * ratio)

    return offset_ms + segment_duration_ms


def _transcribe_nemo_chunked(audio_path: str, chunk_s: int = 120) -> str:
    """Transcribe long audio in word-aware chunks to prevent OOM.

    NeMo Transducer lattice grows O(N) with full sequence length; a 12-min
    recording creates ~15-18 GB of intermediate tensors on 16 GB unified memory.
    Processing bounded chunks caps peak RAM at model weights plus one chunk.

    Instead of using a fixed seconds-based overlap, each next chunk starts at
    the timestamp of the Nth word before the end of the previous chunk
    (`ASR_REWIND_WORDS`, default 15). This gives Parakeet a natural language
    runway around the seam without arbitrarily cutting in the middle of speech.
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path).set_channels(1).set_frame_rate(16000)
    duration_ms = len(audio)
    duration_s = duration_ms / 1000.0
    chunk_ms = chunk_s * 1000

    # Short audio: single-pass, no chunking overhead.
    if duration_s <= chunk_s:
        prepared, cleanup = _convert_audio_to_wav_for_nemo(audio_path)
        try:
            text, _word_timestamps = _transcribe_nemo_file(str(prepared), timestamps=False)
            return text
        finally:
            if cleanup:
                Path(cleanup).unlink(missing_ok=True)

    estimated_chunks = max(1, (duration_ms + chunk_ms - 1) // chunk_ms)
    log.info(
        "transcription_chunked",
        duration_s=round(duration_s, 1),
        chunk_s=chunk_s,
        rewind_words=ASR_REWIND_WORDS,
        estimated_chunks=estimated_chunks,
    )

    parts: list[str] = []
    offset_ms = 0
    chunk_index = 0
    while offset_ms < duration_ms:
        segment_end_ms = min(offset_ms + chunk_ms, duration_ms)
        segment = audio[offset_ms:segment_end_ms]
        segment_duration_ms = segment_end_ms - offset_ms
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        try:
            segment.export(tmp, format="wav")
            raw_text, word_timestamps = _transcribe_nemo_file(tmp, timestamps=True)
        finally:
            Path(tmp).unlink(missing_ok=True)

        text = raw_text
        if text:
            if parts:
                # Remove words duplicated by the word-based rewind window.
                text = _deduplicate_boundary(parts[-1], text, max_words=max(32, ASR_REWIND_WORDS * 3))
            if text:
                parts.append(text)

        if segment_end_ms >= duration_ms:
            break

        candidate_ms = _next_offset_from_rewind_word(
            offset_ms=offset_ms,
            segment_duration_ms=segment_duration_ms,
            text=raw_text,
            word_timestamps=word_timestamps,
            rewind_words=ASR_REWIND_WORDS,
        )
        # Keep progress monotonic and bounded by the current segment.
        next_offset_ms = min(max(candidate_ms, offset_ms + 1000), segment_end_ms)
        if next_offset_ms <= offset_ms + 1000:
            next_offset_ms = segment_end_ms

        log.info(
            "transcription_chunk_done",
            chunk_index=chunk_index,
            start_s=round(offset_ms / 1000, 2),
            end_s=round(segment_end_ms / 1000, 2),
            next_start_s=round(next_offset_ms / 1000, 2),
            words=len(raw_text.split()) if raw_text else 0,
            word_timestamps=len(word_timestamps),
        )

        offset_ms = next_offset_ms
        chunk_index += 1

    return " ".join(parts)


def save_audio(audio_bytes: bytes, entry_type: str = "spontaneous", suffix: str = ".webm") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{entry_type}{suffix}"
    dest = AUDIO_DIR / filename
    dest.write_bytes(audio_bytes)
    log.info("audio_saved", path=str(dest), size_kb=len(audio_bytes) / 1024)
    return dest


def transcribe(audio_path: str | Path) -> dict:
    """Transcribe an audio file using configured ASR backend/model."""
    _ensure_asr()

    audio_path = str(audio_path)
    log.info("transcription_started", path=audio_path, backend=_asr_backend)
    start = time.time()

    if _asr_backend == "nemo-parakeet":
        text = _transcribe_nemo_chunked(audio_path, chunk_s=ASR_CHUNK_LENGTH_S)
    else:
        result = _asr_engine(audio_path, return_timestamps=False)
        if isinstance(result, dict):
            text = (result.get("text") or "").strip()
        else:
            text = str(result or "").strip()

    elapsed_ms = int((time.time() - start) * 1000)
    word_count = len(text.split())

    log.info(
        "transcription_done",
        model=ASR_MODEL,
        backend=_asr_backend,
        device=_asr_device,
        word_count=word_count,
        duration_ms=elapsed_ms,
    )

    return {
        "text": text,
        "word_count": word_count,
        "duration_ms": elapsed_ms,
        "language": "es-en",
    }


def transcribe_bytes(audio_bytes: bytes, suffix: str = ".webm") -> dict:
    """Transcribe audio from raw bytes by writing to a temp file."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        return transcribe(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
