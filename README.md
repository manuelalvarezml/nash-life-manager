# Nash Life Manager

A voice-first AI assistant for persistent memory, goals and human-approved scheduling.

**Status: active local prototype.** This repository is the committed development snapshot, not a hosted service. Personal recordings, databases and credentials are excluded.

## Engineering highlights

- **Voice and text ingestion:** local speech transcription, diary storage and streaming agent responses.
- **Persistent context:** structured memories and goals in SQLite, with local vector retrieval through Chroma.
- **Agent workflows:** FastAPI and LangGraph tools connect conversation to explicit application actions.
- **Scheduling with approval:** inferred actions stay as suggestions until approved; fixed commitments are protected and changes have an audit history.
- **Interface:** React and TypeScript views for diary, memory, goals, agenda and personal tracking.

Storage, audio, transcription and vector retrieval stay local. The default reasoning path uses the OpenAI API with pseudonymization; Ollama is an optional alternative. Local-first does not mean fully offline.

## Explore the code

- [API and application lifecycle](backend/main.py)
- [Agent graph](backend/agent/graph.py)
- [Calendar engine](backend/calendar_engine.py)
- [Persistence schema](backend/db/schema.py)
- [Frontend](frontend/src/App.tsx)
- [Environment and setup](ENVIRONMENT.md)
- [Calendar and memory architecture](docs/calendar_memory_engine.md)

Later local work includes a separate encrypted phone voice inbox. It is not deployed or integrated into this published snapshot.

Built by [Manuel Alvarez](https://manuelalvarez.cc/), an AI engineer focused on agents, Python backends, evaluation and reliable products.
