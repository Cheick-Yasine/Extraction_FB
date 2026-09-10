"""Tests du calcul de score et du rapport de fiabilité."""

from datetime import datetime, timedelta, timezone

from extraction_fb.domain.models import RunMetrics, RunStatus
from extraction_fb.observability.reliability_score import (
    build_reliability_report,
    score_run,
)


def test_score_cooldown_is_reasonable():
    s = score_run(
        nb_posts_bruts=0,
        nb_valides=0,
        couverture=None,
        had_critical_error=False,
        was_cooldown=True,
    )
    assert s == 70.0


def test_score_critical_failure_low():
    s = score_run(
        nb_posts_bruts=0,
        nb_valides=0,
        couverture=None,
        had_critical_error=True,
        was_cooldown=False,
    )
    assert s <= 20.0


def test_score_good_run_high():
    s = score_run(
        nb_posts_bruts=40,
        nb_valides=18,
        couverture=0.9,
        had_critical_error=False,
        was_cooldown=False,
    )
    assert s >= 80.0


def test_reliability_report_empty():
    report = build_reliability_report([])
    assert report.total_runs == 0
    assert report.success_rate == 0.0


def test_reliability_report_mixed():
    now = datetime.now(timezone.utc)
    metrics = [
        RunMetrics(horodatage=now - timedelta(days=1), compte="1", mode="daily", statut=RunStatus.SUCCESS, nb_valides=12, score_fiabilite=85),
        RunMetrics(horodatage=now - timedelta(days=2), compte="1", mode="daily", statut=RunStatus.PARTIAL, nb_valides=8, score_fiabilite=70),
        RunMetrics(horodatage=now - timedelta(days=3), compte="1", mode="daily", statut=RunStatus.COOLDOWN, score_fiabilite=70),
        RunMetrics(horodatage=now - timedelta(days=4), compte="1", mode="daily", statut=RunStatus.FAILED, score_fiabilite=10),
    ]
    report = build_reliability_report(metrics, period_days=30)
    assert report.total_runs == 4
    assert report.success_or_partial == 2
    assert report.failed == 1
    assert report.cooldown == 1
    assert report.success_rate == 0.5
