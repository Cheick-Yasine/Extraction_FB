"""Ports du domaine — contrats que les adapters doivent respecter.

Le cœur métier ne dépend jamais des technologies concrètes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from extraction_fb.domain.models import (
    AccountHealth,
    Annonce,
    Groupe,
    PostBrut,
    RunMetrics,
)


class ScraperPort(ABC):
    """Port de scraping Facebook."""

    @abstractmethod
    async def scrape_groupes(
        self,
        groupes: Sequence[Groupe],
        *,
        days_back: int,
        compte: str,
    ) -> list[PostBrut]:
        ...


class LlmPort(ABC):
    """Port de structuration LLM."""

    @abstractmethod
    async def structurer(self, posts: Sequence[PostBrut]) -> list[Annonce]:
        ...


class RepositoryPort(ABC):
    """Port de persistence (PostgreSQL)."""

    @abstractmethod
    async def upsert_annonces(self, annonces: Sequence[Annonce]) -> int:
        """Retourne le nombre d'annonces réellement écrites/mises à jour."""
        ...

    @abstractmethod
    async def save_run_metrics(self, metrics: RunMetrics) -> None:
        ...

    @abstractmethod
    async def get_recent_volume_stats(
        self, *, compte: str | None, days: int = 14
    ) -> dict[str, float]:
        """Statistiques de volume pour calcul de couverture."""
        ...


class StatePort(ABC):
    """Port de gestion d'état isolé par compte."""

    @abstractmethod
    async def load_health(self, compte: str) -> AccountHealth:
        ...

    @abstractmethod
    async def save_health(self, health: AccountHealth) -> None:
        ...

    @abstractmethod
    async def is_post_seen(self, compte: str, post_id: str) -> bool:
        ...

    @abstractmethod
    async def mark_posts_seen(self, compte: str, post_ids: Sequence[str]) -> None:
        ...


class ClockPort(ABC):
    """Horloge injectable (facilite les tests)."""

    @abstractmethod
    def now(self) -> datetime:
        ...
