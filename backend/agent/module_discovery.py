"""
Module Discovery Conversation Engine

Handles discovery conversations for Nutrition, Exercise, and Finance modules.
Reuses patterns from goal_discovery.py with module-specific prompts.
"""

import json
import re
import structlog
from langchain_core.messages import SystemMessage, HumanMessage

from backend.agent.profile import build_profile_context
from backend.llm import (
    content_to_text,
    get_chat_model,
    restore_local_aliases,
    sanitize_text_for_remote_llm,
    should_redact_identity,
)
from backend.db.schema import (
    get_module_discovery_session,
    add_module_discovery_message,
    update_module_discovery_session,
    upsert_nutrition_profile,
    upsert_exercise_profile,
    upsert_finance_profile,
    get_nutrition_profile,
    get_exercise_profile,
    get_finance_profile,
)

log = structlog.get_logger()

DISCOVERY_MODEL_CTX = 16384

# =============================================
# Module-specific prompts
# =============================================

NUTRITION_DISCOVERY_PROMPT = """\
Eres Nash en MODO DESCUBRIMIENTO DE NUTRICION. Tu objetivo es entender los habitos alimenticios de la persona usuaria, sus metas de nutricion, y configurar su perfil para tracking de macros.

CONTEXTO DE MANUEL:
{profile_context}

PERFIL DE NUTRICION ACTUAL:
{current_profile}

HISTORIAL DE CONVERSACION:
{conversation_history}

INFORMACION QUE NECESITAS RECOPILAR:
1. Peso actual y peso objetivo
2. Meta diaria de proteina (o calcular: 1.6-2.2g por kg de peso)
3. Meta de calorias (si la conoce)
4. Comidas por dia y horario de alimentacion
5. Restricciones alimenticias
6. Suplementos que toma
7. Intentos previos de dieta (que funciono/fallo)

METODOLOGIA:
- Haz preguntas naturales, una a la vez
- Cuando tengas informacion clara, extraela con el formato especificado
- Si la persona usuaria no sabe algo (ej: calorias), ofrece estimaciones basadas en sus metas
- Para ganar masa muscular: recomienda ~2g proteina/kg y superavit calorico moderado

EXTRACCION DE DATOS:
Cuando tengas informacion clara, incluyela asi:

[NUTRICION_DATA]
peso_kg: numero
peso_objetivo_kg: numero
proteina_objetivo_g: numero
calorias_objetivo: numero (opcional)
comidas_por_dia: numero
restricciones: lista separada por comas
suplementos: lista separada por comas
notas: texto libre
[/NUTRICION_DATA]

Responde SIEMPRE en español. Se conciso pero amable.
"""

EXERCISE_DISCOVERY_PROMPT = """\
Eres Nash en MODO DESCUBRIMIENTO DE EJERCICIO. Tu objetivo es entender el nivel de fitness de la persona usuaria, su equipamiento, limitaciones, y diseñar rutinas apropiadas.

CONTEXTO DE MANUEL:
{profile_context}

PERFIL DE EJERCICIO ACTUAL:
{current_profile}

HISTORIAL DE CONVERSACION:
{conversation_history}

INFORMACION QUE NECESITAS RECOPILAR:
1. Nivel de fitness (principiante/intermedio/avanzado)
2. Equipamiento disponible (casa + gym pronto)
3. Dias disponibles por semana para entrenar
4. Tiempo disponible por sesion
5. Metas especificas (masa muscular, movilidad, fuerza)
6. Lesiones o limitaciones
7. Problemas de movilidad (vida sedentaria en escritorio/cama)
8. Historia de entrenamiento previo

SISTEMA DE DOS NIVELES:
- MINIMO: Para dias de baja motivacion (10-15 min, movilidad + movimientos basicos)
- OPTIMO: Entrenamiento completo para ganancia muscular (45-60 min)

La persona usuaria mencionó que:
- Quiere ganar masa muscular
- Necesita movilidad (mucho tiempo en escritorio/cama)
- Tendra acceso a gym pronto
- No hace deportes, entrena solo

METODOLOGIA:
- Haz preguntas naturales, una a la vez
- Considera que necesita rutinas para casa ahora y gym despues
- Enfatiza movilidad dado su estilo de vida sedentario
- Recomienda ejercicios compuestos para eficiencia

EXTRACCION DE DATOS:
[EJERCICIO_DATA]
nivel: beginner|intermediate|advanced
equipamiento: lista separada por comas
dias_por_semana: numero
minutos_por_sesion: numero
metas: lista separada por comas
limitaciones: lista separada por comas
tiene_gym: 0 o 1
fecha_gym: YYYY-MM-DD (opcional)
enfoque_movilidad: 1
notas: texto libre
[/EJERCICIO_DATA]

Responde SIEMPRE en español. Se directo pero motivador.
"""

FINANCE_DISCOVERY_PROMPT = """\
Eres Nash en MODO DESCUBRIMIENTO FINANCIERO. Tu objetivo es entender la situacion financiera de la persona usuaria para ayudarlo a salir de deudas, organizar gastos, y optimizar su dinero.

CONTEXTO DE MANUEL:
{profile_context}

PERFIL FINANCIERO ACTUAL:
{current_profile}

HISTORIAL DE CONVERSACION:
{conversation_history}

INFORMACION QUE NECESITAS RECOPILAR:
1. Ingreso mensual neto
2. Gastos fijos (renta, suscripciones, servicios)
3. Deudas actuales (monto, tasa de interes, pago minimo)
4. Categorias principales de gasto variable
5. Meta de ahorro
6. Fondo de emergencia objetivo
7. Puntos de estres financiero
8. Patrones de gasto problematicos

ESTRATEGIA:
- Si tiene deudas: recomendar metodo avalancha (mayor interes primero) o bola de nieve (menor monto primero)
- Calcular cuanto queda disponible despues de fijos y deudas
- Sugerir asignacion por categoria

METODOLOGIA:
- Preguntas directas pero sin juzgar
- Si no quiere compartir montos exactos, trabajar con porcentajes
- Ser realista sobre lo que es posible ahorrar
- Priorizar: 1) gastos esenciales, 2) pago de deudas, 3) ahorro de emergencia, 4) otros

EXTRACCION DE DATOS:
[FINANZAS_DATA]
ingreso_mensual: numero
moneda: PEN|USD|etc
gastos_fijos: JSON [{{"nombre": "...", "monto": numero, "dia_pago": numero}}]
deudas: JSON [{{"nombre": "...", "total": numero, "restante": numero, "tasa": numero, "pago_minimo": numero}}]
meta_ahorro: numero
fondo_emergencia: numero
notas: texto libre
[/FINANZAS_DATA]

Responde SIEMPRE en español. Se profesional pero empatico con el estres financiero.
"""

MODULE_PROMPTS = {
    'nutrition': NUTRITION_DISCOVERY_PROMPT,
    'exercise': EXERCISE_DISCOVERY_PROMPT,
    'finance': FINANCE_DISCOVERY_PROMPT,
}


def _get_current_profile(module: str) -> str:
    """Get current profile for a module."""
    if module == 'nutrition':
        profile = get_nutrition_profile()
        if not profile:
            return "No hay perfil de nutricion configurado todavia."
        return f"""Peso: {profile.get('weight_kg') or '?'}kg
Peso objetivo: {profile.get('goal_weight_kg') or '?'}kg
Proteina objetivo: {profile.get('protein_target_g') or '?'}g
Calorias objetivo: {profile.get('calorie_target') or '?'}
Comidas/dia: {profile.get('meals_per_day') or '?'}"""

    elif module == 'exercise':
        profile = get_exercise_profile()
        if not profile:
            return "No hay perfil de ejercicio configurado todavia."
        return f"""Nivel: {profile.get('fitness_level') or '?'}
Equipamiento: {profile.get('equipment') or []}
Dias/semana: {profile.get('workout_days_per_week') or '?'}
Min/sesion: {profile.get('time_per_workout_min') or '?'}
Tiene gym: {'Si' if profile.get('has_gym_access') else 'No'}"""

    elif module == 'finance':
        profile = get_finance_profile()
        if not profile:
            return "No hay perfil financiero configurado todavia."
        return f"""Ingreso mensual: {profile.get('monthly_income') or '?'} {profile.get('currency') or 'PEN'}
Gastos fijos: {len(profile.get('fixed_expenses') or [])} items
Deudas: {len(profile.get('debts') or [])} items
Meta ahorro: {profile.get('savings_goal') or '?'}"""

    return "Modulo desconocido."


def _build_module_context(session: dict) -> str:
    """Build the full context for a module discovery conversation."""
    module = session['module']
    profile_context = build_profile_context(redact_identity=should_redact_identity())
    current_profile = _get_current_profile(module)

    messages = session.get('messages', [])
    history_parts = []
    for msg in messages:
        role = "Manuel" if msg['role'] == 'user' else "Nash"
        history_parts.append(f"[{role}]: {msg['content']}")

    conversation_history = "\n\n".join(history_parts) if history_parts else "(Inicio de la conversación)"

    prompt_template = MODULE_PROMPTS.get(module, NUTRITION_DISCOVERY_PROMPT)

    return prompt_template.format(
        profile_context=profile_context,
        current_profile=current_profile,
        conversation_history=conversation_history,
    )


def _parse_extracted_data(response: str, module: str) -> dict | None:
    """Parse module-specific data blocks from Nash's response."""
    patterns = {
        'nutrition': r'\[NUTRICION_DATA\](.*?)\[/NUTRICION_DATA\]',
        'exercise': r'\[EJERCICIO_DATA\](.*?)\[/EJERCICIO_DATA\]',
        'finance': r'\[FINANZAS_DATA\](.*?)\[/FINANZAS_DATA\]',
    }

    pattern = patterns.get(module)
    if not pattern:
        return None

    match = re.search(pattern, response, re.DOTALL)
    if not match:
        return None

    data = {}
    lines = match.group(1).strip().split('\n')
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()

            # Try to parse JSON values
            if value.startswith('[') or value.startswith('{'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            # Try to parse numbers
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)

            data[key] = value

    return data if data else None


def _remove_data_blocks(response: str) -> str:
    """Remove data blocks from response for display."""
    patterns = [
        r'\[NUTRICION_DATA\].*?\[/NUTRICION_DATA\]',
        r'\[EJERCICIO_DATA\].*?\[/EJERCICIO_DATA\]',
        r'\[FINANZAS_DATA\].*?\[/FINANZAS_DATA\]',
    ]
    cleaned = response
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def _save_extracted_data(module: str, data: dict, session_id: int) -> dict:
    """Save extracted data to the appropriate profile."""
    if module == 'nutrition':
        # Map Spanish keys to English
        profile_data = {
            'weight_kg': data.get('peso_kg'),
            'goal_weight_kg': data.get('peso_objetivo_kg'),
            'protein_target_g': data.get('proteina_objetivo_g'),
            'calorie_target': data.get('calorias_objetivo'),
            'meals_per_day': data.get('comidas_por_dia'),
            'restrictions_json': json.dumps(data.get('restricciones', '').split(',') if isinstance(data.get('restricciones'), str) else []),
            'supplements_json': json.dumps(data.get('suplementos', '').split(',') if isinstance(data.get('suplementos'), str) else []),
            'notes': data.get('notas'),
            'discovery_session_id': session_id,
        }
        return upsert_nutrition_profile({k: v for k, v in profile_data.items() if v is not None})

    elif module == 'exercise':
        profile_data = {
            'fitness_level': data.get('nivel'),
            'equipment_json': json.dumps(data.get('equipamiento', '').split(',') if isinstance(data.get('equipamiento'), str) else []),
            'workout_days_per_week': data.get('dias_por_semana'),
            'time_per_workout_min': data.get('minutos_por_sesion'),
            'goals_json': json.dumps(data.get('metas', '').split(',') if isinstance(data.get('metas'), str) else []),
            'limitations_json': json.dumps(data.get('limitaciones', '').split(',') if isinstance(data.get('limitaciones'), str) else []),
            'has_gym_access': data.get('tiene_gym'),
            'gym_start_date': data.get('fecha_gym'),
            'mobility_focus': data.get('enfoque_movilidad'),
            'notes': data.get('notas'),
            'discovery_session_id': session_id,
        }
        return upsert_exercise_profile({k: v for k, v in profile_data.items() if v is not None})

    elif module == 'finance':
        profile_data = {
            'monthly_income': data.get('ingreso_mensual'),
            'currency': data.get('moneda', 'PEN'),
            'fixed_expenses_json': json.dumps(data.get('gastos_fijos')) if isinstance(data.get('gastos_fijos'), list) else None,
            'debts_json': json.dumps(data.get('deudas')) if isinstance(data.get('deudas'), list) else None,
            'savings_goal': data.get('meta_ahorro'),
            'emergency_fund_target': data.get('fondo_emergencia'),
            'notes': data.get('notas'),
            'discovery_session_id': session_id,
        }
        return upsert_finance_profile({k: v for k, v in profile_data.items() if v is not None})

    return {}


async def chat_module_discovery(session_id: int, user_message: str) -> dict:
    """
    Process a message in a module discovery conversation.

    Returns:
        {
            'response': str,
            'extracted_data': dict | None,
            'session': dict,
            'profile_updated': bool,
        }
    """
    session = get_module_discovery_session(session_id)
    if not session:
        raise ValueError(f"Module discovery session {session_id} not found")

    if session['status'] != 'active':
        raise ValueError(f"Module discovery session {session_id} is not active")

    module = session['module']

    # Add user message to session
    add_module_discovery_message(session_id, 'user', user_message)

    # Refresh session with new message
    session = get_module_discovery_session(session_id)

    # Build context and call LLM
    system_prompt = _build_module_context(session)

    model = get_chat_model(
        temperature=0.7,
        context_window=DISCOVERY_MODEL_CTX,
        purpose="discovery",
    )

    messages = [
        SystemMessage(content=sanitize_text_for_remote_llm(system_prompt)),
        HumanMessage(content=sanitize_text_for_remote_llm(user_message)),
    ]

    log.info("module_discovery_chat_start", session_id=session_id, module=module, message_len=len(user_message))

    try:
        response = await model.ainvoke(messages)
        response_text = restore_local_aliases(content_to_text(response.content))
    except Exception as e:
        log.error("module_discovery_chat_error", error=str(e))
        raise

    # Parse any extracted data
    extracted_data = _parse_extracted_data(response_text, module)
    profile_updated = False

    # Save extracted data to profile
    if extracted_data:
        _save_extracted_data(module, extracted_data, session_id)
        profile_updated = True

        # Update session with extracted data
        session = get_module_discovery_session(session_id)
        existing_data = session.get('extracted_data', {})
        existing_data.update(extracted_data)
        update_module_discovery_session(
            session_id,
            extracted_data_json=json.dumps(existing_data)
        )

    # Clean response for display
    display_response = _remove_data_blocks(response_text)

    # Add Nash's response to session
    add_module_discovery_message(session_id, 'nash', display_response)

    # Get final session state
    session = get_module_discovery_session(session_id)

    log.info(
        "module_discovery_chat_complete",
        session_id=session_id,
        module=module,
        response_len=len(display_response),
        profile_updated=profile_updated,
    )

    return {
        'response': display_response,
        'extracted_data': extracted_data,
        'session': session,
        'profile_updated': profile_updated,
    }


def end_module_discovery_session(session_id: int, summary: str | None = None) -> dict | None:
    """End a module discovery session."""
    session = get_module_discovery_session(session_id)
    if not session:
        return None

    if not summary:
        module = session['module']
        summary = f"Sesión de descubrimiento de {module} completada."

    return update_module_discovery_session(
        session_id,
        status='completed',
        summary=summary,
    )
