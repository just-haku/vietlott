"""
Feature Extraction Engine for Vietlott draw records.

Implements the 12 deterministic features (A–L) and 7 modular percentage
mappings (M1–M7) described in SOUL.md.

Digital Root
────────────
digital_root(0) = 0
digital_root(n) = 1 + (n - 1) % 9   for n > 0

Feature Catalogue
─────────────────
A  Main Sum            sum of the 6 main numbers
B  Main Sum Root        digital_root(A)
C  Total Sum            sum of all 7 numbers
D  Total Sum Root       digital_root(C)
E  Main Tens Sum        sum of tens digits of the 6 main numbers
F  Main Tens Sum Root   digital_root(E)
G  Main Units Sum       sum of units digits of the 6 main numbers
H  Main Units Sum Root  digital_root(G)
I  Total Tens Sum       sum of tens digits of all 7 numbers
J  Total Tens Sum Root  digital_root(I)
K  Total Units Sum      sum of units digits of all 7 numbers
L  Total Units Sum Root digital_root(K)

M1–M7 — per-number modular mappings:
  ends_with_pct : last digit d ∈ [1,9] → d×10 ;  d == 0 → 100
  mod5_pct      : x % 5 remainder r:  1→20, 2→40, 3→60, 4→80, 0→100
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List


# ──────────────────────────── helpers ────────────────────────────────

def digital_root(n: int) -> int:
    """Return the single-digit digital root of *n*.

    Recursively sums digits until a single digit remains.
    Special case: digital_root(0) = 0.
    For n > 0: digital_root(n) = 1 + (n - 1) % 9.
    """
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


def _tens_digit(x: int) -> int:
    """Return the tens digit of a non-negative integer."""
    return (x // 10) % 10


def _units_digit(x: int) -> int:
    """Return the units digit of a non-negative integer."""
    return x % 10


def _ends_with_pct(x: int) -> int:
    """Map last digit → percentage.

    Last digit d ∈ [1, 9] → d × 10 %.
    Last digit 0           → 100 %.
    """
    d = _units_digit(x)
    return 100 if d == 0 else d * 10


def _mod5_pct(x: int) -> int:
    """Map x % 5 remainder → percentage.

    1 → 20, 2 → 40, 3 → 60, 4 → 80, 0 → 100.
    """
    r = x % 5
    return 100 if r == 0 else r * 20


# ──────────────────────────── Analyzer ──────────────────────────────

class Analyzer:
    """Feature extraction engine for Vietlott draw records.

    Usage
    ─────
    >>> a = Analyzer()
    >>> features = a.extract_features(record)
    >>> a.process_dataset("dataset_raw.jsonl", "output/")
    >>> a.verify_example()   # asserts SOUL.md example values
    """

    # The 12 scalar feature names in order
    FEATURE_NAMES: List[str] = list("ABCDEFGHIJKL")

    # ────────────── single-record extraction ──────────────

    def extract_features(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all features from a single draw record.

        Parameters
        ──────────
        record : dict
            Must contain at minimum ``id``, ``date``, and ``result``
            (a list of 7 integers: 6 main + 1 special).

        Returns
        ───────
        dict with keys:
            id, date, result,
            A–L (int),
            M1–M7 (each a dict with ``ends_with_pct`` and ``mod5_pct``).
        """
        result: List[int] = record["result"]
        main: List[int] = result[:6]
        all_nums: List[int] = result[:7]

        # ── A–D: sums & their roots ──
        a_val = sum(main)
        b_val = digital_root(a_val)
        c_val = sum(all_nums)
        d_val = digital_root(c_val)

        # ── E–H: tens / units digits of main numbers ──
        e_val = sum(_tens_digit(x) for x in main)
        f_val = digital_root(e_val)
        g_val = sum(_units_digit(x) for x in main)
        h_val = digital_root(g_val)

        # ── I–L: tens / units digits of ALL 7 numbers ──
        i_val = sum(_tens_digit(x) for x in all_nums)
        j_val = digital_root(i_val)
        k_val = sum(_units_digit(x) for x in all_nums)
        l_val = digital_root(k_val)

        # ── M1–M7: per-number modular mappings ──
        m_features: Dict[str, Dict[str, int]] = {}
        for idx, x in enumerate(all_nums, start=1):
            m_features[f"M{idx}"] = {
                "ends_with_pct": _ends_with_pct(x),
                "mod5_pct": _mod5_pct(x),
            }

        features: Dict[str, Any] = {
            "id": record["id"],
            "date": record.get("date", ""),
            "result": result,
            "A": a_val,
            "B": b_val,
            "C": c_val,
            "D": d_val,
            "E": e_val,
            "F": f_val,
            "G": g_val,
            "H": h_val,
            "I": i_val,
            "J": j_val,
            "K": k_val,
            "L": l_val,
        }
        features.update(m_features)
        return features

    # ────────────── full-dataset processing ──────────────

    def process_dataset(
        self,
        input_path: str,
        output_dir: str,
    ) -> List[Dict[str, Any]]:
        """Process every record in *input_path* and persist features.

        Creates ``output_dir`` if it doesn't exist, then writes:
        - ``features.jsonl`` — one JSON object per line
        - ``features.csv``  — flat CSV (M-features flattened)

        Parameters
        ──────────
        input_path : str
            Path to the raw JSONL dataset.
        output_dir : str
            Directory where output files are written.

        Returns
        ───────
        list[dict]  — the full list of extracted feature dicts.
        """
        os.makedirs(output_dir, exist_ok=True)

        all_features: List[Dict[str, Any]] = []

        with open(input_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                feat = self.extract_features(record)
                all_features.append(feat)

        # ── Write features.jsonl ──
        jsonl_path = os.path.join(output_dir, "features.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as fh:
            for feat in all_features:
                fh.write(json.dumps(feat, ensure_ascii=False) + "\n")

        # ── Write features.csv (flat) ──
        csv_path = os.path.join(output_dir, "features.csv")
        self._write_csv(csv_path, all_features)

        return all_features

    # ────────────── verification ──────────────

    def verify_example(self) -> None:
        """Assert correctness against the SOUL.md reference draw.

        Draw #00014: result = [8, 20, 27, 35, 36, 47, 18]
        Expected: A=173, B=2, C=191, D=2, E=14, F=5,
                  G=33,  H=6, I=15,  J=6, K=41, L=5

        Raises ``AssertionError`` if any value is wrong.
        """
        example_record: Dict[str, Any] = {
            "date": "2017-08-31",
            "id": "00014",
            "result": [8, 20, 27, 35, 36, 47, 18],
            "process_time": "2022-05-07 07:56:43.143266",
        }

        expected: Dict[str, int] = {
            "A": 173, "B": 2,
            "C": 191, "D": 2,
            "E": 14,  "F": 5,
            "G": 33,  "H": 6,
            "I": 15,  "J": 6,
            "K": 41,  "L": 5,
        }

        feat = self.extract_features(example_record)

        for key, exp_val in expected.items():
            actual = feat[key]
            assert actual == exp_val, (
                f"Feature {key}: expected {exp_val}, got {actual}"
            )

        # Spot-check M-features for draw #00014
        # Number 8:  ends_with=80, mod5=60  (8%5=3→60)
        assert feat["M1"]["ends_with_pct"] == 80
        assert feat["M1"]["mod5_pct"] == 60

        # Number 20: ends_with=100, mod5=100  (20%5=0→100)
        assert feat["M2"]["ends_with_pct"] == 100
        assert feat["M2"]["mod5_pct"] == 100

        # Number 18 (special): ends_with=80, mod5=60  (18%5=3→60)
        assert feat["M7"]["ends_with_pct"] == 80
        assert feat["M7"]["mod5_pct"] == 60

    # ────────────── internal helpers ──────────────

    @staticmethod
    def _write_csv(
        path: str,
        features: List[Dict[str, Any]],
    ) -> None:
        """Write features to a flat CSV file.

        M-features are flattened into columns like
        ``M1_ends_with_pct``, ``M1_mod5_pct``, etc.
        """
        if not features:
            return

        # Build header from the first record
        scalar_keys = ["id", "date", "result"] + list("ABCDEFGHIJKL")
        m_keys: List[str] = []
        for i in range(1, 8):
            m_keys.append(f"M{i}_ends_with_pct")
            m_keys.append(f"M{i}_mod5_pct")

        header = scalar_keys + m_keys

        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)

            for feat in features:
                row: List[Any] = []
                for k in scalar_keys:
                    val = feat[k]
                    # Serialize the result list as a JSON string in CSV
                    if k == "result":
                        val = json.dumps(val)
                    row.append(val)

                for i in range(1, 8):
                    m = feat[f"M{i}"]
                    row.append(m["ends_with_pct"])
                    row.append(m["mod5_pct"])

                writer.writerow(row)
