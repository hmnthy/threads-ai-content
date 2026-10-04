# Unthreaded

**Langue :** [English](README.md) · [Tiếng Việt](README.vi.md) · Français

![Status](https://img.shields.io/badge/status-in%20progress-orange)
![Tests](https://img.shields.io/badge/tests-425%20passing-brightgreen)
![License](https://img.shields.io/badge/license-private-lightgrey)

> The algorithm, read back to you.
> (L'algorithme, relu à voix haute.)

L'algorithme de classement de Threads est une boîte noire — les créateurs n'ont aucun moyen de
comprendre pourquoi une publication décolle et la suivante non. Ce projet prend un vrai compte
Threads, **[@thydilammuon](https://www.threads.net/@thydilammuon)** (une créatrice vietnamienne
vivant en France, qui parle d'alternance, de recherche d'emploi et de vie d'expatriée), comme cas
d'étude en conditions réelles : chaque chiffre affiché sur le dashboard provient d'une formule
documentée et citée — jamais d'un score « boîte noire ».

C'est un **projet d'analyse et de recherche NLP** dédié à ce seul compte, qui vise une **base de
connaissances** mise à jour en continu à partir de ce que le compte a déjà partagé avec ses abonnés —
construit en parallèle comme pièce de portfolio d'ingénierie NLP/ML. Ce n'est pas un SaaS, pas
multi-tenant, et ça n'a pas vocation à le devenir.

---

## Captures d'écran

Le produit en quatre étapes — du pitch jusqu'aux sujets bruts découverts par clustering.

<p align="center">
  <img src="docs/screenshots/landing.png" alt="Landing page: hero, problem, solution, tech stack" width="820"><br>
  <sub><b>1. Landing</b> — le pitch, le problème, et la solution à trois couches (statistiques → NLP → base de connaissances), avec toute la stack technique affichée selon son statut réel.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/overview.png" alt="Overview tab: KPI strip and Timeline Brush" width="820"><br>
  <sub><b>2. Overview</b> — bandeau de KPI centré sur la médiane, graphique des vues quotidiennes avec le Timeline Brush (glisser pour recalculer), et les contenus les plus performants sur la fenêtre sélectionnée.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/analytics.png" alt="Analytics tab: top posts and timezone breakdown" width="820"><br>
  <sub><b>3. Analytics</b> — meilleures publications par engagement/viralité/conversation, et performance par créneau horaire, répartie sur les deux fuseaux Europe/Paris et Asia/Ho_Chi_Minh.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/topics.png" alt="Topic Explorer: 3D UMAP scatter of discovered topics" width="820"><br>
  <sub><b>4. Topic Explorer</b> — clusters de sujets découverts de façon non supervisée (UMAP 3D + HDBSCAN) à partir de l'historique réel des publications du compte.</sub>
</p>

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

Trois couches, construites dans cet ordre — chacune ancrée dans une méthodologie
citée, jamais dans l'intuition.

| Couche | Statut | Ce qu'elle fait |
|---|---|---|
| **Couche statistique** | En ligne | Six indices intrinsèques gardés séparés — popularité, engagement, viralité, conversation, vélocité, longévité — jamais fusionnés en un seul score. Médiane et moyenne toujours rapportées ensemble (jamais une moyenne seule), IQR et alerte de taille d'échantillon sur chaque groupe, test de Mann-Whitney U + delta de Cliff pour toute comparaison de groupes, viralité calculée en percentile propre à chaque compte plutôt qu'avec un seuil fixe arbitraire. |
| **Couche NLP** | En ligne | Des embeddings de phrases multilingues (le contenu mélange naturellement vietnamien, français et anglais, donc aucun tokenizer propre à une langue) alimentent UMAP + HDBSCAN pour une découverte de sujets non supervisée, puis Claude nomme chaque cluster découvert en anglais. Un Code-Mixing Index — un score continu, pas un simple booléen — mesure à quel point une publication mélange réellement les langues. |
| **Base de connaissances** | Prochaine étape | Les publications du compte et les réponses de l'autrice aux questions des abonnés, transformées en base de connaissances interrogeable : recherche hybride (mots-clés BM25 + sémantique) avec reranker, évaluée sur de vraies questions d'abonnés (recall@k, MRR, nDCG) avant de construire quoi que ce soit — comme un assistant de questions-réponses — par-dessus. |

## Stack technique

Affichée exactement dans l'état réel du code aujourd'hui — rien n'est présenté comme prêt s'il ne
l'est pas.

| Couche | Technologie | Statut |
|---|---|---|
| Backend / API | FastAPI | En ligne |
| Gestionnaire de paquets | uv (`pyproject.toml` + `uv.lock`) | En ligne |
| Client API Threads | httpx (async) | En ligne |
| Validation | Pydantic v2 | En ligne |
| IA / LLM | Claude API (`claude-sonnet-5-5`, nommage des clusters) | En ligne |
| Dashboard | Next.js 16 + Tailwind v4, graphiques SVG faits main + Plotly (carte des sujets) | En ligne |
| Base de données | SQLite — un fichier, un seul processus d'écriture ; la base de connaissances y vivra aussi | En ligne |
| Scoring des métriques | Architecture à 6 indices (popularité/engagement/viralité/conversation/vélocité/longévité) | En ligne |
| Détection de langue | lingua-py + Code-Mixing Index | En ligne |
| Extraction de features NLP | sentence-transformers, multilingue (bge-m3 / multilingual-e5-large) | En ligne |
| Découverte de sujets | UMAP + HDBSCAN (clustering non supervisé) | En ligne |
| Qualité du code | ruff (lint+format), mypy (strict), pytest, pre-commit | En ligne |
| Classification à catégories fixes | SVM-RBF + Régression logistique (échelle de baselines vs. clusters non supervisés) | Recherche, non commencé |
| Recherche dans la base de connaissances | SQLite FTS5 (BM25) + embeddings denses + reranker cross-encoder | Prochaine étape |

## Architecture

```
threads-ai-content/
├── src/
│   ├── api/            Client Threads Graph API (auth, pagination, cache) — en ligne
│   ├── models/          Modèles de domaine ContentUnit / InsightSnapshot — en ligne
│   ├── processing/       Reconstruction des threads (racine + chaîne de self-reply), nettoyage texte — en ligne
│   ├── analysis/         Scoring 6 indices + statistiques par fenêtre temporelle (médiane/moyenne/IQR) — en ligne
│   ├── nlp/              Détection de langue, embeddings multilingues, clustering UMAP+HDBSCAN — en ligne
│   ├── db/                Schéma SQLite (posts, content_units, insights_snapshots, topics, embeddings, cluster_runs) — en ligne
│   ├── pipeline/           Ingestion, cron de snapshot toutes les 4h, pont de clustering Windows↔WSL2 — en ligne
│   ├── main.py             Point d'entrée FastAPI — en ligne
│   └── dashboard/          App Next.js : landing page + Overview/Analytics/Topic Explorer — en ligne
└── tests/                suite pytest, ruff + mypy strict propres
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

Quelques décisions considérées comme structurantes pour ce projet, chacune consignée dans
[`docs/decisions/`](docs/decisions/) (un fichier par décision) et
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

**En ligne :** client API Threads, pipeline NLP de découverte de sujets, architecture à 6
indices, statistiques par fenêtre temporelle, et un dashboard à 3 onglets (Overview, Analytics,
Topic Explorer) plus cette landing page, en conditions réelles sur des données de production
(suite de tests complète au vert, ruff + mypy strict propres).

**Prochaines étapes — un périmètre volontairement resserré (« less is more ») :**
1. Une analyse NLP plus poussée, rédigée sous forme de questions de recherche explicites
   (stabilité des clusters, comparaison de modèles d'embedding, code-mixing vs. engagement,
   échelle de baselines pour un classifieur supervisé).
2. Une base de connaissances mise à jour en continu, avec une qualité de recherche mesurée.
3. Seulement une fois cette base validée : un assistant de questions-réponses qui s'appuie dessus,
   et une page d'accueil de marque pour le compte.

<!-- consistency: allow ADR0001-generation ADR0001-carousel ADR0001-image-gen -->
La génération de publications dans le style de l'autrice et la génération d'images carousel ont
été envisagées puis délibérément abandonnées pour garder le projet ciblé.

## Installation en local

```bash
# Backend (Python 3.12 via uv)
pip install --user uv
uv sync
uv run pre-commit install          # garde-fous de commit : lint, types, cohérence, tests rapides
cp .env.example .env               # renseigner THREADS_* et ANTHROPIC_API_KEY
uv run pytest -q                   # suite complète (~1 min)
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

Sans lien avec Meta. Threads est une marque de Meta Platforms, Inc. Le dépôt conserve son nom
technique `threads-ai-content`.
