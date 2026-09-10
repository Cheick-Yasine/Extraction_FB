# Architecture Decision Record — Extraction_FB

## Contexte

Le projet précédent (`ouaga-foncier-etl`) a prouvé la faisabilité technique :
- scraping Playwright multi-comptes
- filtrage regex + LLM Structured Outputs
- upsert PostgreSQL
- anti-blocage basique

Limites observées pour une exploitation de 6 mois et une soutenance :
- monolithe difficile à faire évoluer (`scraper.py` > 90 Ko)
- résilience dispersée (pas de Circuit Breaker explicite)
- pas de métriques structurées permettant de **prouver** la fiabilité dans le temps
- détection de volume faible existante mais pas intégrée dans un score de fiabilité
- état fragile (fichiers JSON)

## Décision

Adopter une **Hexagonal Architecture (Ports & Adapters)** + patterns de résilience explicites + observabilité first-class.

### Principes non négociables

1. **Le domaine ne dépend de rien**  
   Playwright, OpenAI, Postgres, fichiers → uniquement dans `infrastructure/`.

2. **Isolation par compte (Bulkhead)**  
   Un compte bloqué ne doit jamais contaminer les autres.

3. **Tout run produit des métriques**  
   Même un run en cooldown ou en échec écrit dans `run_metrics`.  
   C’est la source de vérité pour le rapport de soutenance.

4. **Fail-soft**  
   Une erreur sur un groupe ou un post ne tue pas le run entier.

5. **Idempotence**  
   Relancer un run ne crée jamais de doublons.

6. **Score de fiabilité calculable**  
   Chaque run reçoit un score 0-100.  
   Sur 180 jours on peut afficher un taux de succès ≥ 95 %.

## Conséquences

### Positives
- Testabilité unitaire très élevée (mocks des ports)
- Remplacement possible de Playwright ou d’OpenAI sans toucher au métier
- Preuves chiffrées pour la soutenance
- Évolution plus sûre sur 6 mois

### Coût
- Plus de fichiers et d’interfaces au début
- Courbe d’apprentissage un peu plus élevée

→ Accepté : la robustesse et la démontrabilité valent largement le surcoût initial.

## Patterns de résilience retenus

| Pattern | Rôle |
|---------|------|
| **Circuit Breaker** | Empêche de marteler un compte/groupe déjà en difficulté |
| **Bulkhead** | Isolation totale des comptes |
| **Retry avec budget** | Tentatives limitées + jitter (pas de retry infini) |
| **Adaptive throttling** | Score de confiance module les délais |
| **Cooldown explicite** | Exit code 0 (pas un échec de workflow) |

## Preuve pour la soutenance

La table `run_metrics` + le module `reliability_score.py` permettent de générer :

```text
Rapport de fiabilité — 180 jours
--------------------------------
Runs totaux          : 312
Success + Partial    : 298  (95.5 %)
Failed               : 6    (1.9 %)
Cooldown             : 8
Couverture moyenne   : 87 %
Score moyen          : 82.4
```

C’est exactement ce qu’un jury attend pour valider qu’« ça a fonctionné de façon robuste sur 6 mois ».
