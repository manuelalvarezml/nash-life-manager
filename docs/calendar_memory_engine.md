# Calendar and Memory Engine - Architecture, Decisions, and Learning Log

> Date: August 27, 2026
> Status: Calendar Engine V1 and Structured Memory Archive V1 shipped

## Product Intent

The schedule is not a generic productivity calendar. It is the place where Nash turns values,
goals, health plans, financial obligations, and direct life events into realistic commitments.
It should reduce cognitive load without taking control away from the user.

The diary remains the primary capture surface. A five-minute entry may contain feelings,
memories, patterns, goals, and concrete actions. Nash must preserve those sections separately
without forcing the user to speak in a rigid format.

## Central Design Decision: Three Layers

1. `schedule_inputs` stores the original instruction and the interpretation/result audit trail.
2. `calendar_suggestions` stores proposals that are not commitments yet.
3. `calendar_items` and `calendar_series` store accepted commitments and recurring rules.

This separation is intentional. A diary sentence such as "I should call the dentist" should
not silently become a promise. It becomes a suggestion with approve, edit, and delete controls.
A direct calendar mandate such as "move the video to Friday" can be applied immediately.

## Canonical Calendar Model

### `schedule_preferences`

Stores the realistic planning envelope: timezone, day start/end, focus window, transition buffer,
default task duration, and maximum scheduled minutes per day.

### `schedule_inputs`

Stores direct text/audio commands, the normalized command type, interpretation JSON, processing
status, and result. This is the debugging/audit source for future improvements to language
understanding.

### `calendar_series`

Stores recurring commitments independently from generated occurrences. Rules support daily,
weekly, and monthly frequency, explicit weekdays, times per week, interval, and end date.

### `calendar_items`

Stores concrete occurrences and one-time commitments. Important fields include source,
source entity, linked goal, priority, fixed/movable/free flexibility, energy, location, status,
rationale, and metadata. Every mutation writes a `calendar_item_history` record.

### `calendar_suggestions`

Stores proposals from diary actions and engine adapters. A stable fingerprint prevents the same
goal/workout/bill from being proposed repeatedly after approval or rejection.

## Scheduling Behavior

- Explicit date/time commitments are preserved even if they create a conflict. The conflict is
  shown instead of silently changing what the user said.
- Unscheduled work uses deterministic free-slot search inside the configured day boundaries.
- Daily capacity and transition buffers limit fantasy planning.
- Bulk replanning only moves `movable` and `free` items. `fixed` events remain protected.
- Recurrence materialization is idempotent: opening the agenda twice does not duplicate instances.
- Accepted items and pending suggestions are kept distinct in Nash's reasoning context.

## Cross-Engine Contribution Contract

The calendar engine currently has standardized adapters for:

- Goals: active `system` and `action` nodes become one-time or recurring proposals.
- Body: the workout profile contributes the preferred weekly training frequency and duration.
- Finance: fixed expenses with a due day become monthly reminder proposals.
- Diary: explicit `action_item` semantic units become approval-required suggestions.

Nutrition currently contributes no automatic blocks because meal reminders would be an invented
preference unless the user explicitly asks for them. The adapter boundary is ready when eating
windows or meal plans become actionable schedule rules.

## Diary Classification

`SemanticDecomposer` now recognizes `action_item` separately from vague `intention`. This avoids
turning aspirations into obligations. The same classification pass extracts richer metadata for:

- memories: title, age/range, explicit year/range, place, people, themes, emotional valence,
  memory type, significance, sensory detail, and confidence;
- actions: title, date, time, estimated duration, recurrence, priority, and flexibility.

Relative dates are defended locally. If the model preserves "4 PM" but omits "tomorrow," a
deterministic resolver uses words such as `hoy`, `manana`, `pasado manana`, and weekday names.

## Structured Memory Archive

The legacy `memories` table was expanded instead of replaced so old rows remain valid. Existing
`semantic_units` of type `memory` are promoted into the archive on migration while preserving
their original records.

If the user gives an age but no year, Nash computes a possible year range locally from
`self_profile_facts.birth_date`:

- start year = birth year + starting age;
- end year = birth year + ending age + 1.

The extra year represents the fact that a stated age usually spans parts of two calendar years.
An explicit year always takes priority. Inferred fields remain editable and can be marked as
user-verified.

## Privacy Boundary

- Audio is transcribed locally through the existing Parakeet path.
- Calendar command text and diary classification prompts pass through the existing outbound
  pseudonymization before OpenAI calls.
- Calendar data, raw audio, accepted commitments, memory records, and audit history stay local.
- Agent tool descriptions were changed to remove the owner's real name because tool schemas are
  also sent to the remote model and are outside normal message sanitization.

## Alternatives Considered

### One table for everything

Rejected because proposed diary actions would be indistinguishable from commitments and recurring
rules would be awkward to edit safely.

### LLM-only scheduling

Rejected for free-slot selection, recurrence expansion, capacity limits, and bulk rearrangement.
The LLM interprets language; deterministic code applies time and safety rules.

### Automatically accept all goal/workout contributions

Rejected for V1. A goal is not yet evidence that the user consents to a specific weekly schedule.
The suggestion inbox provides the missing consent boundary.

### Store only memory prose

Rejected because age/year/place/people/theme fields enable chronological retrieval, pattern
analysis, and future personal timelines without repeatedly asking the model to re-extract facts.

## Hypotheses to Test in Real Use

1. The suggestion inbox reduces forgotten diary actions without becoming another overwhelming list.
2. A maximum daily planning envelope produces schedules the user actually follows more often.
3. Stable recurring workout blocks improve adherence when paired with the existing home rescue plan.
4. Source labels help the user notice whether calendar time reflects stated goals or only urgent events.
5. Manual correction and verification improve memory metadata enough to support later life-pattern analysis.

## Known Limitations and Future Paths

- There is no Google/Apple calendar synchronization yet. Local-first behavior is deliberate for
  this stage; external calendar conflict merging needs a separate privacy and authority decision.
- Updating an engine profile after its proposal has been approved does not yet rewrite the accepted
  series automatically. Future synchronization needs a visible change proposal, not silent mutation.
- Named-event resolution returns candidates when more than one item matches. A dedicated chooser
  can make this smoother than asking for a more specific command.
- Monthly recurrence currently normalizes end-of-month dates conservatively. A future rule should
  explicitly represent "last day of month."
- Diary actions have estimated duration from the model. Real completion durations should become
  feedback for source/task-specific duration calibration.
- The week view supports direct time editing but not drag-and-drop. Voice/text rearrangement is the
  primary control in V1.
- A later readiness layer can combine sleep, emotional state, workout recovery, and workload while
  preserving the fixed/movable boundary.

## Validation Record

- Additive migration applied after backing up `~/.nash/nash.db` to
  `~/.nash/nash-before-calendar-2026-08-27.db`.
- Backend compile passed.
- Frontend production build passed.
- Real OpenAI command interpretation converted a next-day fixed event to the correct local ISO time.
- Diary decomposition split one transcript into both `memory` and `action_item` records.
- Local age-to-year calculation and relative-date fallback passed.
- Suggestion approval, recurring idempotency, API routes, and cross-engine adapters passed smoke tests.
