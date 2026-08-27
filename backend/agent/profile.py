import structlog

from backend.db.schema import (
    get_entry_count,
    get_exercise_profile,
    get_expenses,
    get_finance_profile,
    get_latest_body_measurement_snapshot,
    get_monthly_expense_summary,
    get_personal_records,
    get_profile_facts,
    get_profile_summaries,
    get_self_profile,
    get_workout_adherence_summary,
    get_workout_sessions,
)
from backend.db.chroma import query_semantic_units
from backend.exercise_engine import generate_workout_plan
from backend.llm import build_literal_replacements, sanitize_text_for_remote_llm

log = structlog.get_logger()

ONBOARDING_THRESHOLD = 10


def _pick(data: dict, *keys: str):
    for key in keys:
        if key in data and data[key] not in (None, "", []):
            return data[key]
    return None


def _build_self_profile_context(
    self_profile: dict | None,
    *,
    redact_identity: bool = False,
    replacements: list[tuple[str, str]] | None = None,
) -> str | None:
    """Build biographical context from self_profile_facts."""
    if not self_profile:
        return None

    parts = []

    # Basic identity
    name = self_profile.get("preferred_name")
    if name and not redact_identity:
        parts.append(f"Nombre: {name}")

    birth_date = self_profile.get("birth_date")
    if birth_date and not redact_identity:
        parts.append(f"Fecha de nacimiento: {birth_date}")

    # Current situation
    city = self_profile.get("current_city")
    country = self_profile.get("current_country")
    if (city or country) and not redact_identity:
        loc = ", ".join(filter(None, [city, country]))
        parts.append(f"Vive en: {loc}")

    living = self_profile.get("living_situation")
    if living:
        text = (
            sanitize_text_for_remote_llm(living, replacements)
            if redact_identity
            else living
        )
        parts.append(f"Situación: {text}")

    # Career
    occupation = self_profile.get("current_occupation")
    if occupation:
        text = (
            sanitize_text_for_remote_llm(occupation, replacements)
            if redact_identity
            else occupation
        )
        parts.append(f"Ocupación: {text}")

    # Relationships
    rel_status = self_profile.get("relationship_status")
    if rel_status:
        partner = self_profile.get("partner_name")
        if partner and rel_status in ("en relacion", "casado") and not redact_identity:
            parts.append(f"Relación: {rel_status} con {partner}")
        else:
            text = (
                sanitize_text_for_remote_llm(rel_status, replacements)
                if redact_identity
                else rel_status
            )
            parts.append(f"Estado: {text}")

    # Family context
    mother_rel = self_profile.get("mother_relationship")
    father_rel = self_profile.get("father_relationship")
    if mother_rel or father_rel:
        family_parts = []
        if mother_rel:
            family_parts.append(f"madre: {mother_rel}")
        if father_rel:
            family_parts.append(f"padre: {father_rel}")
        parts.append(f"Relación con padres: {', '.join(family_parts)}")

    # Values
    values_json = self_profile.get("core_values_json")
    if values_json and values_json != "[]":
        try:
            import json
            values = json.loads(values_json)
            if values:
                joined = ", ".join(values[:5])
                text = (
                    sanitize_text_for_remote_llm(joined, replacements)
                    if redact_identity
                    else joined
                )
                parts.append(f"Valores: {text}")
        except Exception:
            pass

    # Attachment style
    attachment = self_profile.get("attachment_style")
    if attachment and attachment != "no se":
        text = (
            sanitize_text_for_remote_llm(attachment, replacements)
            if redact_identity
            else attachment
        )
        parts.append(f"Estilo de apego: {text}")

    # Life theme
    theme = self_profile.get("life_theme")
    if theme:
        trimmed = theme[:150]
        text = (
            sanitize_text_for_remote_llm(trimmed, replacements)
            if redact_identity
            else trimmed
        )
        parts.append(f"Tema de vida: {text}")

    # Communication preference
    comm_style = self_profile.get("communication_style")
    if comm_style:
        text = (
            sanitize_text_for_remote_llm(comm_style, replacements)
            if redact_identity
            else comm_style
        )
        parts.append(f"Prefiere comunicación: {text}")

    if not parts:
        return None

    return "\n  ".join(parts)


def _build_finance_context(
    *,
    redact_identity: bool = False,
    replacements: list[tuple[str, str]] | None = None,
) -> str | None:
    profile = get_finance_profile() or {}
    monthly_summary = get_monthly_expense_summary()
    recent_expenses = get_expenses(limit=5)

    fixed_expenses = profile.get("fixed_expenses") or []
    debts = profile.get("debts") or []

    has_snapshot = any(
        [
            profile.get("monthly_income") is not None,
            fixed_expenses,
            debts,
            monthly_summary.get("total"),
            recent_expenses,
        ]
    )
    if not has_snapshot:
        return None

    currency = profile.get("currency") or "PEN"
    parts: list[str] = []

    if profile.get("monthly_income") is not None:
        parts.append(f"Ingreso mensual neto: {profile['monthly_income']} {currency}")

    if fixed_expenses:
        total_fixed = 0.0
        due_days: list[str] = []
        for item in fixed_expenses:
            amount = _pick(item, "amount", "monto") or 0
            total_fixed += float(amount or 0)
            due_day = _pick(item, "due_day", "dia_pago")
            if due_day not in (None, ""):
                due_days.append(str(due_day))
        parts.append(
            f"Gastos fijos: {len(fixed_expenses)} items, total aprox {round(total_fixed, 2)} {currency}"
        )
        if due_days:
            parts.append(f"Dias de pago fijos conocidos: {', '.join(due_days[:6])}")

    if debts:
        parts.append("Deudas activas:")
        for debt in debts[:5]:
            name = str(_pick(debt, "name", "nombre") or "Deuda")
            remaining = _pick(debt, "remaining", "restante")
            interest = _pick(debt, "interest_rate", "tasa")
            min_payment = _pick(debt, "min_payment", "pago_minimo")
            if redact_identity:
                name = sanitize_text_for_remote_llm(name, replacements)
            bullet = f"  - {name}"
            if remaining is not None:
                bullet += f": saldo {remaining} {currency}"
            if interest is not None:
                bullet += f", tasa {interest}%"
            if min_payment is not None:
                bullet += f", pago minimo {min_payment} {currency}"
            parts.append(bullet)

    if profile.get("savings_goal") is not None:
        parts.append(f"Meta de ahorro: {profile['savings_goal']} {currency}")

    if profile.get("emergency_fund_target") is not None:
        parts.append(f"Fondo de emergencia objetivo: {profile['emergency_fund_target']} {currency}")

    parts.append(f"Gasto del mes registrado: {monthly_summary.get('total', 0)} {currency}")

    by_category = monthly_summary.get("by_category") or []
    if by_category:
        top_categories = ", ".join(
            f"{item.get('name_es') or 'Sin categoria'} {item.get('total', 0)} {currency}"
            for item in by_category[:4]
        )
        parts.append(f"Categorias mas pesadas del mes: {top_categories}")

    if recent_expenses:
        parts.append("Ultimos movimientos:")
        for expense in recent_expenses[:5]:
            description = expense.get("description") or "Movimiento"
            category = expense.get("category_name") or "Sin categoria"
            if redact_identity:
                description = sanitize_text_for_remote_llm(description, replacements)
                category = sanitize_text_for_remote_llm(category, replacements)
            parts.append(
                f"  - {category}: {description} ({expense.get('amount', 0)} {currency})"
            )

    return "\n  ".join(parts)


def _build_exercise_context(
    *,
    redact_identity: bool = False,
    replacements: list[tuple[str, str]] | None = None,
) -> str | None:
    try:
        profile = get_exercise_profile() or {}
        latest_measurement = get_latest_body_measurement_snapshot()
        recent_sessions = get_workout_sessions(limit=4)
        recent_records = get_personal_records(limit=4)
        adherence_7 = get_workout_adherence_summary(days=7)
        adherence_28 = get_workout_adherence_summary(days=28)
        plan = generate_workout_plan()
    except Exception as exc:
        log.warning("exercise_context_unavailable", error=str(exc))
        return None

    has_snapshot = any(
        [
            profile,
            latest_measurement,
            recent_sessions,
            recent_records,
            adherence_7.get("total_sessions"),
            adherence_28.get("total_sessions"),
        ]
    )
    if not has_snapshot:
        return None

    goal_labels = {
        "muscle_gain": "ganar musculo",
        "strength": "ganar fuerza",
        "recomposition": "recomposicion",
        "general_fitness": "salud general",
    }
    level_labels = {
        "beginner": "principiante",
        "intermediate": "intermedio",
        "advanced": "avanzado",
    }
    location_labels = {
        "home": "casa",
        "gym": "gym",
        "either": "flexible",
    }

    def _sanitize(value: str | None, limit: int = 180) -> str | None:
        if not value:
            return None
        trimmed = value[:limit]
        return (
            sanitize_text_for_remote_llm(trimmed, replacements)
            if redact_identity
            else trimmed
        )

    training_target = plan.get("training_target") or {}
    primary_session = plan.get("primary_session") or {}
    fallback_session = plan.get("fallback_session") or {}

    parts: list[str] = []

    goal = goal_labels.get(profile.get("primary_goal"), profile.get("primary_goal"))
    level = level_labels.get(profile.get("fitness_level"), profile.get("fitness_level"))
    if goal or level:
        sentence = "Objetivo corporal"
        if goal:
            sentence += f": {goal}"
        if level:
            sentence += f" | nivel {level}"
        parts.append(sentence)

    weekly_target = profile.get("workout_days_per_week")
    min_minutes = profile.get("minimum_session_min")
    optimal_minutes = profile.get("optimal_session_min") or profile.get("time_per_workout_min")
    preferred_location = location_labels.get(
        profile.get("preferred_location"),
        profile.get("preferred_location"),
    )
    schedule_days = profile.get("schedule_days") or []
    schedule_text = ", ".join(str(day) for day in schedule_days[:4]) if schedule_days else None
    if weekly_target or min_minutes or optimal_minutes or preferred_location:
        parts.append(
            "Piso y estructura: "
            f"{weekly_target or '?'} sesiones/semana, minimo {min_minutes or '?'} min, "
            f"optimo {optimal_minutes or '?'} min, lugar preferido {preferred_location or 'no definido'}"
        )
    if schedule_text:
        parts.append(f"Dias preferidos: {schedule_text}")

    barriers = profile.get("barriers") or []
    if barriers:
        parts.append(f"Barreras de adherencia: {', '.join(str(item) for item in barriers[:5])}")

    enjoyment = profile.get("enjoyment") or []
    if enjoyment:
        parts.append(f"Lo que suele disfrutar mas: {', '.join(str(item) for item in enjoyment[:5])}")

    limitations = profile.get("limitations") or []
    if limitations:
        parts.append(f"Limitaciones o cuidado: {', '.join(str(item) for item in limitations[:5])}")

    history_note = _sanitize(profile.get("training_history_notes"))
    if history_note:
        parts.append(f"Historia de entrenamiento: {history_note}")

    general_note = _sanitize(profile.get("notes"))
    if general_note:
        parts.append(f"Notas del modulo cuerpo: {general_note}")

    phase = training_target.get("phase")
    weekly_sessions_target = training_target.get("weekly_sessions_target")
    hard_sets = training_target.get("hard_sets_goal_per_muscle")
    if phase or weekly_sessions_target or hard_sets:
        parts.append(
            "Fase actual del motor: "
            f"{phase or 'base'} | objetivo semanal {weekly_sessions_target or '?'} sesiones | "
            f"hard sets objetivo {hard_sets or '?'} por grupo muscular"
        )

    primary_name = primary_session.get("name")
    fallback_name = fallback_session.get("name")
    primary_time = primary_session.get("estimated_duration_min")
    fallback_time = fallback_session.get("estimated_duration_min")
    if primary_name or fallback_name:
        parts.append(
            "Plan sugerido hoy: "
            f"{primary_name or 'sin plan'} ({primary_time or '?'} min). "
            f"Rescate: {fallback_name or 'sin rescate'} ({fallback_time or '?'} min)."
        )

    sessions_7 = adherence_7.get("total_sessions") or 0
    sessions_28 = adherence_28.get("total_sessions") or 0
    minutes_7 = adherence_7.get("total_duration_min") or 0
    fallback_7 = adherence_7.get("fallback_sessions") or 0
    parts.append(
        "Adherencia reciente: "
        f"{sessions_7} sesiones en 7 dias ({minutes_7} min totales, {fallback_7} rescates), "
        f"{sessions_28} sesiones en 28 dias."
    )

    if latest_measurement:
        measurement_parts = []
        for label, field in [
            ("peso", "weight_kg"),
            ("cintura", "waist_cm"),
            ("cadera", "hip_cm"),
            ("brazo", "arm_relaxed_cm"),
            ("muslo", "thigh_cm"),
        ]:
            value = latest_measurement.get(field)
            if value is not None:
                measurement_parts.append(f"{label} {value}")
        if measurement_parts:
            parts.append(
                f"Ultima medicion ({latest_measurement.get('taken_on')}): "
                + ", ".join(measurement_parts)
            )
    else:
        parts.append(
            "Mediciones corporales: aun no hay linea base registrada. Para hipertrofia, "
            "conviene combinar peso, cintura y perimetros repetibles."
        )

    if recent_records:
        record_parts = []
        for record in recent_records[:3]:
            weight = record.get("weight_kg") or 0
            reps = record.get("reps") or 0
            if weight:
                record_parts.append(f"{record.get('exercise_name')}: {weight} kg x {reps}")
            else:
                record_parts.append(f"{record.get('exercise_name')}: {reps} reps")
        if record_parts:
            parts.append(f"PRs recientes: {' | '.join(record_parts)}")

    if recent_sessions:
        session_parts = []
        for session in recent_sessions[:3]:
            session_parts.append(
                f"{session.get('date')}: {session.get('level')} "
                f"{session.get('actual_location') or session.get('planned_location') or 'n/a'} "
                f"{session.get('duration_min') or '?'} min "
                f"(energia {session.get('energy_level') or '?'}, RPE {session.get('session_rpe') or '?'})"
            )
        parts.append(f"Ultimas sesiones: {' | '.join(session_parts)}")

    return "\n  ".join(parts)


def build_profile_context(
    current_message: str | None = None,
    *,
    redact_identity: bool = False,
) -> str:
    """Build the profile context string injected into every LLM call."""
    summaries = get_profile_summaries()
    facts = get_profile_facts()
    self_profile = get_self_profile()
    replacements = build_literal_replacements(self_profile) if redact_identity else None

    parts = ["PERFIL ACTUAL DE LA PERSONA USUARIA:"]

    has_data = False

    # Add biographical context first (most stable)
    bio_context = _build_self_profile_context(
        self_profile,
        redact_identity=redact_identity,
        replacements=replacements,
    )
    if bio_context:
        parts.append(f"\n[DATOS BIOGRÁFICOS]:\n  {bio_context}")
        has_data = True

    finance_context = _build_finance_context(
        redact_identity=redact_identity,
        replacements=replacements,
    )
    if finance_context:
        parts.append(f"\n[FINANZAS]:\n  {finance_context}")
        has_data = True

    exercise_context = _build_exercise_context(
        redact_identity=redact_identity,
        replacements=replacements,
    )
    if exercise_context:
        parts.append(f"\n[CUERPO Y ENTRENAMIENTO]:\n  {exercise_context}")
        has_data = True

    for domain, summary in summaries.items():
        if summary.strip():
            text = (
                sanitize_text_for_remote_llm(summary, replacements)
                if redact_identity
                else summary
            )
            parts.append(f"\n[{domain.upper()}]: {text}")
            has_data = True

    if facts:
        parts.append("\n\nHECHOS REGISTRADOS:")
        for f in facts[:20]:
            confidence_marker = {"emerging": "~", "developing": "?", "established": "✓"}.get(
                f["confidence"], "~"
            )
            statement = f["statement"]
            if redact_identity:
                statement = sanitize_text_for_remote_llm(statement, replacements)
            parts.append(
                f"  {confidence_marker} [{f['domain']}] ({f['fact_type']}): {statement}"
            )
        has_data = True

    # Semantic retrieval from Chroma (Phase 2)
    if current_message and current_message.strip():
        try:
            relevant_units = query_semantic_units(current_message, n_results=5)
            if relevant_units:
                parts.append("\n\nUNIDADES SEMÁNTICAS RELEVANTES:")
                for u in relevant_units:
                    unit_type = u.get("unit_type", "?")
                    life_period = u.get("life_period", "")
                    content = u.get("content", "")[:200]
                    if redact_identity:
                        content = sanitize_text_for_remote_llm(content, replacements)
                    parts.append(f"  [{unit_type}] ({life_period}): {content}")
                has_data = True
        except Exception as e:
            log.warning("semantic_retrieval_error", error=str(e))

    if not has_data:
        parts = ["PERFIL: No hay información sobre la persona usuaria todavía. Es la primera interacción."]

    return "\n".join(parts)


def is_onboarding() -> bool:
    return get_entry_count() < ONBOARDING_THRESHOLD
