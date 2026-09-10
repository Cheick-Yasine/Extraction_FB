"""Calcul du score de fiabilité d'un run et agrégation sur 6 mois.

Ce module produit les chiffres que tu pourras présenter en soutenance :
- score par run (0-100)
- taux de succès sur N jours
- couverture moyenne
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from extraction_fb.domain.models import RunMetrics, RunStatus


@dataclass(frozen=True)
class ReliabilityReport:
    """Rapport agrégé prêt pour la soutenance."""

    period_days: int
    total_runs: int
    success_or_partial: int
    failed: int
    cooldown: int
    success_rate: float          # 0.0 – 1.0
    avg_couverture: float | None
    avg_score_fiabilite: float | None
    avg_posts_valides: float
    first_run: datetime | None
    last_run: datetime | None

    def to_dict(self) -> dict:
        return {
            "period_days": self.period_days,
            "total_runs": self.total_runs,
            "success_or_partial": self.success_or_partial,
            "failed": self.failed,
            "cooldown": self.cooldown,
            "success_rate_pct": round(self.success_rate * 100, 2),
            "avg_couverture_pct": round(self.avg_couverture * 100, 2) if self.avg_couverture is not None else None,
            "avg_score_fiabilite": round(self.avg_score_fiabilite, 1) if self.avg_score_fiabilite is not None else None,
            "avg_posts_valides": round(self.avg_posts_valides, 1),
            "first_run": self.first_run.isoformat() if self.first_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }


def score_run(
    *,
    nb_posts_bruts: int,
    nb_valides: int,
    couverture: float | None,
    had_critical_error: bool,
    was_cooldown: bool,
) -> float:
    """Score 0-100 pour un run individuel.

    Logique :
    - cooldown → 70 (mécanisme de protection qui a fonctionné)
    - erreur critique → 0-20
    - sinon combinaison volume + couverture
    """
    if was_cooldown:
        return 70.0

    if had_critical_error:
        return 10.0 if nb_valides == 0 else 25.0

    # Base sur le volume valide
    volume_score = min(nb_valides / 15.0, 1.0) * 50  # 15 annonces valides = plein score volume

    # Bonus couverture
    cov_score = 0.0
    if couverture is not None:
        cov_score = min(max(couverture, 0.0), 1.0) * 40

    # Petit bonus si on a au moins collecté quelque chose
    activity_bonus = 10.0 if nb_posts_bruts > 0 else 0.0

    return min(100.0, volume_score + cov_score + activity_bonus)


def build_reliability_report(
    metrics: Sequence[RunMetrics],
    *,
    period_days: int = 180,
) -> ReliabilityReport:
    """Construit le rapport de fiabilité sur la période donnée."""
    if not metrics:
        return ReliabilityReport(
            period_days=period_days,
            total_runs=0,
            success_or_partial=0,
            failed=0,
            cooldown=0,
            success_rate=0.0,
            avg_couverture=None,
            avg_score_fiabilite=None,
            avg_posts_valides=0.0,
            first_run=None,
            last_run=None,
        )

    cutoff = max(m.horodatage for m in metrics) - timedelta(days=period_days)
    window = [m for m in metrics if m.horodatage >= cutoff]

    total = len(window)
    success_or_partial = sum(
        1 for m in window if m.statut in (RunStatus.SUCCESS, RunStatus.PARTIAL)
    )
    failed = sum(1 for m in window if m.statut == RunStatus.FAILED)
    cooldown = sum(1 for m in window if m.statut == RunStatus.COOLDOWN)

    scores = [m.score_fiabilite for m in window if m.score_fiabilite is not None]
    covs = [m.couverture for m in window if m.couverture is not None]

    return ReliabilityReport(
        period_days=period_days,
        total_runs=total,
        success_or_partial=success_or_partial,
        failed=failed,
        cooldown=cooldown,
        success_rate=success_or_partial / total if total else 0.0,
        avg_couverture=sum(covs) / len(covs) if covs else None,
        avg_score_fiabilite=sum(scores) / len(scores) if scores else None,
        avg_posts_valides=sum(m.nb_valides for m in window) / total if total else 0.0,
        first_run=min(m.horodatage for m in window) if window else None,
        last_run=max(m.horodatage for m in window) if window else None,
    )
