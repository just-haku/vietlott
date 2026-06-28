"""
Brain management system for the Vietlott Deterministic Universe Pipeline.

A *Brain* encapsulates a set of formulas (one per feature) along with
their entropy scores on train and test data.  The *BrainManager*
maintains a leaderboard of the 5 best brains, sorted by
``test_entropy_score`` (lower is better = more deterministic).

Persistence
───────────
- ``brains/leaderboard.json``        — serialised top-5 list
- ``brains/brain_{rank}_{id}.json``  — individual brain snapshots
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ──────────────────────────── Brain dataclass ───────────────────────

@dataclass
class Brain:
    """A single brain: a scored collection of per-feature formulas.

    Attributes
    ──────────
    id : str
        Unique identifier for this brain.
    formulas : dict[str, str]
        Mapping of feature name → expression string.
    description : str
        Human-readable note about the brain's strategy.
    test_entropy_score : float
        Entropy measured on the held-out test set (lower is better).
    train_entropy_score : float
        Entropy measured on the training set.
    created_at : str
        ISO-8601 timestamp of creation (UTC).
    experiment_id : str
        Identifier of the experiment run that produced this brain.
    """

    id: str
    formulas: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    test_entropy_score: float = float("inf")
    train_entropy_score: float = float("inf")
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    experiment_id: str = ""

    # ── serialisation helpers ──

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Brain":
        """Reconstruct a Brain from a dict (e.g. loaded from JSON)."""
        return cls(
            id=data["id"],
            formulas=data.get("formulas", {}),
            description=data.get("description", ""),
            test_entropy_score=data.get("test_entropy_score", float("inf")),
            train_entropy_score=data.get("train_entropy_score", float("inf")),
            created_at=data.get(
                "created_at",
                datetime.now(timezone.utc).isoformat(),
            ),
            experiment_id=data.get("experiment_id", ""),
        )


# ──────────────────────────── BrainManager ──────────────────────────

class BrainManager:
    """Maintains a sorted top-5 leaderboard of Brains.

    Parameters
    ──────────
    brains_dir : str
        Directory where leaderboard and individual brain files are
        stored.  Created automatically if missing.
    max_brains : int
        Maximum number of brains to keep (default 5).

    Usage
    ─────
    >>> mgr = BrainManager("brains/")
    >>> mgr.submit(brain)
    >>> top5 = mgr.get_leaderboard()
    >>> mgr.save()
    """

    LEADERBOARD_FILENAME = "leaderboard.json"

    def __init__(
        self,
        brains_dir: str = "brains",
        max_brains: int = 5,
    ) -> None:
        self._brains_dir = os.path.normpath(brains_dir)
        self._max_brains = max_brains
        self._leaderboard: List[Brain] = []

    # ────────────── public API ──────────────

    def submit(self, brain: Brain) -> bool:
        """Submit a brain for consideration on the leaderboard.

        The brain is inserted in sorted order (ascending
        ``test_entropy_score``).  If the leaderboard already has
        *max_brains* entries and the new brain is worse than all of
        them, it is rejected.

        Returns
        ───────
        bool — ``True`` if the brain was accepted onto the leaderboard.
        """
        # Check if it qualifies
        if (
            len(self._leaderboard) >= self._max_brains
            and brain.test_entropy_score
            >= self._leaderboard[-1].test_entropy_score
        ):
            return False

        # Remove existing entry with same id (allow updates)
        self._leaderboard = [
            b for b in self._leaderboard if b.id != brain.id
        ]

        self._leaderboard.append(brain)
        self._leaderboard.sort(key=lambda b: b.test_entropy_score)
        self._leaderboard = self._leaderboard[: self._max_brains]
        return True

    def get_leaderboard(self) -> List[Brain]:
        """Return a copy of the current top-N leaderboard."""
        return list(self._leaderboard)

    @property
    def best(self) -> Optional[Brain]:
        """The #1 brain, or ``None`` if the leaderboard is empty."""
        return self._leaderboard[0] if self._leaderboard else None

    @property
    def size(self) -> int:
        """Number of brains currently on the leaderboard."""
        return len(self._leaderboard)

    # ────────────── persistence ──────────────

    def save(self) -> None:
        """Persist the leaderboard and individual brains to disk.

        Files written:
        - ``{brains_dir}/leaderboard.json``
        - ``{brains_dir}/brain_{rank}_{id}.json`` for each ranked brain
        """
        os.makedirs(self._brains_dir, exist_ok=True)

        # ── leaderboard.json ──
        lb_path = os.path.join(self._brains_dir, self.LEADERBOARD_FILENAME)
        lb_data = [b.to_dict() for b in self._leaderboard]
        with open(lb_path, "w", encoding="utf-8") as fh:
            json.dump(lb_data, fh, indent=2, ensure_ascii=False)

        # ── individual brain files ──
        for rank, brain in enumerate(self._leaderboard, start=1):
            # Sanitise id for filename (replace non-alnum with underscore)
            safe_id = "".join(
                c if c.isalnum() or c in "-_" else "_"
                for c in brain.id
            )
            filename = f"brain_{rank}_{safe_id}.json"
            brain_path = os.path.join(self._brains_dir, filename)
            with open(brain_path, "w", encoding="utf-8") as fh:
                json.dump(brain.to_dict(), fh, indent=2, ensure_ascii=False)

    def load(self) -> List[Brain]:
        """Load the leaderboard from disk.

        Reads ``{brains_dir}/leaderboard.json`` and repopulates the
        internal list.  Returns the loaded brains.

        Returns
        ───────
        list[Brain]

        Raises
        ──────
        FileNotFoundError
            If the leaderboard file does not exist.
        """
        lb_path = os.path.join(self._brains_dir, self.LEADERBOARD_FILENAME)
        lb_path = os.path.normpath(lb_path)

        if not os.path.isfile(lb_path):
            raise FileNotFoundError(
                f"Leaderboard not found: {lb_path}"
            )

        with open(lb_path, "r", encoding="utf-8") as fh:
            raw: List[Dict[str, Any]] = json.load(fh)

        self._leaderboard = [Brain.from_dict(d) for d in raw]
        self._leaderboard.sort(key=lambda b: b.test_entropy_score)
        self._leaderboard = self._leaderboard[: self._max_brains]
        return list(self._leaderboard)

    # ────────────── display ──────────────

    def format_leaderboard(self) -> str:
        """Return a human-readable leaderboard string."""
        if not self._leaderboard:
            return "Leaderboard is empty."

        lines = ["Rank | ID               | Test Entropy | Train Entropy | Description"]
        lines.append("─" * 80)
        for rank, b in enumerate(self._leaderboard, start=1):
            lines.append(
                f"  {rank}  | {b.id:<16} | {b.test_entropy_score:12.6f} "
                f"| {b.train_entropy_score:13.6f} | {b.description}"
            )
        return "\n".join(lines)
