"""Orchestrateur principal du pipeline.

Ce use case coordonne les ports sans connaître les technologies concrètes.
Il est le point d'entrée métier de tout run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from extraction_fb.domain.models import (
    Groupe,
    RunMetrics,
    RunStatus,
)
from extraction_fb.domain.ports import (
    ClockPort,
    LlmPort,
    RepositoryPort,
    ScraperPort,
    StatePort,
)
from extraction_fb.infrastructure.resilience.circuit_breaker import CircuitBreakerRegistry
from extraction_fb.observability.reliability_score import score_run


class Pipeline:
    """Cas d'usage principal : scrape → filter/structure → persist → metrics."""

    def __init__(
        self,
        *,
        scraper: ScraperPort,
        llm: LlmPort,
        repository: RepositoryPort,
        state: StatePort,
        clock: ClockPort,
        circuit_registry: CircuitBreakerRegistry | None = None,
    ) -> None:
        self.scraper = scraper
        self.llm = llm
        self.repository = repository
        self.state = state
        self.clock = clock
        self.circuits = circuit_registry or CircuitBreakerRegistry()

    async def run(
        self,
        *,
        groupes: Sequence[Groupe],
        compte: str,
        mode: str = "daily",
        days_back: int = 1,
    ) -> RunMetrics:
        started = self.clock.now()
        errors: list[str] = []
        statut = RunStatus.SUCCESS
        nb_bruts = 0
        nb_candidats = 0
        nb_valides = 0
        couverture: float | None = None

        # 1. Vérifier la santé du compte (Bulkhead + Circuit Breaker)
        health = await self.state.load_health(compte)
        account_cb = self.circuits.get(f"account:{compte}", failure_threshold=3)

        if not account_cb.allow_request(started):
            statut = RunStatus.COOLDOWN
            metrics = self._build_metrics(
                started=started,
                compte=compte,
                mode=mode,
                statut=statut,
                errors=["Circuit breaker OPEN — compte en cooldown"],
            )
            await self.repository.save_run_metrics(metrics)
            return metrics

        if health.cooldown_until and health.cooldown_until > started:
            statut = RunStatus.COOLDOWN
            metrics = self._build_metrics(
                started=started,
                compte=compte,
                mode=mode,
                statut=statut,
                errors=[f"Cooldown actif jusqu'à {health.cooldown_until.isoformat()}"],
            )
            await self.repository.save_run_metrics(metrics)
            return metrics

        try:
            # 2. Scraping (isolé)
            posts = await self.scraper.scrape_groupes(
                groupes, days_back=days_back, compte=compte
            )
            nb_bruts = len(posts)

            # 3. Structuration LLM
            annonces = await self.llm.structurer(posts)
            nb_valides = len(annonces)
            nb_candidats = nb_bruts  # simplifié ici ; le filtrage regex viendra dans l'adapter

            # 4. Persistence idempotente
            if annonces:
                await self.repository.upsert_annonces(annonces)

            # 5. Mise à jour santé
            account_cb.record_success()
            health.consecutive_failures = 0
            health.last_success = started
            health.successful_runs += 1
            health.total_runs += 1
            await self.state.save_health(health)

            # 6. Couverture (basée sur historique)
            stats = await self.repository.get_recent_volume_stats(compte=compte, days=14)
            expected = stats.get("avg_posts_bruts", 0) or 1
            couverture = min(nb_bruts / expected, 2.0)  # cap à 200 %

        except Exception as exc:  # noqa: BLE001 — on capture pour métriques
            errors.append(f"{type(exc).__name__}: {exc}")
            statut = RunStatus.FAILED
            account_cb.record_failure(started)
            health.consecutive_failures += 1
            health.total_runs += 1
            await self.state.save_health(health)

        score = score_run(
            nb_posts_bruts=nb_bruts,
            nb_valides=nb_valides,
            couverture=couverture,
            had_critical_error=statut == RunStatus.FAILED,
            was_cooldown=statut == RunStatus.COOLDOWN,
        )

        metrics = self._build_metrics(
            started=started,
            compte=compte,
            mode=mode,
            statut=statut,
            nb_posts_bruts=nb_bruts,
            nb_candidats=nb_candidats,
            nb_valides=nb_valides,
            couverture=couverture,
            score_fiabilite=score,
            errors=errors,
        )
        await self.repository.save_run_metrics(metrics)
        return metrics

    def _build_metrics(
        self,
        *,
        started: datetime,
        compte: str,
        mode: str,
        statut: RunStatus,
        nb_posts_bruts: int = 0,
        nb_candidats: int = 0,
        nb_valides: int = 0,
        couverture: float | None = None,
        score_fiabilite: float | None = None,
        errors: list[str] | None = None,
    ) -> RunMetrics:
        ended = self.clock.now()
        return RunMetrics(
            horodatage=started,
            compte=compte,
            mode=mode,
            statut=statut,
            nb_posts_bruts=nb_posts_bruts,
            nb_candidats=nb_candidats,
            nb_valides=nb_valides,
            duree_secondes=(ended - started).total_seconds(),
            couverture=couverture,
            score_fiabilite=score_fiabilite,
            erreurs=errors or [],
        )
