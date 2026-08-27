import asyncio
import json
import uuid
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import structlog
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage

from backend.config import AUDIO_DIR, ensure_dirs
from backend.exercise_engine import build_exercise_dashboard, generate_workout_plan
from backend.calendar_engine import (
    approve_calendar_suggestion,
    build_calendar_dashboard,
    process_schedule_input,
    reject_calendar_suggestion,
    sync_engine_suggestions,
)
from backend.db.calendar import (
    get_schedule_preferences,
    update_calendar_item,
    update_schedule_preferences,
)
from backend.db.schema import (
    apply_profile_summary_updates,
    init_db_sync,
    get_db,
    insert_diary_entry,
    insert_question_answer,
    get_todays_questions,
    update_question_richness,
    get_question_stats,
    get_self_profile,
    upsert_self_profile,
    get_unfilled_profile_fields,
    SELF_PROFILE_SECTIONS,
    update_diary_nash_response,
    get_entries_without_response,
    get_diary_conversation,
    add_conversation_message,
    get_conversation_context,
    MAX_CONVERSATION_MESSAGES,
    # Phase 3: Goals
    get_life_domains,
    get_latest_domain_ratings,
    get_domain_rating_history,
    insert_domain_rating,
    bulk_insert_domain_ratings,
    get_goals,
    get_goal_by_id,
    insert_goal,
    update_goal,
    delete_goal,
    get_goals_summary,
    get_goals_graph,
    insert_goal_relation,
    delete_goal_relation,
    # Phase 5: Nutrition, Exercise, Finance
    create_module_discovery_session,
    get_module_discovery_session,
    get_active_module_discovery,
    get_nutrition_profile,
    upsert_nutrition_profile,
    insert_food_entry,
    get_food_entries_today,
    get_nutrition_daily_totals,
    get_exercise_profile,
    upsert_exercise_profile,
    list_exercise_equipment,
    insert_exercise_equipment,
    delete_exercise_equipment,
    get_body_measurement_snapshots,
    insert_body_measurement_snapshot,
    get_workout_templates,
    insert_workout_template,
    insert_workout_session,
    get_workout_sessions,
    get_personal_records,
    get_memories,
    insert_structured_memory,
    update_memory,
    delete_memory,
    get_finance_profile,
    upsert_finance_profile,
    get_expense_categories,
    insert_expense,
    get_expenses,
    get_monthly_expense_summary,
)
from backend.logging_config import setup_logging
from backend.llm import restore_local_aliases

log = structlog.get_logger()

MODULE_NAMES_ES = {
    "nutrition": "nutricion",
    "exercise": "ejercicio",
    "finance": "finanzas",
}


def _content_to_text(content) -> str:
    """Normalize LangChain message content (string or chunks) into plain text."""
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        return "\n".join(p.strip() for p in parts if p and p.strip()).strip()

    return str(content or "").strip()


def _looks_like_tool_payload(text: str) -> bool:
    """Heuristic: detect tool-call JSON accidentally returned as final assistant content."""
    if not text:
        return False

    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\n?", "", candidate).strip()
        candidate = re.sub(r"\n?```$", "", candidate).strip()

    # Common shape emitted by some models: {"name":"tool_name","parameters":{...}}
    if re.match(r'^\{\s*"name"\s*:\s*".+?"\s*,\s*"parameters"\s*:\s*\{', candidate):
        return True

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            has_name = isinstance(parsed.get("name"), str)
            has_args = isinstance(parsed.get("parameters"), dict) or isinstance(parsed.get("args"), dict)
            return has_name and has_args
    except Exception:
        return False

    return False


def _pick_user_facing_response(messages: list) -> str:
    """Pick the last assistant message meant for user display (skip tool payload JSON)."""
    for msg in reversed(messages or []):
        msg_type = getattr(msg, "type", "")
        if msg_type not in ("ai", "assistant"):
            continue
        text = _content_to_text(getattr(msg, "content", ""))
        if not text:
            continue
        if _looks_like_tool_payload(text):
            continue
        return text
    return ""


async def _run_migration_background():
    from backend.audio.ingest import run_audio_migration
    try:
        mig = await asyncio.to_thread(run_audio_migration)
        log.info("audio_migration_done", **mig)
    except Exception as e:
        log.error("audio_migration_failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    setup_logging()
    init_db_sync()
    asyncio.create_task(_run_migration_background())
    log.info("nash_started")
    yield
    log.info("nash_stopped")


app = FastAPI(title="Nash Life Manager", lifespan=lifespan)

app.mount(
    "/media/audio",
    StaticFiles(directory=str(AUDIO_DIR)),
    name="audio_files",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/audio/upload")
async def upload_audio(
    audio: UploadFile = File(...),
    entry_type: str = Form("spontaneous"),
    thread_id: str = Form(""),
    duration_s: str = Form(""),
):
    """Upload audio → save → transcribe → diary row + summary → agent → stream response."""
    from backend.audio.brief_summary import brief_summary_spanish
    from backend.audio.ingest import audio_rel_path
    from backend.audio.transcriber import save_audio, transcribe
    from backend.agent.graph import get_graph

    audio_bytes = await audio.read()
    suffix = "." + (audio.filename or "audio.webm").split(".")[-1]

    audio_path = await asyncio.to_thread(save_audio, audio_bytes, entry_type, suffix)
    result = await asyncio.to_thread(transcribe, audio_path)

    transcript = result["text"]
    if not transcript.strip():
        return {"error": "No se detectó habla en el audio.", "transcript": ""}

    if not thread_id:
        thread_id = str(uuid.uuid4())

    transcription_ms = result["duration_ms"]
    duration_val: float | None = None
    if duration_s and duration_s.strip():
        try:
            duration_val = float(duration_s)
        except ValueError:
            duration_val = None

    summary = await asyncio.to_thread(brief_summary_spanish, transcript)
    rel_audio = audio_rel_path(Path(audio_path).name)
    entry_id = await asyncio.to_thread(
        lambda: insert_diary_entry(
            entry_type=entry_type,
            raw_transcript=transcript,
            summary=summary,
            domain_tags="[]",
            energy_level=None,
            audio_path=rel_audio,
            duration_s=duration_val,
        )
    )

    # Phase 2: Semantic decomposition
    from backend.agent.semantic_decomposer import decompose_transcript
    decomposed_units = await asyncio.to_thread(decompose_transcript, transcript, entry_id)

    # Phase 2: Background profile synthesis (every N entries)
    from backend.agent.profile_synthesize import should_trigger_synthesis, run_background_synthesis
    from backend.db.schema import get_entry_count
    entry_count = get_entry_count()
    synthesis_triggered = False
    if should_trigger_synthesis(entry_count):
        asyncio.create_task(run_background_synthesis())
        synthesis_triggered = True
        log.info("synthesis_triggered", entry_count=entry_count)

    audio_play_url = f"/media/audio/{Path(audio_path).name}"
    log.info(
        "audio_processed",
        transcript_words=result["word_count"],
        thread_id=thread_id,
        diary_id=entry_id,
        semantic_units=len(decomposed_units),
        synthesis_triggered=synthesis_triggered,
    )

    agent_transcript = (
        f"{transcript}\n\n[Nota del sistema: esta grabación de voz ya fue guardada en el diario "
        f"(#{entry_id}) con resumen breve. No uses log_diary_entry para este mismo contenido; "
        "el clasificador semántico ya guardó recuerdos y sugerencias de agenda detectadas, así que no uses "
        "log_memory ni apply_schedule_instruction para repetirlas. Sí puedes usar log_profile_fact si aplica.]"
    )

    async def generate():
        graph = get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        input_msg = {"messages": [HumanMessage(content=agent_transcript)]}

        yield f"data: {json.dumps({'type': 'transcript', 'text': transcript, 'transcription_ms': transcription_ms})}\n\n"
        yield f"data: {json.dumps({'type': 'diary', 'diary_entry_id': entry_id, 'summary': summary, 'audio_play_url': audio_play_url})}\n\n"
        if decomposed_units:
            yield f"data: {json.dumps({'type': 'semantic_units', 'count': len(decomposed_units)})}\n\n"

        nash_response_text = ""
        try:
            final_response = await asyncio.to_thread(graph.invoke, input_msg, config)
            messages = final_response.get("messages", [])
            if messages:
                tool_calls = []
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_calls.append({"name": tc.get("name", ""), "args": tc.get("args", {})})
                    if hasattr(msg, "name") and hasattr(msg, "content"):
                        if msg.type == "tool":
                            tool_calls.append({"name": msg.name, "result": msg.content[:200]})

                nash_response_text = restore_local_aliases(_pick_user_facing_response(messages))
                if not nash_response_text:
                    # Safety fallback: avoid empty UI when model ends on tool-call payload.
                    nash_response_text = (
                        "Te escuché y guardé tu entrada. "
                        "Si quieres, te ayudo a convertir esto en 2-3 acciones concretas para hoy."
                    )
                    log.warning("response_fallback_used", reason="no_user_facing_ai_message", diary_id=entry_id)

                yield f"data: {json.dumps({'type': 'response', 'text': nash_response_text})}\n\n"

                if tool_calls:
                    yield f"data: {json.dumps({'type': 'tools', 'calls': tool_calls})}\n\n"

        except Exception as e:
            log.error("agent_error", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

        # Save Nash's response to the diary entry
        if nash_response_text:
            await asyncio.to_thread(update_diary_nash_response, entry_id, nash_response_text)
            log.info("nash_response_saved", entry_id=entry_id, response_len=len(nash_response_text))

        yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat")
async def chat_text(
    text: str = Form(...),
    thread_id: str = Form(""),
):
    """Text input → agent → stream response."""
    from backend.agent.graph import get_graph

    if not thread_id:
        thread_id = str(uuid.uuid4())

    async def generate():
        graph = get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        input_msg = {"messages": [HumanMessage(content=text)]}

        try:
            final_response = await asyncio.to_thread(graph.invoke, input_msg, config)
            messages = final_response.get("messages", [])
            if messages:
                content = _pick_user_facing_response(messages)
                if not content:
                    content = "Te leí. Si quieres, lo aterrizamos en un siguiente paso concreto."
                    log.warning("chat_response_fallback_used", reason="no_user_facing_ai_message")
                yield f"data: {json.dumps({'type': 'response', 'text': content})}\n\n"
        except Exception as e:
            log.error("agent_error", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _diary_row_to_api(row: dict) -> dict:
    d = dict(row)
    ap = d.get("audio_path")
    if ap:
        d["audio_play_url"] = f"/media/audio/{Path(str(ap)).name}"
    else:
        d["audio_play_url"] = None
    return d


@app.get("/api/diary")
async def list_diary_entries(limit: int = 20):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM diary_entries ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    await db.close()
    return [_diary_row_to_api(dict(r)) for r in rows]


@app.get("/api/profile")
async def get_profile():
    db = await get_db()
    summaries = await db.execute_fetchall("SELECT * FROM profile_summaries")
    facts = await db.execute_fetchall(
        "SELECT * FROM profile_facts ORDER BY weight DESC LIMIT 200"
    )
    memories = await db.execute_fetchall(
        "SELECT * FROM memories ORDER BY timestamp DESC LIMIT 100"
    )
    diary_rows = await db.execute_fetchall(
        """SELECT id, timestamp, entry_type, summary, duration_s,
                  substr(raw_transcript, 1, 220) AS transcript_snippet,
                  audio_path
           FROM diary_entries ORDER BY timestamp DESC LIMIT 25"""
    )
    await db.close()

    def _diary_highlight(r: dict) -> dict:
        d = dict(r)
        ap = d.get("audio_path")
        if ap:
            d["audio_play_url"] = f"/media/audio/{Path(str(ap)).name}"
        else:
            d["audio_play_url"] = None
        return d

    return {
        "summaries": [dict(r) for r in summaries],
        "facts": [dict(r) for r in facts],
        "memories": [dict(r) for r in memories],
        "diary_highlights": [_diary_highlight(dict(r)) for r in diary_rows],
    }


@app.post("/api/profile/synthesize")
async def profile_synthesize():
    """Regenerate profile_summaries from recent diary text (local LLM)."""
    from backend.agent.profile_synthesize import synthesize_profile_from_diaries

    def run():
        updates = synthesize_profile_from_diaries(30)
        if not updates:
            return {"ok": True, "updated_domains": [], "message": "Sin texto de diario reciente."}
        apply_profile_summary_updates(updates)
        return {
            "ok": True,
            "updated_domains": list(updates.keys()),
            "message": f"Actualizados {len(updates)} dominios.",
        }

    return await asyncio.to_thread(run)


@app.get("/api/profile/memories-legacy")
async def list_memories_legacy(limit: int = 20):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    await db.close()
    return [dict(r) for r in rows]


@app.get("/api/debug/last")
async def debug_last():
    """Return debug info including counts, last entry, implementation status."""
    db = await get_db()
    last_entry = await db.execute_fetchall(
        "SELECT * FROM diary_entries ORDER BY id DESC LIMIT 1"
    )
    last_facts = await db.execute_fetchall(
        "SELECT * FROM profile_facts ORDER BY id DESC LIMIT 5"
    )
    entry_count = (await db.execute_fetchall("SELECT COUNT(*) as c FROM diary_entries"))[0]["c"]
    memory_count = (await db.execute_fetchall("SELECT COUNT(*) as c FROM memories"))[0]["c"]
    fact_count = (await db.execute_fetchall("SELECT COUNT(*) as c FROM profile_facts"))[0]["c"]

    # Semantic units count
    semantic_unit_count = 0
    try:
        result = await db.execute_fetchall("SELECT COUNT(*) as c FROM semantic_units")
        semantic_unit_count = result[0]["c"] if result else 0
    except Exception:
        pass  # Table may not exist yet

    # Last synthesis timestamp
    last_synthesis = await db.execute_fetchall(
        "SELECT MAX(last_updated) as ts FROM profile_summaries"
    )
    last_synthesis_at = last_synthesis[0]["ts"] if last_synthesis and last_synthesis[0]["ts"] else None

    await db.close()

    return {
        "counts": {
            "entries": entry_count,
            "memories": memory_count,
            "facts": fact_count,
            "semantic_units": semantic_unit_count,
        },
        "last_entry": dict(last_entry[0]) if last_entry else None,
        "recent_facts": [dict(r) for r in last_facts],
        "last_synthesis_at": last_synthesis_at,
        "implementation_status": {
            "audio_transcription": True,
            "diary_entries": True,
            "profile_facts": True,
            "memories": True,
            "semantic_decomposition": True,
            "chroma_ingestion": True,
            "semantic_retrieval": True,
            "profile_synthesis_manual": True,
            "profile_synthesis_auto": True,
            "question_engine": True,
            "self_profile_facts": True,
            "goals_domains": True,  # Phase 3a
            "goals_basic": True,    # Phase 3a
            "goals_hierarchy": True,  # Phase 3b graph V1
            "goals_okrs": False,    # Phase 3b
            "goals_intentions": False,  # Phase 3d
            "goals_time_blocks": True,  # Calendar engine V1
            "calendar_suggestion_inbox": True,
            "calendar_voice_commands": True,
            "structured_memory_archive": True,
            "work_module": False,
            "body_module": True,
            "finance_module": True,
        },
    }


@app.get("/api/questions/today")
async def get_questions_today():
    """Get today's discovery questions (generates if not exist)."""
    from backend.agent.question_engine import generate_daily_questions

    def run():
        return generate_daily_questions()

    questions = await asyncio.to_thread(run)
    return {"questions": questions}


@app.post("/api/questions/generate")
async def force_generate_questions():
    """Force regenerate today's questions (manual trigger)."""
    from backend.agent.question_engine import generate_daily_questions

    # Delete today's questions first
    db = await get_db()
    await db.execute(
        "DELETE FROM asked_questions WHERE date(timestamp) = date('now')"
    )
    await db.commit()
    await db.close()

    def run():
        return generate_daily_questions()

    questions = await asyncio.to_thread(run)
    return {"ok": True, "questions": questions}


@app.post("/api/questions/answer")
async def answer_question(
    question_id: int = Form(...),
    audio: UploadFile = File(None),
    text: str = Form(None),
):
    """Submit answer for a question (audio or text)."""
    from backend.audio.transcriber import save_audio, transcribe
    from backend.agent.semantic_decomposer import decompose_transcript
    from backend.agent.question_engine import calculate_richness_score

    transcript = ""

    # Process audio if provided
    if audio and audio.filename:
        audio_bytes = await audio.read()
        suffix = "." + (audio.filename or "audio.webm").split(".")[-1]
        audio_path = await asyncio.to_thread(save_audio, audio_bytes, "question", suffix)
        result = await asyncio.to_thread(transcribe, audio_path)
        transcript = result["text"]
    elif text:
        transcript = text.strip()
    else:
        return {"ok": False, "error": "Se requiere audio o texto"}

    if not transcript:
        return {"ok": False, "error": "No se detectó contenido"}

    # Run semantic decomposition
    decomposed_units = await asyncio.to_thread(
        decompose_transcript, transcript, None
    )
    unit_ids = [u.get("id") for u in decomposed_units if u.get("id")]

    # Store answer
    answer_id = await asyncio.to_thread(
        insert_question_answer,
        question_id,
        transcript,
        json.dumps(unit_ids),
    )

    # Calculate and update richness score
    richness = calculate_richness_score(transcript, len(decomposed_units))
    await asyncio.to_thread(update_question_richness, question_id, richness)

    log.info(
        "question_answered",
        question_id=question_id,
        answer_id=answer_id,
        semantic_units=len(decomposed_units),
        richness=richness,
    )

    return {
        "ok": True,
        "answer_id": answer_id,
        "transcript": transcript,
        "semantic_units": len(decomposed_units),
        "richness_score": richness,
    }


@app.get("/api/questions/stats")
async def questions_stats():
    """Return question effectiveness stats (richness scores by type)."""
    stats = await asyncio.to_thread(get_question_stats)
    return {"stats": stats}


@app.get("/api/diary/{entry_id}/conversation")
async def get_diary_conversation_endpoint(entry_id: int):
    """Get conversation thread for a diary entry."""
    conv = await asyncio.to_thread(get_diary_conversation, entry_id)
    if not conv:
        return {
            "diary_entry_id": entry_id,
            "messages": [],
            "message_count": 0,
            "can_continue": True,
            "max_messages": MAX_CONVERSATION_MESSAGES,
        }
    conv["max_messages"] = MAX_CONVERSATION_MESSAGES
    return conv


@app.post("/api/diary/{entry_id}/reply")
async def reply_to_diary_entry(
    entry_id: int,
    audio: UploadFile = File(None),
    text: str = Form(None),
):
    """Reply to a diary entry's conversation with text or audio. Nash will respond."""
    from backend.agent.graph import get_graph
    from backend.agent.semantic_decomposer import decompose_transcript
    from backend.audio.transcriber import save_audio, transcribe
    from backend.audio.ingest import audio_rel_path

    # Check if we can continue the conversation
    conv = await asyncio.to_thread(get_diary_conversation, entry_id)
    current_count = conv['message_count'] if conv else 0

    if current_count >= MAX_CONVERSATION_MESSAGES:
        return {
            "ok": False,
            "error": "Limite de conversacion alcanzado (maximo 11 mensajes).",
            "can_continue": False,
        }

    user_text = ""
    audio_path_rel = None

    # Process audio if provided
    if audio and audio.filename:
        audio_bytes = await audio.read()
        suffix = "." + (audio.filename or "audio.webm").split(".")[-1]
        audio_path = await asyncio.to_thread(save_audio, audio_bytes, "conversation", suffix)
        result = await asyncio.to_thread(transcribe, audio_path)
        user_text = result["text"]
        audio_path_rel = audio_rel_path(Path(audio_path).name)
        log.info("conversation_audio_transcribed", entry_id=entry_id, words=result["word_count"])
    elif text:
        user_text = text.strip()
    else:
        return {"ok": False, "error": "Se requiere audio o texto"}

    if not user_text:
        return {"ok": False, "error": "No se detecto contenido"}

    # Add user message with optional audio path
    result = await asyncio.to_thread(
        add_conversation_message, entry_id, 'user', user_text, audio_path_rel
    )
    if not result:
        return {"ok": False, "error": "No se pudo agregar mensaje."}

    # Build conversation context for agent
    context = await asyncio.to_thread(get_conversation_context, entry_id)

    agent_input = (
        f"{context}\n\n"
        f"[Nuevo mensaje del usuario]: {user_text}\n\n"
        "[Nota del sistema: Continua la conversacion de forma natural. "
        "Responde al nuevo mensaje del usuario considerando el contexto previo.]"
    )

    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": f"diary-conv-{entry_id}"}}
        input_msg = {"messages": [HumanMessage(content=agent_input)]}

        final_response = await asyncio.to_thread(graph.invoke, input_msg, config)
        messages = final_response.get("messages", [])

        nash_reply = ""
        if messages:
            ai_msg = messages[-1]
            nash_reply = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)

        # Add Nash's reply to conversation
        if nash_reply:
            result = await asyncio.to_thread(add_conversation_message, entry_id, 'nash', nash_reply)

            # Run semantic decomposition on the exchange
            combined_text = f"{user_text}\n\n{nash_reply}"
            await asyncio.to_thread(decompose_transcript, combined_text, entry_id)

            log.info("conversation_reply", entry_id=entry_id, message_count=result['message_count'])

        return {
            "ok": True,
            "transcript": user_text,
            "audio_url": f"/media/audio/{Path(audio_path_rel).name}" if audio_path_rel else None,
            "nash_reply": nash_reply,
            "conversation": result,
        }

    except Exception as e:
        log.error("conversation_error", entry_id=entry_id, error=str(e))
        return {"ok": False, "error": str(e)}


@app.post("/api/diary/regenerate-responses")
async def regenerate_diary_responses():
    """Regenerate Nash responses for diary entries that don't have one."""
    from backend.agent.graph import get_graph

    entries = await asyncio.to_thread(get_entries_without_response, 50)

    if not entries:
        return {"ok": True, "message": "No hay entradas sin respuesta.", "processed": 0}

    processed = 0
    errors = []

    for entry in entries:
        entry_id = entry["id"]
        transcript = entry["raw_transcript"]

        if not transcript or not transcript.strip():
            continue

        try:
            graph = get_graph()
            config = {"configurable": {"thread_id": f"regenerate-{entry_id}"}}

            # Create the agent input (similar to upload_audio)
            agent_input = (
                f"{transcript}\n\n[Nota del sistema: esta es una entrada de diario existente "
                f"(#{entry_id}). Responde como si el usuario te acabara de contar esto.]"
            )

            input_msg = {"messages": [HumanMessage(content=agent_input)]}
            final_response = await asyncio.to_thread(graph.invoke, input_msg, config)

            messages = final_response.get("messages", [])
            if messages:
                ai_msg = messages[-1]
                content = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
                await asyncio.to_thread(update_diary_nash_response, entry_id, content)
                processed += 1
                log.info("regenerated_response", entry_id=entry_id)

        except Exception as e:
            log.error("regenerate_error", entry_id=entry_id, error=str(e))
            errors.append({"entry_id": entry_id, "error": str(e)})

    return {
        "ok": True,
        "message": f"Procesadas {processed} entradas.",
        "processed": processed,
        "errors": errors,
    }


@app.get("/api/profile/self")
async def get_self_profile_endpoint():
    """Get biographical self-profile facts."""
    profile = await asyncio.to_thread(get_self_profile)
    if profile is None:
        # Create empty profile and return it
        profile = await asyncio.to_thread(upsert_self_profile, {})
    return {
        "profile": profile,
        "sections": list(SELF_PROFILE_SECTIONS.keys()),
        "unfilled_fields": await asyncio.to_thread(get_unfilled_profile_fields),
    }


@app.patch("/api/profile/self")
async def update_self_profile_endpoint(
    updates: dict,
):
    """Update biographical self-profile facts."""
    profile = await asyncio.to_thread(upsert_self_profile, updates)
    return {
        "ok": True,
        "profile": profile,
        "unfilled_fields": await asyncio.to_thread(get_unfilled_profile_fields),
    }


@app.get("/api/profile/self/sections")
async def get_self_profile_sections():
    """Get section definitions for self-profile UI."""
    return {
        "sections": SELF_PROFILE_SECTIONS,
    }


# =============================================
# Calendar + structured memories API
# =============================================

@app.get("/api/calendar/dashboard")
async def calendar_dashboard(week_start: str = None):
    try:
        return await asyncio.to_thread(build_calendar_dashboard, week_start)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/calendar/input")
async def calendar_input(
    text: str = Form(""),
    audio: UploadFile = File(None),
):
    """Interpret and execute a direct schedule command from text or local transcription."""
    from backend.audio.ingest import audio_rel_path
    from backend.audio.transcriber import save_audio, transcribe

    instruction = (text or "").strip()
    audio_path_rel = None
    input_mode = "text"
    if audio and audio.filename:
        audio_bytes = await audio.read()
        suffix = "." + (audio.filename or "audio.webm").split(".")[-1]
        audio_path = await asyncio.to_thread(save_audio, audio_bytes, "calendar", suffix)
        result = await asyncio.to_thread(transcribe, audio_path)
        transcript = (result.get("text") or "").strip()
        if transcript:
            instruction = f"{instruction}\n{transcript}".strip()
        audio_path_rel = audio_rel_path(Path(audio_path).name)
        input_mode = "audio"
    if not instruction:
        return {"ok": False, "error": "Se requiere audio o texto."}
    try:
        result = await asyncio.to_thread(
            process_schedule_input,
            instruction,
            input_mode=input_mode,
            audio_path=audio_path_rel,
        )
        return {"ok": True, "transcript": instruction, **result}
    except Exception as exc:
        log.error("calendar_input_failed", error=str(exc))
        return {"ok": False, "error": str(exc), "transcript": instruction}


@app.patch("/api/calendar/items/{item_id}")
async def patch_calendar_item(item_id: int, body: dict):
    item = await asyncio.to_thread(
        update_calendar_item,
        item_id,
        body,
        reason=body.get("reason") or "Edicion manual desde Agenda.",
    )
    if not item:
        return {"ok": False, "error": "Actividad no encontrada."}
    return {"ok": True, "item": item}


@app.post("/api/calendar/suggestions/{suggestion_id}/approve")
async def approve_schedule_suggestion(suggestion_id: int, body: dict = None):
    try:
        result = await asyncio.to_thread(approve_calendar_suggestion, suggestion_id, body or {})
        return {"ok": True, **result}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@app.delete("/api/calendar/suggestions/{suggestion_id}")
async def dismiss_schedule_suggestion(suggestion_id: int):
    try:
        suggestion = await asyncio.to_thread(reject_calendar_suggestion, suggestion_id)
        return {"ok": True, "suggestion": suggestion}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/calendar/sync")
async def sync_calendar_engines():
    counts = await asyncio.to_thread(sync_engine_suggestions)
    return {"ok": True, "sources": counts}


@app.get("/api/calendar/preferences")
async def calendar_preferences():
    return {"preferences": await asyncio.to_thread(get_schedule_preferences)}


@app.patch("/api/calendar/preferences")
async def patch_calendar_preferences(body: dict):
    preferences = await asyncio.to_thread(update_schedule_preferences, body)
    return {"ok": True, "preferences": preferences}


@app.get("/api/memories")
async def list_memories(limit: int = 500, search: str = None):
    memories = await asyncio.to_thread(get_memories, limit, search)
    return {"memories": memories}


@app.post("/api/memories")
async def create_memory(body: dict):
    if not str(body.get("title") or body.get("raw_transcript") or "").strip():
        return {"ok": False, "error": "El recuerdo necesita un titulo o contenido."}
    memory = await asyncio.to_thread(insert_structured_memory, body)
    return {"ok": True, "memory": memory}


@app.patch("/api/memories/{memory_id}")
async def patch_memory(memory_id: int, body: dict):
    memory = await asyncio.to_thread(update_memory, memory_id, body)
    if not memory:
        return {"ok": False, "error": "Recuerdo no encontrado o sin cambios validos."}
    return {"ok": True, "memory": memory}


@app.delete("/api/memories/{memory_id}")
async def remove_memory(memory_id: int):
    deleted = await asyncio.to_thread(delete_memory, memory_id)
    return {"ok": deleted}


# =============================================
# Phase 3: Goals + Domains API
# =============================================

@app.get("/api/goals/domains")
async def list_domains():
    """Get all life domains with their latest ratings."""
    domains = await asyncio.to_thread(get_life_domains)
    ratings = await asyncio.to_thread(get_latest_domain_ratings)

    # Merge ratings into domains
    for domain in domains:
        code = domain['code']
        if code in ratings:
            domain['latest_rating'] = ratings[code]['rating']
            domain['latest_notes'] = ratings[code]['notes']
            domain['rated_at'] = ratings[code]['rated_at']
        else:
            domain['latest_rating'] = None
            domain['latest_notes'] = None
            domain['rated_at'] = None

    return {"domains": domains}


@app.post("/api/goals/domains/rate")
async def rate_domains(body: dict):
    """Bulk rate multiple domains at once.
    Body: {"ratings": {"career": 7, "health": 8, ...}, "notes": "Optional note"}
    """
    ratings = body.get("ratings", {})
    notes = body.get("notes")

    if not ratings:
        return {"ok": False, "error": "No ratings provided"}

    # Validate ratings
    for code, rating in ratings.items():
        if not isinstance(rating, int) or not 1 <= rating <= 10:
            return {"ok": False, "error": f"Rating for {code} must be 1-10"}

    count = await asyncio.to_thread(bulk_insert_domain_ratings, ratings, notes)

    log.info("domains_rated", count=count, notes=bool(notes))
    return {"ok": True, "rated_count": count}


@app.get("/api/goals/domains/{domain_code}/history")
async def get_domain_history(domain_code: str, limit: int = 30):
    """Get rating history for a specific domain."""
    history = await asyncio.to_thread(get_domain_rating_history, domain_code, limit)
    return {"domain": domain_code, "history": history}


@app.get("/api/goals")
async def list_goals(
    status: str = None,
    domain: str = None,
    horizon: str = None,
    node_type: str = None,
    limit: int = 100,
):
    """List goals with optional filters."""
    goals = await asyncio.to_thread(get_goals, status, domain, horizon, node_type, limit)
    return {"goals": goals}


@app.post("/api/goals")
async def create_goal(body: dict):
    """Create a new life-graph node.
    Body: {
        "title": "required",
        "node_type": "goal" | "identity" | "system" | "action",
        "domain_code": "optional",
        "description": "optional",
        "why_matters": "optional - for self-concordance",
        "horizon": "quarterly" (required for goal, optional for system)",
        "start_date": "optional YYYY-MM-DD",
        "target_date": "optional YYYY-MM-DD",
        "cadence_text": "optional - only for system",
        "time_cost_min": "optional - only for action",
        "energy_cost": "optional 1-5 - only for action",
        "attention_cost": "optional 1-5 - only for action",
        "motivation_type": "optional: external | introjected | identified | intrinsic"
    }
    """
    title = body.get("title", "").strip()
    if not title:
        return {"ok": False, "error": "Title is required"}

    try:
        goal_id = await asyncio.to_thread(
            insert_goal,
            title=title,
            domain_code=body.get("domain_code"),
            domain_tags=body.get("domain_tags"),
            parent_goal_id=body.get("parent_goal_id"),
            node_type=body.get("node_type", "goal"),
            description=body.get("description"),
            why_matters=body.get("why_matters"),
            horizon=body.get("horizon", "quarterly"),
            start_date=body.get("start_date"),
            target_date=body.get("target_date"),
            cadence_text=body.get("cadence_text"),
            time_cost_min=body.get("time_cost_min"),
            energy_cost=body.get("energy_cost"),
            attention_cost=body.get("attention_cost"),
            motivation_type=body.get("motivation_type"),
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    goal = await asyncio.to_thread(get_goal_by_id, goal_id)
    log.info("goal_created", goal_id=goal_id, title=title)
    return {"ok": True, "goal": goal}


@app.get("/api/goals/summary")
async def goals_summary():
    """Get summary stats for goals."""
    summary = await asyncio.to_thread(get_goals_summary)
    return summary


@app.get("/api/goals/graph")
async def get_goal_graph(status: str = None):
    """Get goals as graph data (nodes + edges)."""
    graph = await asyncio.to_thread(get_goals_graph, status)
    return graph


@app.post("/api/goals/relations")
async def create_goal_relation(body: dict):
    """Create a relation edge between goals."""
    source_goal_id = body.get("source_goal_id")
    target_goal_id = body.get("target_goal_id")
    relation_type = body.get("relation_type", "related")

    if not isinstance(source_goal_id, int) or not isinstance(target_goal_id, int):
        return {"ok": False, "error": "source_goal_id y target_goal_id deben ser enteros."}

    try:
        relation = await asyncio.to_thread(
            insert_goal_relation,
            source_goal_id,
            target_goal_id,
            relation_type,
            body.get("note"),
            body.get("weight"),
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True, "relation": relation}


@app.delete("/api/goals/relations/{relation_id}")
async def remove_goal_relation(relation_id: int):
    """Delete a relation edge between goals."""
    deleted = await asyncio.to_thread(delete_goal_relation, relation_id)
    if not deleted:
        return {"ok": False, "error": "Relacion no encontrada"}
    return {"ok": True}


@app.get("/api/goals/{goal_id}")
async def get_single_goal(goal_id: int):
    """Get a single goal by ID."""
    goal = await asyncio.to_thread(get_goal_by_id, goal_id)
    if not goal:
        return {"ok": False, "error": "Goal not found"}
    return {"goal": goal}


@app.patch("/api/goals/{goal_id}")
async def update_single_goal(goal_id: int, body: dict):
    """Update a life-graph node.
    Body can include: node_type, title, description, why_matters, domain_code, horizon,
    start_date, target_date, cadence_text, action cost fields, status, progress_pct, motivation_type
    """
    try:
        goal = await asyncio.to_thread(update_goal, goal_id, body)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not goal:
        return {"ok": False, "error": "Goal not found"}

    log.info("goal_updated", goal_id=goal_id, updates=list(body.keys()))
    return {"ok": True, "goal": goal}


@app.delete("/api/goals/{goal_id}")
async def delete_single_goal(goal_id: int):
    """Delete a goal."""
    deleted = await asyncio.to_thread(delete_goal, goal_id)
    if not deleted:
        return {"ok": False, "error": "Goal not found"}

    log.info("goal_deleted", goal_id=goal_id)
    return {"ok": True}


# =============================================
# Goal Discovery API
# =============================================

@app.post("/api/goals/discovery/start")
async def start_goal_discovery():
    """Start a new goal discovery session."""
    from backend.db.schema import create_discovery_session, get_active_discovery_session
    from backend.agent.profile import build_profile_context

    # Check for existing active session
    existing = await asyncio.to_thread(get_active_discovery_session)
    if existing:
        log.info("discovery_session_existing", session_id=existing['id'])
        return {"ok": True, "session": existing, "resumed": True}

    # Create new session with context snapshot
    context = await asyncio.to_thread(build_profile_context)
    session_id = await asyncio.to_thread(create_discovery_session, context)
    session = await asyncio.to_thread(
        lambda: __import__('backend.db.schema', fromlist=['get_discovery_session']).get_discovery_session(session_id)
    )

    log.info("discovery_session_started", session_id=session_id)
    return {"ok": True, "session": session, "resumed": False}


@app.get("/api/goals/discovery/active")
async def get_active_discovery():
    """Get the current active discovery session if any."""
    from backend.db.schema import get_active_discovery_session

    session = await asyncio.to_thread(get_active_discovery_session)
    if not session:
        return {"ok": False, "session": None}

    return {"ok": True, "session": session}


@app.get("/api/goals/discovery/{session_id}")
async def get_discovery_session_by_id(session_id: int):
    """Get a specific discovery session."""
    from backend.db.schema import get_discovery_session

    session = await asyncio.to_thread(get_discovery_session, session_id)
    if not session:
        return {"ok": False, "error": "Session not found"}

    return {"ok": True, "session": session}


@app.post("/api/goals/discovery/{session_id}/chat")
async def chat_goal_discovery(
    session_id: int,
    text: str = Form(None),
    audio: UploadFile = File(None),
):
    """Send a message in a goal discovery conversation (text or audio)."""
    from backend.agent.goal_discovery import chat_discovery

    # Handle audio input
    if audio:
        from backend.audio.transcriber import save_audio, transcribe

        audio_bytes = await audio.read()
        suffix = "." + (audio.filename or "audio.webm").split(".")[-1]
        audio_path = await asyncio.to_thread(save_audio, audio_bytes, "discovery", suffix)
        result = await asyncio.to_thread(transcribe, audio_path)
        user_message = result["text"]

        if not user_message.strip():
            return {"ok": False, "error": "No se detectó habla en el audio."}

        log.info("discovery_audio_transcribed", session_id=session_id, words=result["word_count"])
    elif text:
        user_message = text
    else:
        return {"ok": False, "error": "No message provided (text or audio)"}

    try:
        result = await chat_discovery(session_id, user_message)
        return {
            "ok": True,
            "user_message": user_message,
            "response": result['response'],
            "extracted_goals": result['extracted_goals'],
            "extracted_relations": result.get('extracted_relations', []),
            "session": result['session'],
        }
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        log.error("discovery_chat_error", error=str(e), session_id=session_id)
        return {"ok": False, "error": "Error processing message"}


@app.post("/api/goals/discovery/{session_id}/confirm")
async def confirm_discovery_goal(session_id: int):
    """Confirm and save an extracted goal."""
    from backend.agent.goal_discovery import confirm_extracted_goal
    from backend.db.schema import get_discovery_session

    body = await app.state._request.json() if hasattr(app.state, '_request') else {}

    # Get request body manually
    from starlette.requests import Request
    import json as json_module

    # This endpoint needs the goal data in body, use a workaround
    return {"ok": False, "error": "Use POST with JSON body containing goal data"}


@app.post("/api/goals/discovery/{session_id}/confirm-goal")
async def confirm_discovery_goal_with_body(
    session_id: int,
    goal_data: dict = None,
):
    """Confirm and save an extracted goal (with JSON body)."""
    from backend.agent.goal_discovery import confirm_extracted_goal

    # This will be called via fetch with JSON body
    return {"ok": False, "error": "Use request body"}


@app.post("/api/goals/discovery/confirm-goal")
async def confirm_goal_from_discovery():
    """Confirm and save a goal from discovery session."""
    from backend.agent.goal_discovery import confirm_extracted_goal
    from starlette.requests import Request
    from fastapi import Request as FastAPIRequest

    # We need to handle this differently - use a separate endpoint
    return {"ok": False, "error": "Use /api/goals/discovery/save endpoint"}


@app.post("/api/goals/discovery/save")
async def save_discovered_goal(
    session_id: int = Form(...),
    goal_json: str = Form(...),
):
    """Save a goal discovered in a session."""
    from backend.agent.goal_discovery import confirm_extracted_goal
    import json as json_module

    try:
        goal_data = json_module.loads(goal_json)
    except json_module.JSONDecodeError:
        return {"ok": False, "error": "Invalid goal JSON"}

    try:
        saved_goal = await asyncio.to_thread(confirm_extracted_goal, session_id, goal_data)
        return {"ok": True, "goal": saved_goal}
    except Exception as e:
        log.error("goal_save_error", error=str(e))
        return {"ok": False, "error": str(e)}


@app.post("/api/goals/discovery/{session_id}/end")
async def end_goal_discovery(session_id: int):
    """End a discovery session."""
    from backend.agent.goal_discovery import end_discovery_session

    session = await asyncio.to_thread(end_discovery_session, session_id)
    if not session:
        return {"ok": False, "error": "Session not found"}

    log.info("discovery_session_ended", session_id=session_id, goals_confirmed=session.get('goals_confirmed', 0))
    return {"ok": True, "session": session}


# =============================================
# Phase 5: Nutrition, Exercise, Finance API
# =============================================

@app.post("/api/{module}/discovery/start")
async def start_module_discovery(module: str):
    """Start or resume a module discovery session (nutrition/exercise/finance)."""
    from backend.agent.profile import build_profile_context

    if module not in MODULE_NAMES_ES:
        return {"ok": False, "error": "Modulo no soportado."}

    existing = await asyncio.to_thread(get_active_module_discovery, module)
    if existing:
        log.info("module_discovery_existing", module=module, session_id=existing["id"])
        return {"ok": True, "session": existing, "resumed": True}

    context = await asyncio.to_thread(build_profile_context)
    session_id = await asyncio.to_thread(create_module_discovery_session, module, context)
    session = await asyncio.to_thread(get_module_discovery_session, session_id)

    log.info("module_discovery_started", module=module, session_id=session_id)
    return {"ok": True, "session": session, "resumed": False}


@app.get("/api/{module}/discovery/active")
async def get_active_module_discovery_endpoint(module: str):
    """Get active discovery session for a module."""
    if module not in MODULE_NAMES_ES:
        return {"ok": False, "error": "Modulo no soportado.", "session": None}

    session = await asyncio.to_thread(get_active_module_discovery, module)
    return {"ok": bool(session), "session": session}


@app.get("/api/{module}/discovery/{session_id}")
async def get_module_discovery_session_endpoint(module: str, session_id: int):
    """Get a specific module discovery session."""
    if module not in MODULE_NAMES_ES:
        return {"ok": False, "error": "Modulo no soportado."}

    session = await asyncio.to_thread(get_module_discovery_session, session_id)
    if not session:
        return {"ok": False, "error": "Sesion no encontrada."}
    if session.get("module") != module:
        return {"ok": False, "error": "Sesion no corresponde al modulo solicitado."}

    return {"ok": True, "session": session}


@app.post("/api/{module}/discovery/{session_id}/chat")
async def chat_module_discovery_endpoint(
    module: str,
    session_id: int,
    text: str = Form(None),
    audio: UploadFile = File(None),
):
    """Send a message in module discovery conversation (text or audio)."""
    from backend.agent.module_discovery import chat_module_discovery

    if module not in MODULE_NAMES_ES:
        return {"ok": False, "error": "Modulo no soportado."}

    session = await asyncio.to_thread(get_module_discovery_session, session_id)
    if not session:
        return {"ok": False, "error": "Sesion no encontrada."}
    if session.get("module") != module:
        return {"ok": False, "error": "Sesion no corresponde al modulo solicitado."}

    if audio:
        from backend.audio.transcriber import save_audio, transcribe

        audio_bytes = await audio.read()
        suffix = "." + (audio.filename or "audio.webm").split(".")[-1]
        audio_path = await asyncio.to_thread(save_audio, audio_bytes, f"{module}_discovery", suffix)
        result = await asyncio.to_thread(transcribe, audio_path)
        user_message = (result.get("text") or "").strip()
        if not user_message:
            return {"ok": False, "error": "No se detecto habla en el audio."}
    elif text and text.strip():
        user_message = text.strip()
    else:
        return {"ok": False, "error": "No message provided (text or audio)."}

    try:
        result = await chat_module_discovery(session_id, user_message)
        return {
            "ok": True,
            "user_message": user_message,
            "response": result["response"],
            "extracted_data": result["extracted_data"],
            "profile_updated": result["profile_updated"],
            "session": result["session"],
        }
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        log.error("module_discovery_endpoint_error", module=module, session_id=session_id, error=str(e))
        return {"ok": False, "error": "Error procesando el mensaje."}


@app.post("/api/{module}/discovery/{session_id}/end")
async def end_module_discovery_endpoint(module: str, session_id: int, summary: str = Form(None)):
    """End a module discovery session."""
    from backend.agent.module_discovery import end_module_discovery_session

    if module not in MODULE_NAMES_ES:
        return {"ok": False, "error": "Modulo no soportado."}

    session = await asyncio.to_thread(get_module_discovery_session, session_id)
    if not session:
        return {"ok": False, "error": "Sesion no encontrada."}
    if session.get("module") != module:
        return {"ok": False, "error": "Sesion no corresponde al modulo solicitado."}

    updated = await asyncio.to_thread(end_module_discovery_session, session_id, summary)
    if not updated:
        return {"ok": False, "error": "No se pudo cerrar la sesion."}

    log.info("module_discovery_ended", module=module, session_id=session_id)
    return {"ok": True, "session": updated}


@app.get("/api/nutrition/profile")
async def get_nutrition_profile_endpoint():
    """Get nutrition profile + today's totals."""
    profile = await asyncio.to_thread(get_nutrition_profile)
    totals = await asyncio.to_thread(get_nutrition_daily_totals)
    return {"profile": profile, "daily_totals": totals}


@app.patch("/api/nutrition/profile")
async def update_nutrition_profile_endpoint(updates: dict):
    """Create/update nutrition profile."""
    profile = await asyncio.to_thread(upsert_nutrition_profile, updates)
    totals = await asyncio.to_thread(get_nutrition_daily_totals)
    return {"ok": True, "profile": profile, "daily_totals": totals}


@app.get("/api/nutrition/entries")
async def list_nutrition_entries(today: int = 1, limit: int = 50):
    """List food entries (today by default)."""
    if today == 1:
        entries = await asyncio.to_thread(get_food_entries_today)
    else:
        db = await get_db()
        rows = await db.execute_fetchall(
            "SELECT * FROM food_entries ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        await db.close()
        entries = [dict(r) for r in rows]
    totals = await asyncio.to_thread(get_nutrition_daily_totals)
    return {"entries": entries, "daily_totals": totals}


@app.post("/api/nutrition/entries")
async def create_nutrition_entry(
    description: str = Form(""),
    meal_type: str = Form("snack"),
    weight_g: str = Form(""),
    protein_g: str = Form(""),
    carbs_g: str = Form(""),
    fat_g: str = Form(""),
    calories: str = Form(""),
    notes: str = Form(""),
    audio: UploadFile = File(None),
):
    """Create a food entry from text and optional audio."""
    from backend.audio.ingest import audio_rel_path
    from backend.audio.transcriber import save_audio, transcribe

    def parse_float(value: str) -> float | None:
        try:
            return float(value) if value and value.strip() else None
        except ValueError:
            return None

    audio_path_rel = None
    entry_description = (description or "").strip()

    if audio and audio.filename:
        audio_bytes = await audio.read()
        suffix = "." + (audio.filename or "audio.webm").split(".")[-1]
        audio_path = await asyncio.to_thread(save_audio, audio_bytes, "nutrition", suffix)
        result = await asyncio.to_thread(transcribe, audio_path)
        transcript = (result.get("text") or "").strip()
        if transcript and not entry_description:
            entry_description = transcript
        audio_path_rel = audio_rel_path(Path(audio_path).name)

    if not entry_description:
        return {"ok": False, "error": "Descripcion o audio requerido."}

    allowed_meals = {"breakfast", "lunch", "dinner", "snack"}
    entry_meal_type = meal_type if meal_type in allowed_meals else "snack"

    protein_val = parse_float(protein_g)
    carbs_val = parse_float(carbs_g)
    fat_val = parse_float(fat_g)
    calories_val = parse_float(calories)
    weight_val = parse_float(weight_g)

    is_estimated = not all(v is not None for v in [protein_val, carbs_val, fat_val, calories_val])

    entry_id = await asyncio.to_thread(
        insert_food_entry,
        description=entry_description,
        meal_type=entry_meal_type,
        weight_g=weight_val,
        protein_g=protein_val,
        carbs_g=carbs_val,
        fat_g=fat_val,
        calories=calories_val,
        is_estimated=is_estimated,
        audio_path=audio_path_rel,
        notes=(notes or "").strip() or None,
    )

    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM food_entries WHERE id = ?", (entry_id,))
    await db.close()
    entry = dict(rows[0]) if rows else None

    totals = await asyncio.to_thread(get_nutrition_daily_totals)
    return {"ok": True, "entry": entry, "daily_totals": totals}


@app.get("/api/exercise/profile")
async def get_exercise_profile_endpoint():
    """Get exercise profile."""
    profile = await asyncio.to_thread(get_exercise_profile)
    return {"profile": profile}


@app.patch("/api/exercise/profile")
async def update_exercise_profile_endpoint(updates: dict):
    """Create/update exercise profile."""
    profile = await asyncio.to_thread(upsert_exercise_profile, updates)
    return {"ok": True, "profile": profile}


@app.get("/api/exercise/dashboard")
async def get_exercise_dashboard_endpoint():
    """Get the full workout engine dashboard."""
    dashboard = await asyncio.to_thread(build_exercise_dashboard)
    return dashboard


@app.post("/api/exercise/plan")
async def generate_exercise_plan_endpoint(body: dict):
    """Generate an adherence-first workout plan."""
    plan = await asyncio.to_thread(
        generate_workout_plan,
        location=body.get("location"),
        energy_level=body.get("energy_level"),
        available_time_min=body.get("available_time_min"),
        desired_mode=body.get("desired_mode"),
    )
    return {"ok": True, "plan": plan}


@app.get("/api/exercise/equipment")
async def list_exercise_equipment_endpoint(location: str = None):
    """List exercise equipment by location."""
    items = await asyncio.to_thread(list_exercise_equipment, location)
    return {"items": items}


@app.post("/api/exercise/equipment")
async def create_exercise_equipment_endpoint(body: dict):
    """Create an equipment item."""
    location = (body.get("location") or "").strip()
    category = (body.get("category") or "").strip()
    label = (body.get("label") or "").strip()
    if location not in {"home", "gym"}:
        return {"ok": False, "error": "location must be home or gym"}
    if not category:
        return {"ok": False, "error": "category is required"}
    if not label:
        return {"ok": False, "error": "label is required"}

    item_id = await asyncio.to_thread(
        insert_exercise_equipment,
        location=location,
        category=category,
        label=label,
        max_load_kg=body.get("max_load_kg"),
        quantity=body.get("quantity"),
        notes=body.get("notes"),
    )
    items = await asyncio.to_thread(list_exercise_equipment, location)
    created = next((item for item in items if item.get("id") == item_id), None)
    return {"ok": True, "item": created}


@app.delete("/api/exercise/equipment/{item_id}")
async def delete_exercise_equipment_endpoint(item_id: int):
    """Remove an equipment item."""
    await asyncio.to_thread(delete_exercise_equipment, item_id)
    return {"ok": True}


@app.get("/api/exercise/measurements")
async def list_exercise_measurements_endpoint(limit: int = 12):
    """List body measurement snapshots."""
    measurements = await asyncio.to_thread(get_body_measurement_snapshots, limit)
    return {"measurements": measurements}


@app.post("/api/exercise/measurements")
async def create_exercise_measurement_endpoint(body: dict):
    """Create a body measurement snapshot."""
    snapshot = await asyncio.to_thread(insert_body_measurement_snapshot, body)
    return {"ok": True, "measurement": snapshot}


@app.get("/api/exercise/records")
async def list_exercise_records_endpoint(limit: int = 20):
    """List recent exercise personal records."""
    records = await asyncio.to_thread(get_personal_records, limit)
    return {"records": records}


@app.get("/api/exercise/templates")
async def list_exercise_templates(level: str = None):
    """List workout templates."""
    templates = await asyncio.to_thread(get_workout_templates, level)
    return {"templates": templates}


@app.post("/api/exercise/templates")
async def create_exercise_template(body: dict):
    """Create workout template."""
    name = (body.get("name") or "").strip()
    level = (body.get("level") or "").strip()
    exercises = body.get("exercises")

    if not name:
        return {"ok": False, "error": "name is required"}
    if level not in {"minimum", "optimal"}:
        return {"ok": False, "error": "level must be minimum or optimal"}
    if not isinstance(exercises, list) or not exercises:
        return {"ok": False, "error": "exercises must be a non-empty list"}

    template_id = await asyncio.to_thread(
        insert_workout_template,
        name=name,
        level=level,
        exercises_json=json.dumps(exercises),
        workout_type=body.get("workout_type"),
        estimated_duration_min=body.get("estimated_duration_min"),
    )

    templates = await asyncio.to_thread(get_workout_templates, level)
    created = next((t for t in templates if t.get("id") == template_id), None)
    return {"ok": True, "template": created}


@app.get("/api/exercise/sessions")
async def list_exercise_sessions(limit: int = 30):
    """List recent workout sessions."""
    sessions = await asyncio.to_thread(get_workout_sessions, limit)
    return {"sessions": sessions}


@app.post("/api/exercise/sessions")
async def create_exercise_session(body: dict):
    """Create workout session."""
    level = (body.get("level") or "").strip()
    if level not in {"minimum", "optimal"}:
        return {"ok": False, "error": "level must be minimum or optimal"}

    actual_location = body.get("actual_location")
    planned_location = body.get("planned_location")
    if actual_location not in {None, "home", "gym"}:
        return {"ok": False, "error": "actual_location must be home or gym"}
    if planned_location not in {None, "home", "gym"}:
        return {"ok": False, "error": "planned_location must be home or gym"}

    date = body.get("date") or datetime.now().strftime("%Y-%m-%d")
    session_id = await asyncio.to_thread(
        insert_workout_session,
        date=date,
        level=level,
        template_id=body.get("template_id"),
        exercises_json=json.dumps(body.get("exercises")) if isinstance(body.get("exercises"), list) else body.get("exercises_json"),
        notes=body.get("notes"),
        energy_level=body.get("energy_level"),
        focus_code=body.get("focus_code"),
        planned_location=planned_location,
        actual_location=actual_location,
        duration_min=body.get("duration_min"),
        session_rpe=body.get("session_rpe"),
        fallback_used=bool(body.get("fallback_used")),
        plan_source=body.get("plan_source"),
        completed=body.get("completed"),
        exercise_logs=body.get("exercise_logs") if isinstance(body.get("exercise_logs"), list) else None,
    )
    sessions = await asyncio.to_thread(get_workout_sessions, 20)
    created = next((session for session in sessions if session.get("id") == session_id), None)
    return {"ok": True, "session": created}


@app.get("/api/finance/profile")
async def get_finance_profile_endpoint():
    """Get finance profile."""
    profile = await asyncio.to_thread(get_finance_profile)
    return {"profile": profile}


@app.patch("/api/finance/profile")
async def update_finance_profile_endpoint(updates: dict):
    """Create/update finance profile."""
    profile = await asyncio.to_thread(upsert_finance_profile, updates)
    return {"ok": True, "profile": profile}


@app.get("/api/finance/categories")
async def list_finance_categories():
    """List expense categories."""
    categories = await asyncio.to_thread(get_expense_categories)
    return {"categories": categories}


@app.get("/api/finance/expenses")
async def list_finance_expenses(limit: int = 50, month: str = None):
    """List expenses with optional month filter (YYYY-MM)."""
    expenses = await asyncio.to_thread(get_expenses, limit, month)
    return {"expenses": expenses}


@app.post("/api/finance/expenses")
async def create_finance_expense(body: dict):
    """Create an expense entry."""
    description = (body.get("description") or "").strip()
    amount = body.get("amount")
    if not description:
        return {"ok": False, "error": "description is required"}
    if amount is None:
        return {"ok": False, "error": "amount is required"}

    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        return {"ok": False, "error": "amount must be numeric"}

    expense_id = await asyncio.to_thread(
        insert_expense,
        description=description,
        amount=amount_value,
        category_code=body.get("category_code"),
        is_recurring=bool(body.get("is_recurring")),
        notes=body.get("notes"),
        payment_method=body.get("payment_method"),
        timestamp=body.get("timestamp"),
    )

    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT e.*, ec.code as category_code, ec.name_es as category_name, ec.icon as category_icon
           FROM expenses e
           LEFT JOIN expense_categories ec ON ec.id = e.category_id
           WHERE e.id = ?""",
        (expense_id,),
    )
    await db.close()

    summary = await asyncio.to_thread(get_monthly_expense_summary)
    return {"ok": True, "expense": dict(rows[0]) if rows else None, "summary": summary}


@app.get("/api/finance/summary")
async def finance_summary(month: str = None):
    """Get monthly finance summary."""
    summary = await asyncio.to_thread(get_monthly_expense_summary, month)
    return {"summary": summary}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "nash"}
