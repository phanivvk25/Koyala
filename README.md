<p align="center">
  <img src="docs/assets/koyala-banner.png" alt="Koyala — An AI-assisted mental health companion. Chat confidentially · Feel better every day · Build healthy habits · A brighter you. You're not alone." width="100%">
</p>

<h1 align="center">Koyala</h1>
<p align="center"><b>An AI-assisted mental health companion</b><br>
Chat confidentially · Feel better every day · Build healthy habits · A brighter you</p>

> **Koyala is not an emergency service.** If you are in crisis in India, call Tele-MANAS **14416** or emergency **112**.

Koyala offers private, culturally aware, evidence-based emotional support in English and Indian languages, with crisis detection built in and a bridge to human counsellors when it matters.

## Status

**Backend MVP — not ready for real users.** Crisis content, helplines, exercises and the risk word list are placeholders awaiting clinical sign-off; the crisis partner, paging and push notifications are stubs. See the [Roadmap](https://github.com/phanivvk25/Koyala/wiki/Roadmap).

## What's built

- **Safety first** — every message is risk-checked before any reply; high-risk messages get fixed, clinician-owned crisis responses (the AI never improvises them), helplines and a "talk to a counsellor" handoff.
- **Conversation** — Claude-backed replies with personal details removed before sending, and checks that block diagnoses, medication advice and claims to be human.
- **Self-help** — guided exercises, PHQ-9 / GAD-7 / WHO-5, mood log, journal (with private entries), safety plan.
- **Care continuity** — follow-up check-ins after elevated risk; on-call alerts when no one responds.
- **Privacy by design** — anonymous accounts, per-user encryption, full data export and instant account deletion.

## Quick start

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" uvicorn
pytest -q
uvicorn koyala.main:app --reload   # API docs at http://localhost:8000/docs
```

More: [Getting Started](https://github.com/phanivvk25/Koyala/wiki/Getting-Started) · [Configuration](https://github.com/phanivvk25/Koyala/wiki/Configuration) · [API Reference](https://github.com/phanivvk25/Koyala/wiki/API-Reference)

## Documentation

- **[Wiki](https://github.com/phanivvk25/Koyala/wiki)** — how to run, configure and contribute (source in [`wiki/`](wiki/))
- **[`docs/`](docs/README.md)** — product and technical specification (MRD, BRD, PRD, TDD, AI model spec, clinical safety protocol, compliance)
- **[`backend/README.md`](backend/README.md)** — backend details
