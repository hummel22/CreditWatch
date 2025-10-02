# Agent notes

Welcome to CreditWatch! This repository contains a FastAPI backend and a Vue 3 frontend. When extending the project:

- Keep Python code formatted and typed (the project uses SQLModel + Pydantic v2).
- Vue components follow the `<script setup>` composition API pattern.
- All persistent data lives in `backend/data` — avoid committing generated SQLite files.
- If you add new tooling, document it in the README.
- Run `pytest backend/tests` before sending your changes. The suite seeds mock data for benefit window scenarios that power Codex previews.

Refer to the `TODO.md` file for high-level roadmap items.
