# Threads AI Content

**Langue :** [English](README.md) · [Tiếng Việt](README.vi.md) · Français

![Status](https://img.shields.io/badge/status-Phase%201%20in%20progress-orange)
![Tests](https://img.shields.io/badge/tests-183%20passing-brightgreen)
![License](https://img.shields.io/badge/license-private-lightgrey)

> The algorithm, read back to you.
> (L'algorithme, relu à voix haute.)

L'algorithme de classement de Threads est une boîte noire — les créateurs n'ont aucun moyen de
comprendre pourquoi une publication décolle et la suivante non. Ce projet prend un vrai compte
Threads, **[@thydilammuon](https://www.threads.net/@thydilammuon)** (une créatrice vietnamienne
vivant en France, qui parle d'alternance, de recherche d'emploi et de vie d'expatriée), comme cas
d'étude en conditions réelles : chaque chiffre affiché sur le dashboard provient d'une formule
documentée et citée — jamais d'un score « boîte noire ».

C'est un **outil interne d'analyse (et bientôt de génération de contenu)** dédié à ce seul compte,
construit en parallèle comme pièce de portfolio d'ingénierie NLP/ML. Ce n'est pas un SaaS, pas
multi-tenant, et ça n'a pas vocation à le devenir.

---

## Captures d'écran

> Les trois images ci-dessous pointent vers `docs/screenshots/` mais ne sont **pas encore
> commitées** — ce dépôt est privé et les captures doivent être prises depuis une session
> `npm run dev` en cours d'exécution avant le premier push. Voir
> [Installation en local](#installation-en-local).

| Landing / page de présentation | Overview — Timeline Brush | Analytics — répartition par fuseau horaire |
|---|---|---|
| ![Landing page](docs/screenshots/landing.png) | ![Overview dashboard](docs/screenshots/overview.png) | ![Analytics tab](docs/screenshots/analytics.png) |

---

## Sommaire

- [Le problème](#le-problème)
- [La solution](#la-solution)
- [Stack technique](#stack-technique)
- [Architecture](#architecture)
- [Points forts de la méthodologie](#points-forts-de-la-méthodologie)
- [État du projet](#état-du-projet)
- [Installation en local](#installation-en-local)
- [À propos du compte](#à-propos-du-compte)
- [Licence](#licence)

---

## Le problème

Threads ne donne aux créateurs que juste assez de données pour prendre des décisions qui *sonnent*
sûres d'elles, sans réelle base.

- **Pas de véritable profondeur analytique.** Les Insights de Threads exposent `views`, `likes`,
  `replies`, `reposts` et `quotes` — pas d'impressions, pas de reach, pas de répartition par fuseau
  horaire. Les créateurs en sont réduits à deviner.
- **Aucune analyse au niveau des sujets.** Chaque publication est jugée isolément. Rien ne permet
  nativement de voir quels sujets, racontés de quelle façon, performent réellement mieux sur
  l'historique complet d'un compte.
- **Des rapports statistiquement malhonnêtes.** Une seule publication virale tire la moyenne loin
  au-dessus de ce à quoi ressemble une publication typique, et un « meilleur créneau horaire »
  basé sur 2 publications est rapporté avec la même confiance qu'un créneau basé sur 50.

## La solution

Trois couches, construites et vérifiées dans cet ordre — chacune ancrée dans une méthodologie
citée, jamais dans l'intuition.

| Couche | Statut | Ce qu'elle fait |
|---|---|---|
| **Couche statistique** | En ligne | Six indices intrinsèques gardés séparés — popularité, engagement, viralité, conversation, vélocité, longévité — jamais fusionnés en un seul score. Médiane et moyenne toujours rapportées ensemble (jamais une moyenne seule), IQR et alerte de taille d'échantillon sur chaque groupe, test de Mann-Whitney U + delta de Cliff pour toute comparaison de groupes, viralité calculée en percentile propre à chaque compte plutôt qu'avec un seuil fixe arbitraire. |
| **Couche NLP** | En ligne | Des embeddings de phrases multilingues (le contenu mélange naturellement vietnamien, français et anglais, donc aucun tokenizer propre à une langue) alimentent UMAP + HDBSCAN pour une découverte de sujets non supervisée, puis Claude nomme chaque cluster découvert en anglais. Un Code-Mixing Index — un score continu, pas un simple booléen — mesure à quel point une publication mélange réellement les langues. |
| **IA générative + RAG** | Bientôt disponible | Claude nomme déjà les clusters de sujets. La prochaine couche proposera de nouvelles idées de publications, ancrées — via une recherche dans les contenus les plus performants du compte — dans le ton réel et documenté de l'autrice, pas dans une voix IA générique. |

## Stack technique

Affichée exactement dans l'état réel du code aujourd'hui — rien n'est présenté comme prêt s'il ne
l'est pas.

| Couche | Technologie | Statut |
|---|---|---|
| Backend / API | FastAPI | En ligne |
| Gestionnaire de paquets | uv (`pyproject.toml` + `uv.lock`) | En ligne |
| Client API Threads | httpx (async) | En ligne |
| Validation | Pydantic v2 | En ligne |
| IA / LLM | Claude API (`claude-opus-5`, nommage des clusters + prompt caching) | En ligne |
| Dashboard | Next.js 16 + Tailwind v4 + Recharts | En ligne |
| Base de données | SQLite (dev) → PostgreSQL (prévu avant tout usage multi-utilisateur) | En ligne (dev) |
| Scoring des métriques | Architecture à 6 indices (popularité/engagement/viralité/conversation/vélocité/longévité) | En ligne |
| Détection de langue | lingua-py + Code-Mixing Index | En ligne |
| Extraction de features NLP | sentence-transformers, multilingue (bge-m3 / multilingual-e5-large) | En ligne |
| Découverte de sujets | UMAP + HDBSCAN (clustering non supervisé) | En ligne |
| Qualité du code | ruff (lint+format), mypy (strict), pytest, pre-commit | En ligne |
| Classification à catégories fixes | SVM-RBF + Régression logistique | Bientôt disponible |
| Vector store / RAG | Chroma ou FAISS (réutilise les embeddings du clustering) | Bientôt disponible |
| Génération d'images | Pillow + police Google Sans (templates carousel prêts, code non écrit) | Bientôt disponible |

## Architecture

```
threads-ai-content/
├── src/
│   ├── api/            Client Threads Graph API (auth, pagination, cache) — en ligne
│   ├── models/          Modèles de domaine ContentUnit / InsightSnapshot — en ligne
│   ├── processing/       Reconstruction des threads (racine + chaîne de self-reply), nettoyage texte — en ligne
│   ├── analysis/         Scoring 6 indices + statistiques par fenêtre temporelle (médiane/moyenne/IQR) — en ligne
│   ├── nlp/              Détection de langue, embeddings multilingues, clustering UMAP+HDBSCAN — en ligne
│   ├── db/                Schéma SQLite (posts, content_units, insights_snapshots, topics) — en ligne
│   ├── pipeline/           Ingestion, cron de snapshot toutes les 4h, pont de clustering Windows↔WSL2 — en ligne
│   ├── generation/         Génération de texte via RAG — non commencé
│   ├── carousel/           Composition d'images carousel avec Pillow — non commencé
│   ├── main.py             Point d'entrée FastAPI — en ligne
│   └── dashboard/          App Next.js : landing page + Overview/Analytics/Topic Explorer — en ligne
└── tests/                183 tests, ruff + mypy strict propres
```

Flux de données, de bout en bout :

```
Threads Graph API  ──(cron 4h)──>  SQLite  ──>  FastAPI  ──>  Dashboard Next.js
        │                              │
        └── posts, replies,            └── Pipeline NLP (WSL2 : embeddings, UMAP, HDBSCAN)
            vues quotidiennes              re-clusterise chaque jour, Claude nomme les clusters
```

Le pipeline ML batch (embeddings, clustering) tourne comme un job séparé qui écrit dans SQLite —
FastAPI ne fait que lire des résultats précalculés, il ne charge jamais de modèle transformer par
requête.

## Points forts de la méthodologie

Quelques décisions considérées comme structurantes pour ce projet, documentées intégralement dans
[`docs/claude/architecture.md`](docs/claude/architecture.md) et
[`docs/claude/data-model.md`](docs/claude/data-model.md) :

- **Médiane en chiffre principal, moyenne en secondaire — jamais un ratio agrégé.** Un ratio
  Σinteractions/Σvues calculé sur toute une fenêtre temporelle est dominé par la publication ayant
  le plus de vues ; la médiane entre publications est toujours rapportée en premier, accompagnée
  de la moyenne, de la taille d'échantillon (`n`) et de l'IQR.
- **Six indices, jamais un seul score fusionné.** Popularité, engagement, viralité, conversation,
  vélocité et longévité répondent à des questions différentes et ne sont jamais moyennés en un
  seul « score ».
- **Toute constante heuristique est soit dérivée de données réelles, soit explicitement étiquetée
  comme hypothèse non calibrée** — aucun nombre magique sans étiquette.
- **L'espace de clustering a été choisi par expérimentation, pas par théorie.** HDBSCAN a été
  testé à la fois sur l'espace d'embedding brut (1024 dimensions) et sur l'espace réduit par UMAP —
  l'espace brut dégénérait (un cluster absorbant 82 % des données), l'espace UMAP produisait des
  clusters stables et équilibrés — le résultat empirique a prévalu sur l'hypothèse de conception
  initiale. Chiffres complets dans `data-model.md`.
- **Le mélange de langues est un score continu, pas un booléen.** Conformément à la littérature
  NLP sur le code-switching, la détection de langue au niveau du document sur du texte court n'est
  pas fiable et ne devrait pas conditionner les étapes suivantes du pipeline — le Code-Mixing
  Index quantifie *à quel point* une publication mélange les langues plutôt que de la classer en
  binaire.

## État du projet

**Phase 1 — outil d'analyse + contenu pour un seul compte (en cours).** Client API Threads,
pipeline NLP de découverte de sujets, architecture à 6 indices, statistiques par fenêtre
temporelle, et un dashboard à 3 onglets (Overview, Analytics, Topic Explorer) plus cette landing
page tournent en conditions réelles sur des données de production (183 tests passants, ruff + mypy
strict propres). La génération de contenu par IA (`src/generation/`) et l'export d'images carousel
(`src/carousel/`) sont conçus mais pas encore construits.

**Phase 2 — recherche sur l'écosystème Threads / « KOL Strategy Engine » (orientation, non
engagée).** Étendre l'analyse d'un seul compte à une recherche de patterns cross-comptes
nécessiterait le niveau Advanced Access de Meta (vérification d'entreprise, App Review), que ce
projet n'a pas et n'a pas besoin d'avoir pour la Phase 1. Aucun calendrier ni effort d'ingénierie
n'est engagé pour l'instant — voir le raisonnement complet dans [`CLAUDE.md`](CLAUDE.md).

## Installation en local

```bash
# Backend (Python 3.12 via uv)
pip install --user uv
uv sync
cp .env.example .env               # renseigner THREADS_* et ANTHROPIC_API_KEY
uv run pytest -q                   # 183 tests
uv run uvicorn src.main:app --reload --port 8000

# Dashboard (Next.js)
cd src/dashboard
npm install
npm run dev                        # http://localhost:3000
```

Le dashboard lit des données réelles depuis le backend FastAPI ci-dessus — les deux doivent
tourner en même temps pour voir de vrais chiffres.

## À propos du compte

Construit par Thy ([@thydilammuon](https://www.threads.net/@thydilammuon)), une créatrice
vietnamienne vivant et travaillant en France, qui partage du contenu sur l'alternance, la
recherche d'emploi et la vie quotidienne d'expatriée. Ce projet est né du besoin de vraiment
comprendre son propre compte — pas des métriques de vanité, mais un regard rigoureux sur ce que
font réellement ses publications — et s'est développé jusqu'à devenir le cas d'étude complet en
statistiques et NLP décrit ci-dessus.

## Licence

Projet personnel, privé. Tous droits réservés — ce n'est pas un logiciel open source, les
contributions externes ne sont pas acceptées. Construit comme pièce de portfolio, pour démontrer
une ingénierie NLP/ML appliquée sur des données de production réelles.
