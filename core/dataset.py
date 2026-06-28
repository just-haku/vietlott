"""
Dataset manager for the Vietlott feature pipeline.

Responsibilities
────────────────
- Load extracted features from a JSONL file.
- Provide a deterministic, sequential 80/20 train/test split
  (time-ordered; no shuffling).
- Generate sliding-window sequences for time-series modelling.

Cross-platform: uses ``os.path`` everywhere — works on Linux & Windows.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


class DatasetManager:
    """Manages feature data loading, splitting, and windowing.

    Parameters
    ──────────
    path : str
        Path to a ``features.jsonl`` file produced by :class:`Analyzer`.
    train_ratio : float
        Fraction of records used for training (default 0.8 = 80 %).

    Usage
    ─────
    >>> dm = DatasetManager("output/features.jsonl")
    >>> train = dm.get_train()
    >>> test  = dm.get_test()
    >>> seqs  = dm.get_sequences(window_size=10)
    """

    def __init__(
        self,
        path: Optional[str] = None,
        train_ratio: float = 0.80,
    ) -> None:
        self._features: List[Dict[str, Any]] = []
        self._train_ratio = train_ratio
        self._split_idx: int = 0

        if path is not None:
            self.load_features(path)

    # ────────────── loading ──────────────

    def load_features(self, path: str) -> List[Dict[str, Any]]:
        """Load feature records from a JSONL file.

        Records are kept in their original file order (which should be
        chronological).  The internal train/test boundary is recomputed
        each time this method is called.

        Parameters
        ──────────
        path : str
            Absolute or relative path to ``features.jsonl``.

        Returns
        ───────
        list[dict] — all loaded feature records.

        Raises
        ──────
        FileNotFoundError
            If *path* does not exist.
        """
        path = os.path.normpath(path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Feature file not found: {path}")

        features: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                features.append(json.loads(line))

        self._features = features
        self._split_idx = int(len(features) * self._train_ratio)
        return features

    # ────────────── splitting ──────────────

    @property
    def total_records(self) -> int:
        """Total number of loaded feature records."""
        return len(self._features)

    @property
    def train_size(self) -> int:
        """Number of records in the training split."""
        return self._split_idx

    @property
    def test_size(self) -> int:
        """Number of records in the test split."""
        return len(self._features) - self._split_idx

    def get_train(self) -> List[Dict[str, Any]]:
        """Return the training split (first 80 % of records).

        The split is sequential (time-ordered, no shuffle) to preserve
        temporal causality for time-series models.
        """
        return list(self._features[: self._split_idx])

    def get_test(self) -> List[Dict[str, Any]]:
        """Return the test split (last 20 % of records).

        These records are strictly later in time than any training
        record, preventing data leakage.
        """
        return list(self._features[self._split_idx :])

    # ────────────── windowing ──────────────

    def get_sequences(
        self,
        window_size: int = 10,
        split: Optional[str] = None,
    ) -> List[List[Dict[str, Any]]]:
        """Generate sliding-window sequences for time-series modelling.

        Parameters
        ──────────
        window_size : int
            Number of consecutive records per window (default 10).
        split : str or None
            ``"train"``, ``"test"``, or ``None`` (full dataset).

        Returns
        ───────
        list[list[dict]]
            Each element is a list of *window_size* consecutive feature
            dicts.  Windows slide by one record at a time.

        Raises
        ──────
        ValueError
            If *window_size* < 1 or larger than the selected data.
        """
        if window_size < 1:
            raise ValueError("window_size must be >= 1")

        if split == "train":
            data = self.get_train()
        elif split == "test":
            data = self.get_test()
        elif split is None:
            data = list(self._features)
        else:
            raise ValueError(f"Unknown split: {split!r}. Use 'train', 'test', or None.")

        if window_size > len(data):
            raise ValueError(
                f"window_size ({window_size}) exceeds data length ({len(data)})"
            )

        sequences: List[List[Dict[str, Any]]] = []
        for i in range(len(data) - window_size + 1):
            sequences.append(data[i : i + window_size])
        return sequences

    # ────────────── summary ──────────────

    def summary(self) -> Dict[str, Any]:
        """Return a quick summary of the loaded dataset."""
        return {
            "total_records": self.total_records,
            "train_size": self.train_size,
            "test_size": self.test_size,
            "train_ratio": self._train_ratio,
            "first_id": self._features[0]["id"] if self._features else None,
            "last_id": self._features[-1]["id"] if self._features else None,
            "first_date": self._features[0].get("date") if self._features else None,
            "last_date": self._features[-1].get("date") if self._features else None,
        }
