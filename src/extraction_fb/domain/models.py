"""Modèles du domaine — purement métier, zéro dépendance technique."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    COOLDOWN = "cooldown"
    FAILED = "failed"
    SKIPPED = "skipped"


class CircuitState(str, Enum):
    CLOSED = "closed"      # normal
    OPEN = "open"          # bloqué
    HALF_OPEN = "half_open"  # test de recovery


@dataclass(frozen=True, slots=True)
class Groupe:
    id: str
    nom: str
    url: str
    compte: str
    actif: bool = True


@dataclass(frozen=True, slots=True)
class PostBrut:
    """Post tel que sorti du scraper (avant filtrage / LLM)."""

    id: str
    groupe_id: str
    groupe_nom: str
    url: str
    texte: str
    date_publication: datetime | None
    date_apparition_groupe: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class Annonce:
    """Annonce structurée et validée (après LLM + normalisation)."""

    id: str
    groupe_nom: str
    url: str
    date_publication: datetime | None
    type_bien: str | None
    quartier_zone: str | None
    superficie_m2: float | None
    prix_fcfa: int | None
    statut_document: str | None
    contacts_whatsapp: list[str]
    mots_cles_pertinents: list[str]
    resume_court: str
    texte_nettoye: str
    premiere_collecte: datetime
    derniere_maj: datetime


@dataclass(slots=True)
class RunMetrics:
    """Métriques d'un run — source de vérité pour prouver 6 mois de fiabilité."""

    horodatage: datetime
    compte: str
    mode: str
    statut: RunStatus
    nb_posts_bruts: int = 0
    nb_candidats: int = 0
    nb_valides: int = 0
    duree_secondes: float = 0.0
    couverture: float | None = None  # 0.0 – 1.0
    score_fiabilite: float | None = None  # 0 – 100
    erreurs: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "horodatage": self.horodatage.isoformat(),
            "compte": self.compte,
            "mode": self.mode,
            "statut": self.statut.value,
            "nb_posts_bruts": self.nb_posts_bruts,
            "nb_candidats": self.nb_candidats,
            "nb_valides": self.nb_valides,
            "duree_secondes": self.duree_secondes,
            "couverture": self.couverture,
            "score_fiabilite": self.score_fiabilite,
            "erreurs": self.erreurs,
            "details": self.details,
        }


@dataclass(slots=True)
class AccountHealth:
    """État de santé d'un compte Facebook (isolé)."""

    compte: str
    circuit: CircuitState = CircuitState.CLOSED
    score_confiance: float = 1.0  # 0.0 – 1.0
    cooldown_until: datetime | None = None
    last_success: datetime | None = None
    consecutive_failures: int = 0
    total_runs: int = 0
    successful_runs: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 1.0
        return self.successful_runs / self.total_runs
