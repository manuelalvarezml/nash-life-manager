import structlog

from backend.db.schema import (
    get_entry_count,
    get_expenses,
    get_finance_profile,
    get_monthly_expense_summary,
    get_profile_facts,
    get_profile_summaries,
    get_self_profile,
)
from backend.db.chroma import query_semantic_units
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
