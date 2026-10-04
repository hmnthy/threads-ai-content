# Unthreaded

**Language:** English · [Tiếng Việt](README.vi.md) · [Français](README.fr.md)

![Status](https://img.shields.io/badge/status-in%20progress-orange)
![Tests](https://img.shields.io/badge/tests-397%20passing-brightgreen)
![License](https://img.shields.io/badge/license-private-lightgrey)

> The algorithm, read back to you.

Threads' ranking algorithm is a black box — creators can't query why one post takes off and the
next one doesn't. This project treats one real Threads channel, **[@thydilammuon](https://www.threads.net/@thydilammuon)**
(a Vietnamese creator living in France, posting about *alternance*, job hunting, and expat life),
as a live case study: every number on the dashboard is computed from a documented, cited formula —
never a black-box score.

It is a working **analytics + NLP research project** for that one channel, heading toward a
continuously updated **knowledge base** of what the channel has already taught its followers —
built and open-sourced-in-spirit as an NLP/ML engineering portfolio piece. Not a SaaS, not
multi-tenant, not trying to be.

---

## Screenshots

The product in four steps — from the pitch to the raw discovered topics.

<p align="center">
  <img src="docs/screenshots/landing.png" alt="Landing page: hero, problem, solution, tech stack" width="820"><br>
  <sub><b>1. Landing</b> — the pitch, the problem, and the three-layer solution (statistics → NLP → knowledge base), plus the full tech stack shown with its real status.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/overview.png" alt="Overview tab: KPI strip and Timeline Brush" width="820"><br>
  <sub><b>2. Overview</b> — median-first KPI strip, the daily-views chart with the drag-to-rescale Timeline Brush, and the top content units in the selected window.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/analytics.png" alt="Analytics tab: top posts and timezone breakdown" width="820"><br>
  <sub><b>3. Analytics</b> — top posts by engagement/virality/conversation, and posting-time performance broken down by both Europe/Paris and Asia/Ho_Chi_Minh.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/topics.png" alt="Topic Explorer: 3D UMAP scatter of discovered topics" width="820"><br>
  <sub><b>4. Topic Explorer</b> — unsupervised topic clusters (UMAP 3D + HDBSCAN) discovered from the channel's own post history.</sub>
</p>

---

## Table of contents

- [The problem](#the-problem)
- [How it's solved](#how-its-solved)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Methodology highlights](#methodology-highlights)
- [Project status](#project-status)
- [Local setup](#local-setup)
- [About the channel](#about-the-channel)
- [License](#license)

---

## The problem

Threads gives creators just enough data to make confident-sounding, unfounded decisions.

- **No real analytics depth.** Threads' own Insights expose `views`, `likes`, `replies`, `reposts`
  and `quotes` — no impressions, no reach, no shares, no timezone breakdown. Creators are left
  estimating.
- **No topic-level insight.** Every post is judged in isolation. There's no built-in way to see
  which subjects, told which way, actually perform better across a channel's real history.
- **No statistically honest reporting.** A single viral post drags a mean far above what a typical
  post looks like, and a 2-post "best hour" bucket gets reported with the same confidence as a
  50-post one.

## How it's solved

Three layers, built in that order — each grounded in cited methodology, not intuition.

| Layer | Status | What it does |
|---|---|---|
| **Statistics layer** | Live | Six intrinsic indices kept separate — popularity, engagement, virality, conversation, velocity, longevity — never blended into one score. Median and mean reported together (never a lone mean), IQR and sample-size flags on every bucket, Mann-Whitney U + Cliff's delta for any group comparison, per-channel percentile-relative virality instead of an arbitrary fixed threshold. |
| **NLP layer** | Live | Multilingual sentence embeddings (content mixes Vietnamese, French and English naturally, so no per-language tokenizer) feed UMAP + HDBSCAN for unsupervised topic discovery, then Claude labels each discovered cluster in English. A Code-Mixing Index — a continuous score, not a boolean flag — measures how much a post actually switches languages. |
| **Knowledge base** | Next | The channel's own posts and the author's answers to follower questions, turned into a searchable knowledge base: hybrid keyword (BM25) + semantic retrieval with a reranker, evaluated against real follower questions (recall@k, MRR, nDCG) before anything — such as a Q&A assistant — is built on top of it. |

## Tech stack

Shown as it actually stands today — nothing implied that isn't built yet.

| Layer | Technology | Status |
|---|---|---|
| Backend / API | FastAPI | Live |
| Package manager | uv (`pyproject.toml` + `uv.lock`) | Live |
| Threads API client | httpx (async) | Live |
| Validation | Pydantic v2 | Live |
| AI / LLM | Claude API (`claude-sonnet-5-5`, cluster labeling) | Live |
| Dashboard | Next.js 16 + Tailwind v4, hand-built SVG charts + Plotly (topic map) | Live |
| Database | SQLite — one file, one writer; the knowledge base will live in it too | Live |
| Metric scoring | 6-index architecture (popularity/engagement/virality/conversation/velocity/longevity) | Live |
| Language ID | lingua-py + Code-Mixing Index | Live |
| NLP feature extraction | sentence-transformers, multilingual (bge-m3 / multilingual-e5-large) | Live |
| Topic discovery | UMAP + HDBSCAN (unsupervised clustering) | Live |
| Code quality | ruff (lint+format), mypy (strict), pytest, pre-commit | Live |
| Fixed-category classification | SVM-RBF + Logistic Regression (baseline ladder vs. the unsupervised clusters) | Research, not started |
| Knowledge base retrieval | SQLite FTS5 (BM25) + dense embeddings + cross-encoder reranker | Next |

## Architecture

```
threads-ai-content/
├── src/
│   ├── api/            Threads Graph API client (auth, pagination, caching) — live
│   ├── models/          ContentUnit / InsightSnapshot domain models — live
│   ├── processing/       thread reconstruction (root + self-reply chains), text cleaning — live
│   ├── analysis/         6-index metric scoring + windowed statistics (median/mean/IQR) — live
│   ├── nlp/              language ID, multilingual embeddings, UMAP+HDBSCAN clustering — live
│   ├── db/                SQLite schema (posts, content_units, insights_snapshots, topics, embeddings, cluster_runs) — live
│   ├── pipeline/           ingest, 4h snapshot cron, Windows↔WSL2 clustering bridge — live
│   ├── main.py             FastAPI entry point — live
│   └── dashboard/          Next.js app: landing page + Overview/Analytics/Topic Explorer — live
└── tests/                pytest suite, ruff + mypy strict clean
```

Data flow, end to end:

```
Threads Graph API  ──(4h cron)──>  SQLite  ──>  FastAPI  ──>  Next.js dashboard
        │                              │
        └── posts, replies,            └── NLP pipeline (WSL2: embeddings, UMAP, HDBSCAN)
            account daily views            re-clusters daily, Claude labels clusters
```

The batch ML pipeline (embeddings, clustering) runs as a separate job that writes to SQLite —
FastAPI only ever reads precomputed results, it never loads a transformer model per request.

## Methodology highlights

A few decisions this project treats as load-bearing, each recorded in
[`docs/decisions/`](docs/decisions/) (one file per decision) and
[`docs/claude/data-model.md`](docs/claude/data-model.md):

- **Median-as-headline, mean-as-secondary — never a pooled ratio.** A single windowed
  Σinteractions/Σviews ratio is dominated by whichever post got the most views; median across posts
  is reported first everywhere, with mean, sample size (`n`) and an IQR shown alongside it.
- **Six indices, never one blended score.** Popularity, engagement, virality, conversation,
  velocity and longevity answer different questions and are never averaged together into a single
  "score."
- **Every heuristic constant is either derived from real data or explicitly labeled as an
  uncalibrated hypothesis** — no unlabeled magic numbers.
- **Clustering space chosen by experiment, not by theory.** HDBSCAN was tried on both the raw
  1024-D embedding space and the UMAP-reduced space; raw-embedding space degenerated (one cluster
  absorbing 82% of the data), UMAP space produced stable, balanced clusters — the empirical result
  overrode the original design assumption. Full numbers in `data-model.md`.
- **Code-mixing is a continuous score, not a boolean.** Following the code-switching NLP
  literature, document-level language ID on short text is unreliable and shouldn't gate downstream
  pipeline steps — the Code-Mixing Index quantifies *how much* a post mixes languages instead of
  classifying it into one.

## Project status

**Live:** Threads API client, NLP topic-discovery pipeline, 6-index metric architecture, windowed
statistics, and a three-tab dashboard (Overview, Analytics, Topic Explorer) plus this landing page,
all running against real production data (full test suite passing, ruff + mypy strict clean).

**Next — deliberately narrow scope ("less is more"):**
1. Deeper NLP analysis written up as explicit research questions (cluster stability, embedding
   model comparison, code-mixing vs. engagement, a supervised classifier baseline ladder).
2. A continuously updated knowledge base with measured retrieval quality.
3. Only once that knowledge base passes its quality gate: a Q&A assistant grounded in it, and a
   brand landing page for the channel.

<!-- consistency: allow ADR0001-generation ADR0001-carousel ADR0001-image-gen -->
Voice-matched post generation and carousel image generation were considered and deliberately
dropped to keep the project focused.

## Local setup

```bash
# Backend (Python 3.12 via uv)
pip install --user uv
uv sync
uv run pre-commit install          # commit gates: lint, types, consistency, fast tests
cp .env.example .env               # fill in THREADS_* and ANTHROPIC_API_KEY
uv run pytest -q                   # full test suite (~1 min)
uv run uvicorn src.main:app --reload --port 8000

# Dashboard (Next.js)
cd src/dashboard
npm install
npm run dev                        # http://localhost:3000
```

The dashboard reads live data from the FastAPI backend above — both need to be running locally to
see real numbers.

## About the channel

Built by Thy ([@thydilammuon](https://www.threads.net/@thydilammuon)), a Vietnamese creator living
and working in France who posts about *alternance*, job hunting, and everyday life as an expat.
This project started as a way to actually understand her own channel — not vanity metrics, but a
rigorous look at what her real posts do — and grew into the full statistics + NLP case study
described above.

## License

Private personal project. All rights reserved — not open source, not accepting external
contributions. Built as a portfolio piece demonstrating applied NLP/ML engineering on real
production data.

Not affiliated with Meta. Threads is a trademark of Meta Platforms, Inc. The repository keeps its
working slug `threads-ai-content`.
