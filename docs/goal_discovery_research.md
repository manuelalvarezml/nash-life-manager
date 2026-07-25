# Goal Discovery Conversation — Research & Design

> Research synthesis for implementing conversational goal discovery with Nash.

---

## Research Sources

### Coaching Frameworks
- [GROW Model Questions](https://www.thecoachingtoolscompany.com/grow-model-coaching-questions/) — 79+ coaching questions organized by GROW stages
- [Co-Active Self-Discovery Questions](https://coactive.com/blog/self-discovery-questions/) — Discovery questions from leading coaching institute
- [Positive Psychology Life Coaching](https://positivepsychology.com/life-coaching-questions/) — 20+ powerful coaching questions

### Goal Systems Theory
- [Kruglanski et al. Goal Systems Theory (2023)](https://academic.oup.com/book/45852) — Comprehensive framework for understanding goal systems
- [Properties of Goal Systems](https://link.springer.com/article/10.1007/s11225-008-9117-6) — Formal analysis of consistency, conflict, and coherence

### Motivational Interviewing
- [NCBI MI as Counseling Style](https://www.ncbi.nlm.nih.gov/books/NBK571068/) — Evidence-based approach for behavior change
- [OARS Framework](https://positivepsychology.com/motivational-interviewing/) — Open questions, Affirmations, Reflections, Summaries

### AI Goal Setting
- [LLM-Based Goal Setting Chatbots (arXiv 2024)](https://arxiv.org/html/2602.08636) — State-based architecture for structured goal conversations
- [AI Coaching Chatbot Research](https://journals.sagepub.com/doi/10.1177/09504222241287090) — Goal-attainment chatbot using GROW model

### Goal Attributes Research
- [Goal Setting Wikipedia](https://en.wikipedia.org/wiki/Goal_setting) — Locke & Latham's foundational research
- [Hierarchical Taxonomy of Human Goals](https://link.springer.com/article/10.1023/A:1012225223418) — Classification of 135 human goals
- [Comprehensive Taxonomy of Human Motives](https://ncbi.nlm.nih.gov/pmc/articles/PMC5322894) — 161 motives organized hierarchically

---

## Key Frameworks

### 1. GROW Model (Coaching Foundation)

| Stage | Purpose | Key Questions |
|-------|---------|---------------|
| **G**oal | What do you want? | "¿Qué te gustaría lograr?" "Si todo fuera posible, ¿qué querrías?" |
| **R**eality | What's happening now? | "¿Dónde estás ahora con respecto a esto?" "¿Qué has intentado?" |
| **O**ptions | What could you do? | "¿Qué opciones tienes?" "¿Qué más podrías hacer?" |
| **W**ill | What will you do? | "¿Qué vas a hacer?" "¿Cuándo?" "¿Cómo sabré que lo lograste?" |

**Key Insight:** The model is flexible — conversations flow ROTGOW or TROWG, not rigidly G-R-O-W.

### 2. Motivational Interviewing (OARS)

| Technique | Purpose | Example |
|-----------|---------|---------|
| **O**pen Questions | Explore without leading | "¿Qué es lo más importante para ti en este momento?" |
| **A**ffirmations | Build confidence | "Has logrado cosas difíciles antes..." |
| **R**eflections | Show understanding | "Suena como que te sientes atrapado entre..." |
| **S**ummaries | Consolidate | "Entonces, lo que escucho es... ¿es correcto?" |

**Key Insight:** Never give unsolicited advice. Draw out the person's own reasons for change.

### 3. Goal Systems Theory (GST)

**Core Concepts:**
- **Goal Hierarchy**: Superordinate (abstract) → Subordinate (concrete)
- **Multifinality**: Means that serve multiple goals simultaneously
- **Equifinality**: Multiple means to the same goal
- **Coherence**: How well goals align and support each other
- **Conflict**: When pursuing one goal harms another

**Conflict Types:**
1. **Resource conflict**: Time, money, energy competing
2. **Instrumental conflict**: Means for one goal harms another
3. **Value conflict**: Goals reflect opposing values
4. **Identity conflict**: Goals pull toward different self-concepts

### 4. Goal Attributes (Research-Validated)

| Attribute | Description | Why It Matters |
|-----------|-------------|----------------|
| **Importance** | Personal significance (1-10) | Predicts commitment and persistence |
| **Difficulty** | Challenge level (1-10) | Optimal: challenging but attainable |
| **Commitment** | Determination to pursue (1-10) | Strongest predictor of achievement |
| **Specificity** | How concrete/measurable | Specific > vague for performance |
| **Timeframe** | Deadline or horizon | Creates urgency, enables planning |
| **Motivation Type** | External → Intrinsic | Intrinsic = more sustained pursuit |
| **Locus of Control** | Internal vs external | Internal = more agency |
| **Progress** | Current advancement (%) | Feedback loop for adjustment |
| **Values Alignment** | Connection to core values | Self-concordance research |

---

## Conversation Architecture

### State-Based Flow (Inspired by arXiv Paper)

```
┌─────────────────────────────────────────────────────────────┐
│                    GOAL DISCOVERY SESSION                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │ ENGAGE  │───▶│  EXPLORE │───▶│  EXTRACT │───▶│ REVIEW │ │
│  │         │    │          │    │          │    │        │ │
│  │ Build   │    │ Life     │    │ Specific │    │ Check  │ │
│  │ rapport │    │ domains  │    │ goals    │    │ list   │ │
│  │         │    │ values   │    │ details  │    │        │ │
│  └─────────┘    └──────────┘    └──────────┘    └────────┘ │
│       │              │               │               │      │
│       └──────────────┴───────────────┴───────────────┘      │
│                    (Can loop back any time)                 │
└─────────────────────────────────────────────────────────────┘
```

### Session States

1. **ENGAGE** — Build context, understand current state
   - "¿Cómo te sientes con tu vida en general?"
   - Review Wheel of Life domains if rated

2. **EXPLORE** — Discover what matters, dreams, frustrations
   - "¿Qué te gustaría que fuera diferente?"
   - "Si pudieras cambiar una cosa, ¿qué sería?"
   - "¿Qué te hace sentir más vivo?"

3. **EXTRACT** — Get specific on goals
   - "Hablemos más de [tema]. ¿Qué específicamente quieres lograr?"
   - "¿Cómo sabrás que lo lograste?"
   - "¿Para cuándo te gustaría esto?"

4. **REVIEW** — Present extracted goals, check coherence
   - "Hasta ahora he identificado estas metas: [lista]"
   - "¿Te parece que capturé lo importante?"
   - "Noto una posible tensión entre X e Y..."

---

## Nash's Analysis Capabilities

### Opinion Fields for Each Goal

```python
GoalAnalysis:
    coherence_score: float      # 0-100, how well it fits with other goals
    priority_rank: int          # Suggested priority order
    nash_opinion: str           # Free-form analysis
    conflicts: list[GoalConflict]
    synergies: list[GoalSynergy]
    recommendations: list[str]
    questions_for_user: list[str]  # What Nash still wants to know
```

### Coherence Analysis Algorithm

```python
def analyze_goal_coherence(goal, all_goals, user_profile):
    analysis = {
        "conflicts": [],
        "synergies": [],
        "score": 100
    }

    for other_goal in all_goals:
        if other_goal.id == goal.id:
            continue

        # Time conflict
        if goals_overlap_timeframe(goal, other_goal):
            if combined_effort_exceeds_capacity(goal, other_goal):
                analysis["conflicts"].append({
                    "type": "resource_time",
                    "with_goal": other_goal.id,
                    "severity": "medium",
                    "note": f"Both '{goal.title}' and '{other_goal.title}' require significant time in same period"
                })
                analysis["score"] -= 15

        # Value alignment check
        if goals_share_domain(goal, other_goal):
            analysis["synergies"].append({
                "with_goal": other_goal.id,
                "type": "domain_alignment",
                "note": f"Both support your {goal.domain} priorities"
            })
            analysis["score"] += 5

        # Contradiction check
        if goals_contradict(goal, other_goal):
            analysis["conflicts"].append({
                "type": "value_conflict",
                "with_goal": other_goal.id,
                "severity": "high",
                "note": "These goals may pull in opposite directions"
            })
            analysis["score"] -= 25

    # Values alignment from self_profile
    if user_profile.core_values:
        aligned_values = find_value_match(goal, user_profile.core_values)
        if aligned_values:
            analysis["score"] += len(aligned_values) * 5
        else:
            analysis["questions_for_user"].append(
                "No veo conexión clara con tus valores principales. ¿Por qué es importante esta meta para ti?"
            )

    return analysis
```

---

## Database Schema Additions

### Expanded Goals Table

```sql
ALTER TABLE goals ADD COLUMN importance INTEGER CHECK (importance BETWEEN 1 AND 10);
ALTER TABLE goals ADD COLUMN difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 10);
ALTER TABLE goals ADD COLUMN commitment INTEGER CHECK (commitment BETWEEN 1 AND 10);
ALTER TABLE goals ADD COLUMN locus_of_control TEXT CHECK (locus_of_control IN ('internal', 'external', 'mixed'));
ALTER TABLE goals ADD COLUMN nash_opinion TEXT;           -- Nash's analysis
ALTER TABLE goals ADD COLUMN coherence_score REAL;        -- 0-100
ALTER TABLE goals ADD COLUMN conflicts_json TEXT;         -- JSON array of conflicts
ALTER TABLE goals ADD COLUMN synergies_json TEXT;         -- JSON array of synergies
ALTER TABLE goals ADD COLUMN source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'discovery'));
ALTER TABLE goals ADD COLUMN discovery_session_id INTEGER REFERENCES goal_discovery_sessions(id);
```

### Goal Discovery Sessions Table

```sql
CREATE TABLE IF NOT EXISTS goal_discovery_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    current_state TEXT DEFAULT 'engage',  -- engage, explore, extract, review
    messages_json TEXT NOT NULL DEFAULT '[]',  -- Full conversation
    extracted_goals_json TEXT DEFAULT '[]',    -- Goals identified so far
    context_snapshot TEXT,                     -- Profile context at session start
    summary TEXT                               -- Session summary when complete
);
```

---

## System Prompt for Goal Discovery Mode

```
Eres Nash en modo de descubrimiento de metas. Tu objetivo es ayudar a Manuel a:
1. Explorar qué quiere para su vida
2. Identificar metas específicas y medibles
3. Encontrar la coherencia entre sus metas
4. Detectar posibles conflictos
5. Dar tu opinión honesta sobre cada meta

CONTEXTO DE MANUEL:
{self_profile_context}
{profile_summaries_context}

METAS ACTUALES:
{existing_goals}

DOMINIOS DE VIDA (Wheel of Life):
{domain_ratings}

CONVERSACIÓN:
{conversation_history}

INSTRUCCIONES:
- Usa preguntas abiertas para explorar, no para dirigir
- Cuando identifiques una meta potencial, confírmala: "Suena como que quieres [X]. ¿Es correcto?"
- Cuando tengas suficiente información, extrae la meta en formato estructurado
- Sé honesto sobre conflictos que veas: "Noto que esta meta podría chocar con..."
- Da tu opinión cuando la pidas, o cuando veas algo importante
- Mantén un tono de amigo sabio, no de coach corporativo

EXTRACCIÓN DE METAS:
Cuando identifiques una meta clara, usa este formato en tu respuesta:
[META_IDENTIFICADA]
título: ...
descripción: ...
dominio: ...
horizonte: ...
importancia_estimada: 1-10
dificultad_estimada: 1-10
por_qué_importa: ...
mi_opinión: ...
[/META_IDENTIFICADA]

El usuario puede hablar en voz o texto. Responde siempre en español.
```

---

## Future Considerations (Lined Up)

### Voice Output for Nash
- Text-to-speech integration (ElevenLabs, local TTS)
- Voice conversation mode
- Emotional tone matching

### Expert Panel Debate (Multi-Agent)
- Spawn 5 "expert" personas (psychologist, strategist, realist, optimist, philosopher)
- Each analyzes goals from their perspective
- Synthesize into balanced recommendation
- Extensible to all Nash interactions

### MCP Integration
- Model Context Protocol for tool standardization
- External knowledge bases
- Specialized coaching tools

---

## Implementation Phases

1. **Phase A: Schema & Context** — Add goal fields, build goal context function
2. **Phase B: Discovery Session** — Table, API, session management
3. **Phase C: Specialized Prompt** — Goal discovery system prompt
4. **Phase D: Goal Extraction** — Parse [META_IDENTIFICADA] blocks
5. **Phase E: Frontend** — Discovery conversation UI in Metas tab
6. **Phase F: Coherence Analysis** — Nash opinion generation

---

## Success Metrics

- [ ] User can start goal discovery conversation from Metas tab
- [ ] Nash asks exploratory questions, not leading ones
- [ ] Goals are extracted with all fields populated
- [ ] Nash provides coherent opinions on each goal
- [ ] Conflicts are detected and surfaced
- [ ] Extracted goals can be confirmed and saved
- [ ] Conversation history persists in session
