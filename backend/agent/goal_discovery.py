"""
Goal Discovery Conversation Engine

Typed life-graph discovery for Metas.
"""

import json
import re
import unicodedata

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agent.profile import build_profile_context
from backend.db.schema import (
    add_discovery_message,
    get_discovery_session,
    get_domain_ratings_for_context,
    get_goals_for_context,
    insert_goal,
    update_discovery_session,
)
from backend.llm import (
    content_to_text,
    get_chat_model,
    restore_local_aliases,
    sanitize_text_for_remote_llm,
    should_redact_identity,
)

log = structlog.get_logger()

DISCOVERY_MODEL_CTX = 16384

_NODE_START_PATTERN = re.compile(r"(?im)^\s*\[\s*NODO_IDENTIFICADO\s*\]\s*$")
_NODE_END_PATTERN = re.compile(r"(?im)^\s*\[\s*/\s*NODO_IDENTIFICADO\s*\]\s*$")
_NODE_FIELD_LINE_PATTERN = re.compile(
    r"(?im)^\s*(tipo|titulo|descripcion|dominio|horizonte|fecha_inicio|fecha_objetivo|cadencia|costo_tiempo_min|costo_energia|costo_atencion|importancia|dificultad|compromiso|motivacion|por_que_importa|mi_opinion)\s*:"
)

_RELATION_START_PATTERN = re.compile(r"(?im)^\s*\[\s*RELACION_IDENTIFICADA\s*\]\s*$")
_RELATION_END_PATTERN = re.compile(r"(?im)^\s*\[\s*/\s*RELACION_IDENTIFICADA\s*\]\s*$")
_RELATION_FIELD_LINE_PATTERN = re.compile(
    r"(?im)^\s*(origen|destino|tipo|nota)\s*:"
)

_LEGACY_GOAL_START_PATTERN = re.compile(
    r"(?im)^\s*(?:\[\s*META_IDENTIFICADA\s*\]|\*{0,2}\s*META\s+IDENTIFICADA(?:\s+\d+)?\s*\*{0,2})\s*$"
)
_LEGACY_GOAL_END_PATTERN = re.compile(r"(?im)^\s*\[\s*/\s*META_IDENTIFICADA\s*\]\s*$")
_LEGACY_GOAL_FIELD_LINE_PATTERN = re.compile(
    r"(?im)^\s*\*{0,2}(titulo|descripcion|dominio|horizonte|fecha_inicio|fecha_objetivo|importancia|dificultad|compromiso|motivacion|por_que_importa|mi_opinion)\*{0,2}\s*:"
)

VALID_NODE_TYPES = {"identity", "goal", "system", "action"}
VALID_HORIZONS = {"life", "annual", "quarterly", "monthly", "weekly"}
VALID_MOTIVATIONS = {"external", "introjected", "identified", "intrinsic"}
VALID_RELATION_TYPES = {
    "related",
    "supports",
    "depends_on",
    "conflicts_with",
    "synergy",
    "blocks",
    "drives",
    "requires",
    "reinforces",
    "costs",
}
VALID_BASE_DOMAINS = {
    "career",
    "finance",
    "health",
    "relationships",
    "personal_growth",
    "fun_recreation",
    "environment",
    "contribution",
}

NODE_TYPE_ALIASES = {
    "identity": "identity",
    "identidad": "identity",
    "goal": "goal",
    "meta": "goal",
    "super_goal": "goal",
    "supergoal": "goal",
    "sub_goal": "goal",
    "subgoal": "goal",
    "sub_meta": "goal",
    "submeta": "goal",
    "system": "system",
    "sistema": "system",
    "process": "system",
    "proceso": "system",
    "action": "action",
    "accion": "action",
    "task": "action",
    "tarea": "action",
}

HORIZON_ALIASES = {
    "vida": "life",
    "anual": "annual",
    "trimestral": "quarterly",
    "mensual": "monthly",
    "semanal": "weekly",
}

MOTIVATION_ALIASES = {
    "externa": "external",
    "introyectada": "introjected",
    "identificada": "identified",
    "intrinseca": "intrinsic",
    "intrínseca": "intrinsic",
}

RELATION_TYPE_ALIASES = {
    "related": "related",
    "relacionada": "related",
    "relacionado": "related",
    "supports": "supports",
    "apoya": "supports",
    "supports_to": "supports",
    "depends_on": "depends_on",
    "depende_de": "depends_on",
    "dependency": "depends_on",
    "conflicts_with": "conflicts_with",
    "conflicto": "conflicts_with",
    "conflict": "conflicts_with",
    "synergy": "synergy",
    "sinergia": "synergy",
    "blocks": "blocks",
    "bloquea": "blocks",
    "drives": "drives",
    "impulsa": "drives",
    "genera": "drives",
    "requires": "requires",
    "requiere": "requires",
    "reinforces": "reinforces",
    "refuerza": "reinforces",
    "costs": "costs",
    "cuesta": "costs",
}

GOAL_DISCOVERY_PROMPT = """\
Eres Nash en MODO LIFE GRAPH.
Tu trabajo es ayudar a la persona usuaria a construir una primera versión de su sistema de vida como un grafo editable.

CAPAS DEL GRAFO:
- identity: rasgos o identidades deseadas ("calmo", "disciplinado", "ingeniero creativo")
- goal: estado deseado o resultado
- system: proceso repetible que empuja metas
- action: acción concreta, ejecutable, de una sola vez

REGLAS DE MODELADO:
- "super-goal" y "sub-goal" NO son tipos separados. Si algo es una meta grande o una sub-meta, igual se guarda como tipo goal.
- dominio SIEMPRE es metadata/tags, nunca un nodo aparte.
- horizonte aplica así:
  - identity: sin horizonte
  - goal: requiere horizonte
  - system: horizonte opcional
  - action: sin horizonte
- cadencia solo aplica a system
- costo_tiempo_min, costo_energia y costo_atencion solo aplican a action
- Si una acción, sistema, meta o identidad ya está lo bastante clara, créala ahora. No esperes perfección.

TIPOS DE RELACIÓN CANÓNICOS:
- drives: progreso en origen impulsa destino
- requires: origen requiere destino o depende estructuralmente de destino
- reinforces: progreso en uno ayuda al otro
- conflicts_with: hay tensión o conflicto real
- costs: el origen consume tiempo/energía/atención del destino o del sistema general

CONTEXTO DE LA PERSONA USUARIA:
{profile_context}

SATISFACCIÓN POR DOMINIO:
{domain_ratings}

GRAFO ACTUAL:
{existing_goals}

HISTORIAL DE ESTA CONVERSACIÓN:
{conversation_history}

MODO DE RESPUESTA:
1. Guía a la persona usuaria con pasos cortos. Haz como máximo UNA pregunta breve por turno.
2. Prioriza proponer un borrador V1 utilizable.
3. Si la persona usuaria pide crear 2 o 3 nodos, créalos en el mismo turno.
4. Si puedes inferir una relación útil entre nodos mencionados, declárala en el mismo turno.
5. Responde SIEMPRE en español.
6. No simules conversaciones falsas ni uses etiquetas [Usuario] o [Nash].

FORMATO ESTRICTO DE EXTRACCIÓN:
- Cada nodo debe usar EXACTAMENTE:
  [NODO_IDENTIFICADO]
  ...
  [/NODO_IDENTIFICADO]
- Cada relación debe usar EXACTAMENTE:
  [RELACION_IDENTIFICADA]
  ...
  [/RELACION_IDENTIFICADA]
- No uses formatos alternativos.
- Si no respetas estos tags exactos, el sistema no podrá guardar el nodo o la relación.

FORMATO DE NODO:
[NODO_IDENTIFICADO]
tipo: identity | goal | system | action
titulo: título conciso
descripcion: descripción clara
dominio: tags separadas por | (incluye al menos un dominio base cuando aplique: career|finance|health|relationships|personal_growth|fun_recreation|environment|contribution)
horizonte: life | annual | quarterly | monthly | weekly | vacio
fecha_inicio: YYYY-MM-DD o vacio
fecha_objetivo: YYYY-MM-DD o vacio
cadencia: texto breve o vacio
costo_tiempo_min: numero o vacio
costo_energia: numero 1-5 o vacio
costo_atencion: numero 1-5 o vacio
importancia: entero 1-10 o vacio
dificultad: entero 1-10 o vacio
compromiso: entero 1-10 o vacio
motivacion: external | introjected | identified | intrinsic | vacio
por_que_importa: por qué importa
mi_opinion: tu análisis honesto
[/NODO_IDENTIFICADO]

FORMATO DE RELACIÓN:
[RELACION_IDENTIFICADA]
origen: título exacto del nodo origen
destino: título exacto del nodo destino
tipo: drives | requires | reinforces | conflicts_with | costs | related | supports | depends_on | synergy | blocks
nota: explicación breve o vacio
[/RELACION_IDENTIFICADA]

REGLAS EXTRA:
- Cuando el usuario ya haya dicho "créala", "agrega", "sepáralas", "quiero que traces esas metas", ejecuta y devuelve bloques.
- Si el usuario está empezando desde cero, ayúdalo a construir primero 1 identidad, 1 goal y 1 system si hay suficiente señal.
- Si una goal no tiene horizonte claro, elige uno razonable y luego se podrá editar.
- Si una action no tiene costos claros, déjalos vacíos.
- Mantén cada respuesta natural, concreta y útil, idealmente entre 80 y 180 palabras sin contar bloques.
"""


def _normalize_field_key(key: str) -> str:
    normalized = key.strip().lower().strip("*` ")
    normalized = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    return normalized


def _extract_segments(
    response: str,
    start_pattern: re.Pattern,
    end_pattern: re.Pattern,
    field_line_pattern: re.Pattern,
    include_spans: bool = False,
):
    starts = list(start_pattern.finditer(response))
    if not starts:
        return []

    segments: list[tuple[int, int, str]] = []
    for idx, start_match in enumerate(starts):
        body_start = start_match.end()
        next_start_pos = starts[idx + 1].start() if idx + 1 < len(starts) else len(response)
        end_match = end_pattern.search(response, body_start, next_start_pos)

        if end_match:
            segment_end = end_match.end()
            body_end = end_match.start()
        else:
            raw_block = response[body_start:next_start_pos]
            field_matches = list(field_line_pattern.finditer(raw_block))
            if field_matches:
                last_field = field_matches[-1]
                last_line_end = raw_block.find("\n", last_field.end())
                if last_line_end == -1:
                    last_line_end = len(raw_block)
                body_end = body_start + last_line_end
                segment_end = body_end
            else:
                body_end = next_start_pos
                segment_end = next_start_pos

        body = response[body_start:body_end].strip()
        segments.append((start_match.start(), segment_end, body))

    if include_spans:
        return segments
    return [segment[2] for segment in segments if segment[2]]


def _normalize_domain_value(value: str, target: dict):
    candidates = [part.strip().lower() for part in re.split(r"[|,]", value) if part.strip()]
    deduped_tags: list[str] = []
    for tag in candidates:
        if tag not in deduped_tags:
            deduped_tags.append(tag)
    target["domain_tags"] = deduped_tags
    target["domain_code"] = next((item for item in candidates if item in VALID_BASE_DOMAINS), None)


def _normalize_horizon_value(value: str) -> str | None:
    candidates = [part.strip().lower() for part in re.split(r"[|,]", value) if part.strip()]
    normalized_candidates = [HORIZON_ALIASES.get(item, item) for item in candidates]
    return next((item for item in normalized_candidates if item in VALID_HORIZONS), None)


def _normalize_motivation_value(value: str) -> str | None:
    tokens = [token.strip().lower() for token in re.findall(r"[a-z_áéíóúñ]+", value)]
    normalized = [MOTIVATION_ALIASES.get(token, token) for token in tokens]
    return next((item for item in normalized if item in VALID_MOTIVATIONS), None)


def _normalize_relation_type_value(value: str) -> str | None:
    normalized = _normalize_field_key(value)
    normalized = RELATION_TYPE_ALIASES.get(normalized, normalized)
    return normalized if normalized in VALID_RELATION_TYPES else None


def _coerce_optional_int(value: str) -> int | None:
    numeric_match = re.search(r"-?\d+", value)
    if not numeric_match:
        return None
    try:
        return int(numeric_match.group(0))
    except ValueError:
        return None


def _coerce_optional_date(value: str) -> str | None:
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    return None


def _finalize_node(node: dict) -> dict | None:
    if not node.get("title"):
        return None

    node_type = NODE_TYPE_ALIASES.get(_normalize_field_key(node.get("node_type", "goal")), "goal")
    node["node_type"] = node_type

    if node_type == "goal" and not node.get("horizon"):
        node["horizon"] = "quarterly"
    if node_type in {"identity", "action"}:
        node["horizon"] = None
    if node_type != "system":
        node["cadence_text"] = None
    if node_type != "action":
        node["time_cost_min"] = None
        node["energy_cost"] = None
        node["attention_cost"] = None

    return node


def _parse_node_segments(response: str) -> list[dict]:
    nodes: list[dict] = []
    segments = _extract_segments(
        response,
        _NODE_START_PATTERN,
        _NODE_END_PATTERN,
        _NODE_FIELD_LINE_PATTERN,
    )

    for segment in segments:
        node: dict = {}
        for raw_line in segment.splitlines():
            line = raw_line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            normalized_key = _normalize_field_key(key)

            if normalized_key == "tipo":
                node["node_type"] = value
            elif normalized_key == "titulo":
                node["title"] = value
            elif normalized_key == "descripcion":
                node["description"] = value or None
            elif normalized_key == "dominio":
                _normalize_domain_value(value, node)
            elif normalized_key == "horizonte":
                node["horizon"] = _normalize_horizon_value(value)
            elif normalized_key == "fecha_inicio":
                node["start_date"] = _coerce_optional_date(value)
            elif normalized_key == "fecha_objetivo":
                node["target_date"] = _coerce_optional_date(value)
            elif normalized_key == "cadencia":
                node["cadence_text"] = value or None
            elif normalized_key == "costo_tiempo_min":
                node["time_cost_min"] = _coerce_optional_int(value)
            elif normalized_key == "costo_energia":
                node["energy_cost"] = _coerce_optional_int(value)
            elif normalized_key == "costo_atencion":
                node["attention_cost"] = _coerce_optional_int(value)
            elif normalized_key == "importancia":
                node["importance"] = _coerce_optional_int(value)
            elif normalized_key == "dificultad":
                node["difficulty"] = _coerce_optional_int(value)
            elif normalized_key == "compromiso":
                node["commitment"] = _coerce_optional_int(value)
            elif normalized_key == "motivacion":
                node["motivation_type"] = _normalize_motivation_value(value)
            elif normalized_key == "por_que_importa":
                node["why_matters"] = value or None
            elif normalized_key == "mi_opinion":
                node["nash_opinion"] = value or None

        finalized = _finalize_node(node)
        if finalized:
            nodes.append(finalized)

    return nodes


def _parse_legacy_goal_segments(response: str) -> list[dict]:
    nodes: list[dict] = []
    segments = _extract_segments(
        response,
        _LEGACY_GOAL_START_PATTERN,
        _LEGACY_GOAL_END_PATTERN,
        _LEGACY_GOAL_FIELD_LINE_PATTERN,
    )

    for segment in segments:
        node: dict = {"node_type": "goal"}
        for raw_line in segment.splitlines():
            line = raw_line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            normalized_key = _normalize_field_key(key)

            if normalized_key == "titulo":
                node["title"] = value
            elif normalized_key == "descripcion":
                node["description"] = value or None
            elif normalized_key == "dominio":
                _normalize_domain_value(value, node)
            elif normalized_key == "horizonte":
                node["horizon"] = _normalize_horizon_value(value)
            elif normalized_key == "fecha_inicio":
                node["start_date"] = _coerce_optional_date(value)
            elif normalized_key == "fecha_objetivo":
                node["target_date"] = _coerce_optional_date(value)
            elif normalized_key == "importancia":
                node["importance"] = _coerce_optional_int(value)
            elif normalized_key == "dificultad":
                node["difficulty"] = _coerce_optional_int(value)
            elif normalized_key == "compromiso":
                node["commitment"] = _coerce_optional_int(value)
            elif normalized_key == "motivacion":
                node["motivation_type"] = _normalize_motivation_value(value)
            elif normalized_key == "por_que_importa":
                node["why_matters"] = value or None
            elif normalized_key == "mi_opinion":
                node["nash_opinion"] = value or None

        finalized = _finalize_node(node)
        if finalized:
            nodes.append(finalized)

    return nodes


def _parse_relation_segments(response: str) -> list[dict]:
    relations: list[dict] = []
    segments = _extract_segments(
        response,
        _RELATION_START_PATTERN,
        _RELATION_END_PATTERN,
        _RELATION_FIELD_LINE_PATTERN,
    )

    for segment in segments:
        relation: dict = {}
        for raw_line in segment.splitlines():
            line = raw_line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            normalized_key = _normalize_field_key(key)

            if normalized_key == "origen":
                relation["source_title"] = value
            elif normalized_key == "destino":
                relation["target_title"] = value
            elif normalized_key == "tipo":
                relation["relation_type"] = _normalize_relation_type_value(value)
            elif normalized_key == "nota":
                relation["note"] = value or None

        if relation.get("source_title") and relation.get("target_title") and relation.get("relation_type"):
            relations.append(relation)

    return relations


def _remove_extraction_blocks(response: str) -> str:
    spans = []
    spans.extend(
        _extract_segments(
            response,
            _NODE_START_PATTERN,
            _NODE_END_PATTERN,
            _NODE_FIELD_LINE_PATTERN,
            include_spans=True,
        )
    )
    spans.extend(
        _extract_segments(
            response,
            _RELATION_START_PATTERN,
            _RELATION_END_PATTERN,
            _RELATION_FIELD_LINE_PATTERN,
            include_spans=True,
        )
    )
    spans.extend(
        _extract_segments(
            response,
            _LEGACY_GOAL_START_PATTERN,
            _LEGACY_GOAL_END_PATTERN,
            _LEGACY_GOAL_FIELD_LINE_PATTERN,
            include_spans=True,
        )
    )

    cleaned = response
    for start, end, _body in sorted(spans, key=lambda item: item[0], reverse=True):
        cleaned = cleaned[:start] + cleaned[end:]
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _sanitize_display_response(display_response: str) -> str:
    if not display_response:
        return display_response

    roleplay_marker = re.search(r"(?im)^\[(?:manuel|nash)\]\s*:", display_response)
    if roleplay_marker:
        head = display_response[:roleplay_marker.start()].strip()
        if head:
            display_response = head
        else:
            kept_lines: list[str] = []
            for raw_line in display_response.splitlines():
                line = raw_line.strip()
                match = re.match(r"^\[(manuel|nash)\]\s*:\s*(.*)$", line, flags=re.IGNORECASE)
                if not match:
                    if line:
                        kept_lines.append(line)
                    continue
                if (match.group(1) or "").lower() == "nash":
                    content = (match.group(2) or "").strip()
                    if content:
                        kept_lines.append(content)
            display_response = "\n".join(kept_lines).strip()

    return re.sub(r"\n{3,}", "\n\n", display_response).strip()


def _dedupe_nodes(nodes: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for node in nodes:
        title = (node.get("title") or "").strip().lower()
        node_type = (node.get("node_type") or "goal").strip().lower()
        horizon = (node.get("horizon") or "").strip().lower() if isinstance(node.get("horizon"), str) else ""
        key = f"{title}|{node_type}|{horizon}"
        if not title or key in seen:
            continue
        seen.add(key)
        deduped.append(node)
    return deduped


def _dedupe_relations(relations: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for relation in relations:
        key = "|".join(
            [
                (relation.get("source_title") or "").strip().lower(),
                (relation.get("target_title") or "").strip().lower(),
                (relation.get("relation_type") or "").strip().lower(),
            ]
        )
        if "||" in key or key in seen:
            continue
        seen.add(key)
        deduped.append(relation)
    return deduped


def _build_discovery_context(session: dict) -> str:
    profile_context = build_profile_context(redact_identity=should_redact_identity())
    domain_ratings = get_domain_ratings_for_context()
    existing_goals = get_goals_for_context()

    messages = session.get("messages", [])
    history_parts = []
    for msg in messages:
        role = "Manuel" if msg["role"] == "user" else "Nash"
        history_parts.append(f"[{role}]: {msg['content']}")

    conversation_history = "\n\n".join(history_parts) if history_parts else "(Inicio de la conversación)"

    return GOAL_DISCOVERY_PROMPT.format(
        profile_context=profile_context,
        domain_ratings=domain_ratings,
        existing_goals=existing_goals,
        conversation_history=conversation_history,
    )


async def chat_discovery(session_id: int, user_message: str) -> dict:
    session = get_discovery_session(session_id)
    if not session:
        raise ValueError(f"Discovery session {session_id} not found")
    if session["status"] != "active":
        raise ValueError(f"Discovery session {session_id} is not active")

    add_discovery_message(session_id, "user", user_message)
    session = get_discovery_session(session_id)
    system_prompt = _build_discovery_context(session)

    model = get_chat_model(
        temperature=0.2,
        context_window=DISCOVERY_MODEL_CTX,
        purpose="discovery",
    )

    log.info("discovery_chat_start", session_id=session_id, message_len=len(user_message))

    try:
        response = await model.ainvoke(
            [
                SystemMessage(content=sanitize_text_for_remote_llm(system_prompt)),
                HumanMessage(content=sanitize_text_for_remote_llm(user_message)),
            ]
        )
        response_text = restore_local_aliases(content_to_text(response.content))
    except Exception as exc:
        log.error("discovery_chat_error", error=str(exc))
        raise

    typed_nodes = _parse_node_segments(response_text)
    legacy_nodes = _parse_legacy_goal_segments(response_text)
    new_nodes = _dedupe_nodes([*typed_nodes, *legacy_nodes])
    new_relations = _dedupe_relations(_parse_relation_segments(response_text))

    display_response = _sanitize_display_response(_remove_extraction_blocks(response_text))
    if not display_response.strip():
        if new_nodes or new_relations:
            node_titles = [f"• {node.get('title', 'Nodo')}" for node in new_nodes]
            relation_titles = [
                f"• {rel['source_title']} -> {rel['relation_type']} -> {rel['target_title']}"
                for rel in new_relations
            ]
            bullet_lines = node_titles + relation_titles
            display_response = (
                "Preparé este borrador del life graph para que lo revises a la derecha:\n"
                + "\n".join(bullet_lines)
                + "\n\nSi quieres, afinamos antes de guardarlo."
            )
        else:
            display_response = "Te escucho. Elijamos una capa para avanzar ahora: identidad, meta, sistema o acción."

    add_discovery_message(session_id, "nash", display_response)

    if new_nodes or new_relations:
        session = get_discovery_session(session_id)
        merged_nodes = _dedupe_nodes([*(session.get("extracted_goals") or []), *new_nodes])
        merged_relations = _dedupe_relations([*(session.get("extracted_relations") or []), *new_relations])
        update_discovery_session(
            session_id,
            extracted_goals_json=json.dumps(merged_nodes, ensure_ascii=False),
            extracted_relations_json=json.dumps(merged_relations, ensure_ascii=False),
        )

    session = get_discovery_session(session_id)

    log.info(
        "discovery_chat_complete",
        session_id=session_id,
        response_len=len(display_response),
        nodes_extracted=len(new_nodes),
        relations_extracted=len(new_relations),
    )

    return {
        "response": display_response,
        "extracted_goals": new_nodes,
        "extracted_relations": new_relations,
        "session": session,
    }


def confirm_extracted_goal(session_id: int, goal_data: dict) -> dict:
    node_type = goal_data.get("node_type") or "goal"
    horizon = goal_data.get("horizon")
    if node_type == "goal" and not horizon:
        horizon = "quarterly"

    goal_id = insert_goal(
        title=goal_data.get("title", "Nodo sin título"),
        node_type=node_type,
        domain_code=goal_data.get("domain_code"),
        domain_tags=goal_data.get("domain_tags"),
        parent_goal_id=goal_data.get("parent_goal_id"),
        description=goal_data.get("description"),
        why_matters=goal_data.get("why_matters"),
        horizon=horizon,
        start_date=goal_data.get("start_date"),
        target_date=goal_data.get("target_date"),
        cadence_text=goal_data.get("cadence_text"),
        time_cost_min=goal_data.get("time_cost_min"),
        energy_cost=goal_data.get("energy_cost"),
        attention_cost=goal_data.get("attention_cost"),
        motivation_type=goal_data.get("motivation_type"),
        importance=goal_data.get("importance"),
        difficulty=goal_data.get("difficulty"),
        commitment=goal_data.get("commitment"),
        nash_opinion=goal_data.get("nash_opinion"),
        source="discovery",
        discovery_session_id=session_id,
    )

    session = get_discovery_session(session_id)
    if session:
        update_discovery_session(
            session_id,
            goals_confirmed=(session.get("goals_confirmed", 0) or 0) + 1,
        )

    log.info(
        "goal_confirmed",
        session_id=session_id,
        goal_id=goal_id,
        title=goal_data.get("title"),
        node_type=node_type,
    )

    from backend.db.schema import get_goal_by_id

    return get_goal_by_id(goal_id)


def end_discovery_session(session_id: int, summary: str | None = None) -> dict | None:
    session = get_discovery_session(session_id)
    if not session:
        return None

    if not summary:
        goals_confirmed = session.get("goals_confirmed", 0) or 0
        extracted_nodes = session.get("extracted_goals", [])
        extracted_relations = session.get("extracted_relations", [])
        summary = (
            f"Sesión completada. {goals_confirmed} nodos confirmados, "
            f"{len(extracted_nodes)} nodos identificados y {len(extracted_relations)} relaciones propuestas."
        )

    return update_discovery_session(
        session_id,
        status="completed",
        summary=summary,
    )
