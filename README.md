# Extraction_FB

**Pipeline ETL ultra-robuste d'extraction d'annonces foncières Facebook (Ouagadougou)**  
Conçu explicitement pour une **soutenance académique** et pour démontrer **6 mois de fonctionnement continu, fiable et à volume élevé**.

> Objectif non négociable : **zéro run critique qui échoue silencieusement**, volume de données cohérent avec l'activité réelle des groupes, preuves chiffrées de fiabilité sur toute la période.

---

## Pourquoi cette architecture est radicalement supérieure à un ETL classique

| Critère | ETL classique (ex: monolithe) | **Extraction_FB** |
|---------|------------------------------|-------------------|
| Structure | Fichiers plats, logique mélangée | **Hexagonal Architecture** (Ports & Adapters) |
| Résilience | try/except dispersés | **Circuit Breaker + Bulkhead + Retry budget + Adaptive throttle** par compte |
| Observabilité | logs texte | **Métriques structurées + historique 6 mois + score de fiabilité** |
| Volume | « on a scrapé ce qu'on a pu » | **Contrats de couverture** + détection de dérive de volume |
| État | fichiers JSON fragiles | État versionné, isolé par compte, avec health score |
| Échec | un run raté = trou de données | **Fail-soft** + recovery automatique + audit complet |
| Maintenabilité | 1 fichier de 2000+ lignes | Modules isolés, testables unitairement |
| Preuve soutenance | « ça a marché » | **Table `run_metrics` + dashboard de fiabilité sur 180 jours** |

---

## Architecture (Hexagonale / Ports & Adapters)

```
src/extraction_fb/
├── domain/                 # Cœur pur (zéro dépendance technique)
│   ├── models.py           # Annonce, PostBrut, Groupe, Compte, RunMetrics
│   ├── events.py           # Domain events (SessionExpiree, VolumeDrift, ...)
│   ├── policies.py         # Règles métier (filtrage, normalisation)
│   └── ports.py            # Interfaces (ScraperPort, LlmPort, RepositoryPort, ...)
│
├── application/            # Cas d'usage (orchestration)
│   ├── pipeline.py         # Orchestrateur principal
│   ├── scraping_use_case.py
│   ├── processing_use_case.py
│   └── health_use_case.py  # Score de santé + décisions de recovery
│
├── infrastructure/         # Adapters concrets
│   ├── facebook/           # Playwright + anti-détection
│   ├── llm/                # OpenAI Structured Outputs
│   ├── persistence/        # PostgreSQL (Neon) + Excel
│   ├── resilience/         # CircuitBreaker, Bulkhead, RetryPolicy
│   └── state/              # Gestion d'état isolée par compte
│
├── observability/          # Logs structurés + métriques
│   ├── metrics.py
│   ├── logging.py
│   └── reliability_score.py
│
└── config/                 # Configuration validée (Pydantic Settings)
```

**Principe d'or** : le `domain/` ne connaît ni Playwright, ni OpenAI, ni Postgres.  
On peut remplacer n'importe quel adapter sans toucher au métier → robustesse et testabilité maximales.

---

## Piliers de fiabilité (conçus pour 6 mois)

### 1. Isolation totale par compte (Bulkhead)
Chaque compte Facebook possède :
- sa propre session / cookies
- son propre circuit breaker
- son propre score de santé
- son propre cooldown
- son propre état de déduplication

Un compte bloqué **n'impacte jamais** les autres.

### 2. Circuit Breaker multi-niveaux
- Niveau **compte** : après N détections de blocage → open 24h
- Niveau **groupe** : un groupe qui retourne 0 post de façon anormale est mis en quarantaine temporaire
- Niveau **global** : protection contre les cascades

### 3. Contrats de couverture & détection de dérive
Chaque run calcule :
- `posts_bruts` vs `posts_attendus` (basé sur l'historique mobile des 14 derniers jours)
- `taux_de_couverture`
- `score_de_fiabilite_run` (0-100)

Si le volume est anormalement bas → alerte + éventuelle stratégie de recovery (re-scrape ciblé, changement de proxy, etc.).

### 4. Observabilité prouvable
Table `run_metrics` (PostgreSQL) :
- horodatage, compte, mode
- nb_posts_bruts, nb_candidats, nb_valides
- durée, erreurs classifiées
- score_fiabilite, couverture
- statut final (`success` | `partial` | `cooldown` | `failed`)

→ Permet de générer un **rapport de fiabilité sur 180 jours** pour la soutenance.

### 5. Idempotence stricte
Tout upsert est basé sur l'`id` Facebook du post.  
Relancer un run ne crée jamais de doublons et ne corrompt pas l'historique.

### 6. Fail-soft par design
- `CooldownActif` → exit 0 (ce n'est pas un échec)
- Erreur sur un groupe → on continue les autres
- Erreur LLM sur un post → quarantaine du post, pas du run entier

---

## Objectifs quantitatifs pour la soutenance

| KPI | Cible sur 6 mois |
|-----|------------------|
| Taux de runs « success » ou « partial » | ≥ 95 % |
| Runs critiques en échec total | ≤ 2 % |
| Volume moyen vs activité estimée des groupes | ≥ 80 % de couverture |
| Doublons en base | 0 |
| Temps moyen de recovery après session expirée | < 2 h (process documenté) |

Ces chiffres seront calculés automatiquement à partir de `run_metrics`.

---

## Stack technique

- **Python 3.12**
- **Playwright** (scraping mobile authentifié)
- **OpenAI** (gpt-4o-mini + Structured Outputs)
- **PostgreSQL** (Neon) — source de vérité
- **Pydantic v2** — validation partout
- **Patterns de résilience** (Circuit Breaker, Bulkhead, Retry budget) implémentés explicitement
- **GitHub Actions** (matrice multi-comptes + isolation forte)
- **pytest** + tests d'intégration contre Postgres réel

---

## Statut actuel

Ce dépôt est le **socle architectural** conçu pour remplacer et surpasser l'approche précédente.  
Les modules de domaine, de résilience et d'observabilité sont prioritaires.  
Le scraping et le processing concrets s'appuient sur les leçons apprises (anti-blocage, multi-comptes, proxy, etc.) tout en étant complètement découplés.

---

## Roadmap vers la soutenance (6 mois)

1. **Mois 1** — Domaine + Résilience + Observabilité + tests unitaires solides
2. **Mois 2** — Adapter Facebook complet + multi-comptes + proxy
3. **Mois 3** — Processing LLM + persistence + contrats de volume
4. **Mois 4-5** — Stabilisation, tuning anti-blocage, collecte réelle
5. **Mois 6** — Rapport de fiabilité 180 jours + préparation soutenance

---

**Auteur** : Cheick-Yasine  
**Objectif** : Architecture de référence pour extraction fiable à long terme sur Facebook Groups.
