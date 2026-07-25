# Phase 4: Self Profile Facts — Deep Research Synthesis

> **Date:** April 2026
> **Purpose:** Document research-backed schema for biographical/self-profile data that will serve as foundational context for Nash's advisory capabilities.

---

## 1. Research Sources Consulted

### Psychology & Identity
- **McAdams Life Story Interview** — Narrative identity protocol with chapters, nuclear episodes (high points, low points, turning points), imagoes, and life themes
- **Self-Concept Clarity Scale (Campbell et al., 1996)** — 12-item measure of how clearly/confidently one knows themselves
- **Erikson's Psychosocial Stages** — 8 developmental stages with core conflicts (identity vs. confusion, intimacy vs. isolation, etc.)
- **Attachment Theory** — Secure, anxious, avoidant patterns from early relationships

### Clinical & Therapeutic
- **Biopsychosocial Model** — Biological, psychological, social factors in health/wellbeing
- **ACEs (Adverse Childhood Experiences)** — 10-item questionnaire on childhood trauma (5 personal, 5 household)
- **Therapy Intake Protocols** — Presenting problems, mental health history, risk factors, social support
- **IFS (Internal Family Systems)** — Parts work, exiles, managers, firefighters

### Values & Culture
- **Schwartz Theory of Basic Values** — 10 universal values in circular structure (self-direction, stimulation, hedonism, achievement, power, security, conformity, tradition, benevolence, universalism)
- **Cultural Identity Assessment (CFI)** — Cultural background, identity, stressors, support systems
- **RESPECTFUL Model** — Religion, economic class, sexual identity, psychology, ethnicity, chronological, trauma, family, unique physical, location

### Life Domains & Coaching
- **Wheel of Life** — 8-10 domains (career, finance, health, relationships, personal growth, fun, physical environment, family)
- **7 Domains of Wellness** — Physical, social, occupational, emotional, intellectual, environmental, spiritual
- **Valued Living Questionnaire** — 10 key life domains with satisfaction ratings

### AI Personalization Research
- Current AI coaches use: personality assessments, real-time behavioral data, communication preferences, goals/challenges
- Effective personalization requires: individual attention, exploring psychological mechanisms, focus on life outside sessions, individualized assessment

---

## 2. Key Insights for Nash

### What Makes Context Effective for Advice

Research shows **85% of therapy outcome variance** comes from common factors (client characteristics, therapeutic relationship, empathy) rather than specific techniques. This means Nash needs:

1. **Deep client knowledge** — Not just demographics, but values, patterns, history
2. **Cultural context** — Background shapes how advice is received
3. **Relationship awareness** — Who matters to the user, relationship dynamics
4. **Life stage context** — Erikson stages, current developmental challenges
5. **Historical patterns** — How past experiences shape present reactions

### The Three Layers of Self-Knowledge

Based on research, self-knowledge operates at three levels:

| Layer | What It Contains | How Nash Uses It |
|-------|------------------|------------------|
| **Factual/Biographical** | Demographics, education, career, family structure, health conditions | Base context for all interactions |
| **Narrative/Experiential** | Key memories, turning points, formative experiences, life chapters | Understanding "why" behind patterns |
| **Values/Identity** | Core values, beliefs, self-concept, attachment style | Aligning advice with who user wants to be |

### McAdams Life Story Framework Relevance

The Life Story Interview provides structure for understanding identity:

- **Life Chapters** — Major periods (childhood, college years, career transition, etc.)
- **Nuclear Episodes** — High points, low points, turning points, earliest memory
- **Significant People** — Heroes, mentors, villains (connects to People table)
- **Life Theme** — Central message or meaning running through story
- **Imagoes** — Idealized self-images, role models

This maps well to Nash's semantic memory system — these are exactly the types of "semantic units" that should be extracted and indexed.

---

## 3. Validated Schema Design

Based on research, the `self_profile_facts` table should capture:

### 3.1 Core Demographics (Factual Layer)

```sql
-- Basic identity
birth_date DATE,
birth_place TEXT,  -- city, country
current_age INTEGER,  -- computed or stored
gender TEXT,
nationality TEXT,
ethnicities TEXT,  -- JSON array, can be multiple

-- Living situation
current_city TEXT,
current_country TEXT,
living_situation TEXT,  -- alone, partner, family, roommates
years_at_current_location REAL,
```

### 3.2 Family & Origins

```sql
-- Parents
mother_alive BOOLEAN,
mother_age INTEGER,
mother_occupation TEXT,
mother_relationship_quality TEXT,  -- close, distant, estranged, deceased

father_alive BOOLEAN,
father_age INTEGER,
father_occupation TEXT,
father_relationship_quality TEXT,

parents_relationship TEXT,  -- married, divorced, separated, widowed, never_married
childhood_family_structure TEXT,  -- nuclear, single_parent, extended, blended, etc.

-- Siblings
num_siblings INTEGER,
birth_order TEXT,  -- only, oldest, middle, youngest
sibling_details TEXT,  -- JSON array with name, age, relationship

-- Childhood context
childhood_socioeconomic TEXT,  -- low, lower_middle, middle, upper_middle, upper
childhood_location TEXT,
```

### 3.3 Education & Career

```sql
-- Education
highest_education TEXT,  -- high_school, bachelors, masters, doctorate, etc.
field_of_study TEXT,
schools_attended TEXT,  -- JSON array with name, years, degree

-- Career
current_occupation TEXT,
current_industry TEXT,
years_in_current_role REAL,
career_satisfaction INTEGER,  -- 1-10
job_history TEXT,  -- JSON array with role, company, years
```

### 3.4 Relationships

```sql
-- Current romantic
relationship_status TEXT,  -- single, dating, partnered, married, divorced, widowed
partner_name TEXT,
relationship_years REAL,
relationship_satisfaction INTEGER,  -- 1-10
has_children BOOLEAN,
num_children INTEGER,
children_details TEXT,  -- JSON array

-- Relationship history
num_significant_relationships INTEGER,
longest_relationship_years REAL,
age_first_relationship INTEGER,
relationship_patterns TEXT,  -- user reflection
```

### 3.5 Health & Body

```sql
-- Physical
height_cm REAL,
weight_kg REAL,
chronic_conditions TEXT,  -- JSON array
medications TEXT,  -- JSON array
allergies TEXT,  -- JSON array
disability_status TEXT,

-- Mental health
mental_health_history TEXT,  -- JSON array of conditions
currently_in_therapy BOOLEAN,
therapy_history TEXT,
psychiatric_medications TEXT,
```

### 3.6 Values & Identity (from Schwartz + research)

```sql
-- Core values (top 3-5 from Schwartz)
core_values TEXT,  -- JSON array: self_direction, achievement, benevolence, etc.

-- Beliefs
religious_spiritual TEXT,  -- none, spiritual_not_religious, [specific religion]
religious_practice_level TEXT,  -- not_practicing, occasional, regular, devout
political_orientation TEXT,  -- optional

-- Languages
native_language TEXT,
other_languages TEXT,  -- JSON array with language, proficiency

-- Personality (if known)
mbti_type TEXT,
big_five_scores TEXT,  -- JSON: {openness, conscientiousness, extraversion, agreeableness, neuroticism}
attachment_style TEXT,  -- secure, anxious, avoidant, disorganized
```

### 3.7 Life Story Elements (from McAdams)

```sql
-- Life chapters
life_chapters TEXT,  -- JSON array: {title, age_range, summary}

-- Nuclear episodes (stored as references or summaries)
earliest_memory_id INTEGER,  -- reference to memories table
high_point_ids TEXT,  -- JSON array of memory IDs
low_point_ids TEXT,
turning_point_ids TEXT,

-- Life theme
life_theme TEXT,  -- user's articulated central theme
life_theme_updated_at TEXT,
```

### 3.8 Adverse Experiences (ACEs-informed, optional/sensitive)

```sql
-- These are sensitive and optional
aces_score INTEGER,  -- 0-10 if user chooses to disclose
aces_details TEXT,  -- JSON, only if user explicitly shares
trauma_history TEXT,  -- general categories if disclosed
```

### 3.9 Assets & Practical

```sql
-- Financial (optional)
income_bracket TEXT,
owns_home BOOLEAN,
has_savings BOOLEAN,
financial_stress_level INTEGER,  -- 1-10

-- Practical
has_drivers_license BOOLEAN,
owns_vehicle BOOLEAN,
has_passport BOOLEAN,
```

---

## 4. Final Table Design

```sql
CREATE TABLE IF NOT EXISTS self_profile_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- SECTION: Core Identity
    birth_date TEXT,  -- ISO date
    birth_place TEXT,
    gender TEXT,
    nationality TEXT,
    ethnicities TEXT DEFAULT '[]',  -- JSON array

    -- SECTION: Current Situation
    current_city TEXT,
    current_country TEXT,
    living_situation TEXT,
    years_at_location REAL,

    -- SECTION: Family Origins
    mother_alive INTEGER,  -- 0/1/NULL
    mother_age INTEGER,
    mother_occupation TEXT,
    mother_relationship TEXT,  -- close, distant, complicated, estranged
    father_alive INTEGER,
    father_age INTEGER,
    father_occupation TEXT,
    father_relationship TEXT,
    parents_status TEXT,  -- married, divorced, separated, widowed
    childhood_structure TEXT,
    childhood_socioeconomic TEXT,
    childhood_location TEXT,
    num_siblings INTEGER,
    birth_order TEXT,
    siblings_json TEXT DEFAULT '[]',

    -- SECTION: Education
    highest_education TEXT,
    field_of_study TEXT,
    schools_json TEXT DEFAULT '[]',

    -- SECTION: Career
    current_occupation TEXT,
    current_industry TEXT,
    years_in_role REAL,
    career_satisfaction INTEGER,
    jobs_json TEXT DEFAULT '[]',

    -- SECTION: Relationships
    relationship_status TEXT,
    partner_name TEXT,
    relationship_years REAL,
    relationship_satisfaction INTEGER,
    has_children INTEGER,
    num_children INTEGER,
    children_json TEXT DEFAULT '[]',
    num_past_relationships INTEGER,
    longest_relationship_years REAL,
    age_first_relationship INTEGER,
    relationship_patterns_reflection TEXT,

    -- SECTION: Health
    height_cm REAL,
    weight_kg REAL,
    chronic_conditions_json TEXT DEFAULT '[]',
    medications_json TEXT DEFAULT '[]',
    allergies_json TEXT DEFAULT '[]',
    mental_health_history_json TEXT DEFAULT '[]',
    in_therapy INTEGER,
    attachment_style TEXT,

    -- SECTION: Values & Identity
    core_values_json TEXT DEFAULT '[]',
    religious_spiritual TEXT,
    religious_practice TEXT,
    native_language TEXT,
    languages_json TEXT DEFAULT '[]',
    mbti TEXT,
    big_five_json TEXT,

    -- SECTION: Life Story (McAdams)
    life_chapters_json TEXT DEFAULT '[]',
    life_theme TEXT,

    -- SECTION: Context & Preferences
    preferred_name TEXT,
    pronouns TEXT,
    timezone TEXT,
    communication_style TEXT,  -- direct, gentle, analytical, etc.

    -- SECTION: Financial (optional)
    income_bracket TEXT,
    owns_home INTEGER,
    financial_stress INTEGER,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    completeness_score REAL DEFAULT 0.0,
    last_review_prompt TEXT  -- when Nash last asked to fill gaps
);

-- Index for quick access
CREATE INDEX IF NOT EXISTS idx_self_profile_updated ON self_profile_facts(updated_at);
```

---

## 5. Completeness Tracking

Track which fields are filled to enable Nash to ask about gaps:

```python
REQUIRED_FIELDS = [
    'birth_date', 'current_city', 'current_country', 'living_situation',
    'highest_education', 'current_occupation', 'relationship_status',
]

RECOMMENDED_FIELDS = [
    'mother_relationship', 'father_relationship', 'childhood_socioeconomic',
    'core_values_json', 'attachment_style', 'life_theme',
]

OPTIONAL_SENSITIVE = [
    'mental_health_history_json', 'income_bracket', 'relationship_patterns_reflection',
]
```

Completeness score = (filled_required / total_required) * 0.6 + (filled_recommended / total_recommended) * 0.4

---

## 6. How This Feeds Agent Context

### 6.1 Profile Context Builder

When Nash responds, include relevant biographical context:

```python
def build_profile_context(user_message: str) -> str:
    profile = get_self_profile()

    # Always include basics
    context = f"""
PERFIL DE MANUEL:
- Edad: {calculate_age(profile.birth_date)} años
- Vive en: {profile.current_city}, {profile.current_country}
- Ocupación: {profile.current_occupation}
- Situación: {profile.relationship_status}
"""

    # Add relevant sections based on conversation topic
    if mentions_family(user_message):
        context += build_family_context(profile)

    if mentions_work(user_message):
        context += build_career_context(profile)

    if mentions_relationship(user_message):
        context += build_relationship_context(profile)

    # Always include values and communication preference
    context += f"""
- Valores core: {', '.join(profile.core_values)}
- Estilo comunicación preferido: {profile.communication_style}
"""

    return context
```

### 6.2 Advisory Phase Integration

In later phases, this data enables:

1. **Goals Module (Phase 3)** — Suggest goals aligned with values, consider career/relationship context
2. **Body Module (Phase 5)** — Account for health conditions, medications
3. **Finance Module (Phase 6)** — Contextualize with income bracket, financial stress
4. **Dashboard (Phase 7)** — Show life stage context, track progress against life theme

### 6.3 Question Engine Enhancement

The QuestionEngine can use profile gaps to prioritize questions:

```python
def get_priority_domains():
    profile = get_self_profile()
    gaps = []

    if not profile.life_theme:
        gaps.append('narrative')  # Ask about life theme

    if not profile.core_values_json:
        gaps.append('values')  # Explore what matters

    if not profile.attachment_style:
        gaps.append('relationships')  # Understand patterns

    return gaps
```

---

## 7. UI Design: "Sobre Mí" Tab

### 7.1 Layout

```
┌─────────────────────────────────────────────────────────┐
│  Sobre Mí                           [Completeness: 45%] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ 🎂 Identidad    │  │ 👨‍👩‍👧 Familia      │              │
│  │ ░░░░░░░░▓▓ 80%  │  │ ░░░░▓▓▓▓▓▓ 60%  │              │
│  └─────────────────┘  └─────────────────┘              │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ 🎓 Educación    │  │ 💼 Carrera      │              │
│  │ ░░░░░░░░░▓ 90%  │  │ ░░░░░░▓▓▓▓ 40%  │              │
│  └─────────────────┘  └─────────────────┘              │
│                                                         │
│  [Editar directamente]  [Nash me pregunta]             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Input Methods

1. **Direct Form** — Click section → form with all fields
2. **Guided Questions** — Nash asks one field at a time with context
3. **Conversation Extraction** — Nash detects and suggests: "Mencionaste que naciste en Monterrey. ¿Quieres que lo guarde en tu perfil?"

---

## 8. Privacy & Sensitivity

### Handling Sensitive Data

- **ACEs/Trauma** — Only ask if user initiates topic; store minimally
- **Mental Health** — Clearly optional; useful for context but never required
- **Financial** — Brackets only, not exact figures
- **All data** — Stored locally in SQLite, never transmitted

### User Control

- User can view/edit all stored data
- User can delete specific fields
- Export entire profile as JSON
- Clear all profile data option

---

## 9. Implementation Order

1. **Schema** — Create `self_profile_facts` table
2. **API** — GET/PATCH endpoints for profile
3. **Basic UI** — "Sobre Mí" tab with section cards
4. **Form Entry** — Direct edit capability
5. **Guided Mode** — Nash asks questions to fill gaps
6. **Extraction** — Agent detects biographical info in conversations
7. **Context Integration** — Feed profile into agent system prompt

---

## 10. Research Sources

- [McAdams Life Story Interview II (Northwestern)](https://cpb-us-e1.wpmucdn.com/sites.northwestern.edu/dist/4/3901/files/2020/11/The-Life-Story-Interview-II-2007.pdf)
- [Self-Concept Clarity Scale (Campbell et al., 1996)](https://psycnet.apa.org/record/1996-01707-011)
- [Schwartz Theory of Basic Values](https://www.sciencedirect.com/topics/psychology/schwartz-theory-of-basic-values)
- [ACEs Questionnaire (CDC)](https://www.cdc.gov/violenceprevention/aces/index.html)
- [Biopsychosocial Model (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4448138/)
- [Wheel of Life Categories (Jay Shetty)](https://www.jayshettycoaching.com/blog/wheel-of-life-categories)
- [7 Domains of Wellness](https://www.addictionpolicy.org/post/7-domains-of-wellness)
- [Life Domains (Positive Psychology)](https://positivepsychology.com/what-are-life-domains/)
- [Person-Centered Therapy (NCBI)](https://www.ncbi.nlm.nih.gov/books/NBK589708/)
- [Treatment Personalization in Mental Health (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11379769/)

---

*End of Phase 4 Research Document*
