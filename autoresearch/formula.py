"""
Formula system for the Auto-Research Engine.

Handles formula representation, safe evaluation, and scoring against
the lottery feature dataset. Formulas are Python expression strings that
reference feature history using bracket notation (e.g., A[t-1], B[t-2]).
"""

import json
import logging
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature definitions
# ---------------------------------------------------------------------------

FEATURE_NAMES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

# Digital root features (categorical, values 0–9)
DIGITAL_ROOT_FEATURES = {'B', 'D', 'F', 'H', 'J', 'L'}

# Numeric (continuous) features
NUMERIC_FEATURES = {'A', 'C', 'E', 'G', 'I', 'K'}

# Modular mapping features
MODULAR_FEATURES = [f'M{i}' for i in range(1, 8)]

# Raw number prediction slots
RAW_SLOTS = [f'raw_{i}' for i in range(1, 8)]

ALL_PREDICTABLE = FEATURE_NAMES + RAW_SLOTS


# ---------------------------------------------------------------------------
# Safe math namespace
# ---------------------------------------------------------------------------

def digital_root(n: int | float) -> int:
    """
    Compute the digital root of a number.

    Repeatedly sums digits until a single digit remains.
    digital_root(0) = 0, digital_root(n) = 1 + (n-1) % 9 for n > 0.
    """
    n = int(abs(n))
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


def _safe_div(a: float, b: float) -> float:
    """Safe division — returns 0 on divide-by-zero."""
    if b == 0:
        return 0.0
    return a / b


def _safe_floordiv(a: float, b: float) -> float:
    """Safe floor division — returns 0 on divide-by-zero."""
    if b == 0:
        return 0
    return a // b


def _safe_mod(a: float, b: float) -> float:
    """Safe modulo — returns 0 on mod-by-zero."""
    if b == 0:
        return 0
    return a % b


# Build the restricted namespace for safe eval
SAFE_NAMESPACE: dict[str, Any] = {
    '__builtins__': {},  # No builtins
    'abs': abs,
    'min': min,
    'max': max,
    'sum': sum,
    'round': round,
    'int': int,
    'float': float,
    'digital_root': digital_root,
    'math': math,
}


# ---------------------------------------------------------------------------
# Formula parsing — convert bracket notation to Python variables
# ---------------------------------------------------------------------------

# Pattern: FEATURE[t], FEATURE[t-N]
_VAR_PATTERN = re.compile(r'([A-L]|M[1-7]|raw_[1-7])\[t(?:-(\d+))?\]')


def _extract_references(expression: str) -> list[tuple[str, int]]:
    """
    Extract all variable references from a formula expression.

    Returns list of (feature_name, lag) tuples.
    E.g., "A[t-1] + B[t-2]" → [('A', 1), ('B', 2)]
    """
    refs = []
    for match in _VAR_PATTERN.finditer(expression):
        feature = match.group(1)
        lag = int(match.group(2)) if match.group(2) else 0
        refs.append((feature, lag))
    return refs


def _resolve_variables(
    expression: str,
    history: list[dict],
    target: Optional[dict] = None,
) -> str:
    """
    Replace bracket-notation variables with actual numeric values.

    Args:
        expression: Formula string with variables like A[t-1].
        history: List of feature dicts, ordered newest-first.
                 history[0] = t-1, history[1] = t-2, etc.
        target: Optional dict for t (current timestep). Only used for
                validation, not in formulas.

    Returns:
        Python expression string with variables replaced by numbers.

    Raises:
        ValueError: If a referenced lag exceeds history length.
    """
    def replacer(match: re.Match) -> str:
        feature = match.group(1)
        lag = int(match.group(2)) if match.group(2) else 0

        if lag == 0:
            # Referencing t (current) — only valid if target is provided
            if target is None:
                raise ValueError(
                    f"Formula references {feature}[t] (current timestep) "
                    "which is the prediction target and cannot be used as input."
                )
            value = target.get(feature, 0)
        else:
            # lag >= 1: index into history (0-indexed: lag-1)
            idx = lag - 1
            if idx >= len(history):
                raise ValueError(
                    f"Formula references {feature}[t-{lag}] but history "
                    f"only has {len(history)} entries."
                )
            value = history[idx].get(feature, 0)

        return str(value)

    return _VAR_PATTERN.sub(replacer, expression)


def safe_eval(expression: str, history: list[dict]) -> Optional[float]:
    """
    Safely evaluate a formula expression given feature history.

    Args:
        expression: Formula string with bracket-notation variables.
        history: List of feature dicts, newest first.

    Returns:
        Numeric result, or None if evaluation fails.
    """
    try:
        resolved = _resolve_variables(expression, history)

        # Replace unsafe operators with safe versions
        # We do this by wrapping division/modulo in the namespace
        namespace = dict(SAFE_NAMESPACE)
        namespace['_safe_div'] = _safe_div
        namespace['_safe_floordiv'] = _safe_floordiv
        namespace['_safe_mod'] = _safe_mod

        result = eval(resolved, namespace)  # noqa: S307

        # Validate result
        if isinstance(result, (int, float)):
            if math.isnan(result) or math.isinf(result):
                return None
            return result
        return None

    except Exception as e:
        logger.debug("Formula eval failed: '%s' → %s", expression, e)
        return None


# ---------------------------------------------------------------------------
# FormulaSet — a collection of formulas for all features
# ---------------------------------------------------------------------------

class FormulaSet:
    """
    A set of prediction formulas for lottery features.

    Each formula maps a feature name to a Python expression string
    that references historical feature values using bracket notation.

    Example:
        fs = FormulaSet({
            'A': '(A[t-1] + A[t-2]) / 2',
            'B': 'digital_root(A[t-1] + A[t-2])',
        })
    """

    def __init__(
        self,
        formulas: Optional[dict[str, str]] = None,
        description: str = '',
    ):
        """
        Initialize with a dict of feature→expression mappings.

        Args:
            formulas: Dict mapping feature names to expression strings.
            description: Human-readable description of this formula set.
        """
        self.formulas: dict[str, str] = formulas or {}
        self.description = description

        # Validate formula keys
        valid_keys = set(FEATURE_NAMES + RAW_SLOTS)
        invalid = set(self.formulas.keys()) - valid_keys
        if invalid:
            logger.warning("Unknown formula keys will be ignored: %s", invalid)

    def evaluate(
        self,
        history: list[dict],
        target: Optional[dict] = None,
    ) -> dict[str, Optional[float]]:
        """
        Evaluate all formulas given a history window.

        Args:
            history: List of feature dicts, newest-first.
                     history[0] = most recent draw (t-1).
            target: Optional actual values for scoring.

        Returns:
            Dict of {feature_name: predicted_value}.
        """
        predictions: dict[str, Optional[float]] = {}

        for feature, expression in self.formulas.items():
            predictions[feature] = safe_eval(expression, history)

        return predictions

    def score(self, dataset_sequences: list[dict]) -> float:
        """
        Compute prediction score across a dataset of sequences.

        Each sequence dict should have:
            - 'history': list of feature dicts (newest first)
            - 'target': dict of actual feature values

        Score = weighted combination of MAE (numeric features) +
                cross-entropy (digital root features).
        Lower is better. 0.0 = perfect.

        Args:
            dataset_sequences: List of sequence dicts from Dataset.get_sequences().

        Returns:
            Combined prediction score (lower = better).
        """
        if not dataset_sequences:
            return float('inf')

        mae_sums: dict[str, float] = {}
        mae_counts: dict[str, int] = {}
        ce_sums: dict[str, float] = {}
        ce_counts: dict[str, int] = {}

        for seq in dataset_sequences:
            history = seq['history']
            target = seq['target']
            predictions = self.evaluate(history)

            for feature in FEATURE_NAMES:
                if feature not in self.formulas:
                    continue

                pred = predictions.get(feature)
                actual = target.get(feature)

                if pred is None or actual is None:
                    continue

                if feature in DIGITAL_ROOT_FEATURES:
                    # Cross-entropy for categorical features (digital roots 0–9)
                    ce = _cross_entropy_single(pred, actual, num_classes=10)
                    ce_sums[feature] = ce_sums.get(feature, 0.0) + ce
                    ce_counts[feature] = ce_counts.get(feature, 0) + 1
                else:
                    # MAE for numeric features
                    error = abs(float(pred) - float(actual))
                    mae_sums[feature] = mae_sums.get(feature, 0.0) + error
                    mae_counts[feature] = mae_counts.get(feature, 0) + 1

        # Compute averages
        total_score = 0.0
        num_scored = 0

        # Numeric MAE (normalize by typical range)
        numeric_ranges = {
            'A': 309.0, 'C': 357.0, 'E': 30.0,
            'G': 54.0, 'I': 35.0, 'K': 63.0,
        }
        for feature, total_error in mae_sums.items():
            count = mae_counts[feature]
            if count > 0:
                avg_mae = total_error / count
                # Normalize to 0–1 range
                range_val = numeric_ranges.get(feature, 100.0)
                normalized = avg_mae / range_val if range_val > 0 else avg_mae
                total_score += normalized
                num_scored += 1

        # Categorical cross-entropy (already 0–1 scale after normalization)
        max_ce = -math.log(1.0 / 10)  # ≈ 2.302 (uniform over 10 classes)
        for feature, total_ce in ce_sums.items():
            count = ce_counts[feature]
            if count > 0:
                avg_ce = total_ce / count
                normalized = avg_ce / max_ce if max_ce > 0 else avg_ce
                total_score += normalized
                num_scored += 1

        if num_scored == 0:
            return float('inf')

        # Average across all scored features
        return total_score / num_scored

    def score_detailed(self, dataset_sequences: list[dict]) -> dict:
        """
        Compute per-feature scores for diagnostics.

        Returns:
            Dict with 'total', 'per_feature', and 'num_sequences' keys.
        """
        if not dataset_sequences:
            return {'total': float('inf'), 'per_feature': {}, 'num_sequences': 0}

        feature_errors: dict[str, list[float]] = {f: [] for f in FEATURE_NAMES}
        numeric_ranges = {
            'A': 309.0, 'C': 357.0, 'E': 30.0,
            'G': 54.0, 'I': 35.0, 'K': 63.0,
        }
        max_ce = -math.log(1.0 / 10)

        for seq in dataset_sequences:
            history = seq['history']
            target = seq['target']
            predictions = self.evaluate(history)

            for feature in FEATURE_NAMES:
                if feature not in self.formulas:
                    continue
                pred = predictions.get(feature)
                actual = target.get(feature)
                if pred is None or actual is None:
                    continue

                if feature in DIGITAL_ROOT_FEATURES:
                    ce = _cross_entropy_single(pred, actual, num_classes=10)
                    feature_errors[feature].append(ce / max_ce)
                else:
                    error = abs(float(pred) - float(actual))
                    range_val = numeric_ranges.get(feature, 100.0)
                    feature_errors[feature].append(error / range_val)

        per_feature = {}
        scored_avgs = []
        for feature in FEATURE_NAMES:
            errors = feature_errors[feature]
            if errors:
                avg = sum(errors) / len(errors)
                per_feature[feature] = {
                    'score': round(avg, 6),
                    'count': len(errors),
                }
                scored_avgs.append(avg)
            else:
                per_feature[feature] = {'score': None, 'count': 0}

        total = sum(scored_avgs) / len(scored_avgs) if scored_avgs else float('inf')

        return {
            'total': round(total, 6),
            'per_feature': per_feature,
            'num_sequences': len(dataset_sequences),
        }

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            'description': self.description,
            'formulas': dict(self.formulas),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FormulaSet':
        """Deserialize from a dict."""
        return cls(
            formulas=data.get('formulas', {}),
            description=data.get('description', ''),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'FormulaSet':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def save(self, path: str | Path) -> None:
        """Save to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> 'FormulaSet':
        """Load from a JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))

    def get_max_lag(self) -> int:
        """
        Determine the maximum lag referenced across all formulas.

        Returns:
            Maximum lag value (e.g., 5 if the deepest ref is A[t-5]).
        """
        max_lag = 0
        for expression in self.formulas.values():
            refs = _extract_references(expression)
            for _, lag in refs:
                max_lag = max(max_lag, lag)
        return max(max_lag, 1)  # At least 1

    @staticmethod
    def default() -> 'FormulaSet':
        """
        Create a simple baseline formula set using naive last-value prediction.

        Returns:
            FormulaSet with simple formulas for all 12 features.
        """
        return FormulaSet(
            formulas={
                'A': 'A[t-1]',
                'B': 'B[t-1]',
                'C': 'C[t-1]',
                'D': 'D[t-1]',
                'E': 'E[t-1]',
                'F': 'F[t-1]',
                'G': 'G[t-1]',
                'H': 'H[t-1]',
                'I': 'I[t-1]',
                'J': 'J[t-1]',
                'K': 'K[t-1]',
                'L': 'L[t-1]',
            },
            description='Naive baseline: predict last observed value for each feature.',
        )

    def __repr__(self) -> str:
        n = len(self.formulas)
        return f"FormulaSet({n} formulas, desc='{self.description[:50]}')"


# ---------------------------------------------------------------------------
# FormulaEvaluator — higher-level evaluation utilities
# ---------------------------------------------------------------------------

class FormulaEvaluator:
    """
    High-level evaluator that wraps FormulaSet scoring with dataset integration.

    Provides convenience methods for train/test evaluation and
    comparative analysis between formula sets.
    """

    def __init__(self, window_size: int = 10):
        """
        Args:
            window_size: Number of historical draws to use as context.
        """
        self.window_size = window_size

    def evaluate_on_sequences(
        self,
        formula_set: FormulaSet,
        sequences: list[dict],
    ) -> dict:
        """
        Evaluate a formula set on pre-built sequences.

        Args:
            formula_set: The formulas to evaluate.
            sequences: List of {history, target} dicts.

        Returns:
            Dict with 'score', 'detailed', and 'num_predictions'.
        """
        score = formula_set.score(sequences)
        detailed = formula_set.score_detailed(sequences)

        return {
            'score': score,
            'detailed': detailed,
            'num_predictions': len(sequences),
        }

    def compare(
        self,
        formula_a: FormulaSet,
        formula_b: FormulaSet,
        sequences: list[dict],
    ) -> dict:
        """
        Compare two formula sets on the same sequences.

        Returns:
            Dict with scores for both and improvement delta.
        """
        score_a = formula_a.score(sequences)
        score_b = formula_b.score(sequences)
        improvement = score_a - score_b  # Positive = B is better

        return {
            'score_a': score_a,
            'score_b': score_b,
            'improvement': improvement,
            'better': 'B' if improvement > 0 else 'A' if improvement < 0 else 'tied',
        }


# ---------------------------------------------------------------------------
# Helper: cross-entropy for single prediction
# ---------------------------------------------------------------------------

def _cross_entropy_single(
    predicted: float,
    actual: float,
    num_classes: int = 10,
) -> float:
    """
    Compute cross-entropy loss for a single categorical prediction.

    Treats the predicted value as a point estimate and computes
    the negative log probability of the actual class under a
    simple distance-based soft distribution.

    Args:
        predicted: Predicted value (continuous).
        actual: Actual value (integer class).
        num_classes: Number of possible classes.

    Returns:
        Cross-entropy loss value (non-negative).
    """
    predicted = int(round(predicted)) if predicted is not None else 0
    actual = int(actual)

    # Clamp to valid range
    predicted = max(0, min(predicted, num_classes - 1))
    actual = max(0, min(actual, num_classes - 1))

    # Simple: if prediction matches, low loss; otherwise, high loss
    # Using a soft assignment with exponential decay
    epsilon = 1e-7
    if predicted == actual:
        prob = 0.8  # High confidence for correct prediction
    else:
        distance = abs(predicted - actual)
        # Exponential decay with distance
        prob = 0.2 * math.exp(-0.5 * distance) / max(num_classes - 1, 1)
        prob = max(prob, epsilon)

    return -math.log(prob)


# ---------------------------------------------------------------------------
# LLM response parser
# ---------------------------------------------------------------------------

def parse_formula_response(response_text: str) -> Optional[FormulaSet]:
    """
    Parse an LLM response to extract a FormulaSet.

    Looks for a JSON block (```json ... ```) in the response text.
    Falls back to finding the first { ... } JSON object.

    Args:
        response_text: Raw LLM output text.

    Returns:
        FormulaSet if parsing succeeds, None otherwise.
    """
    # Strategy 1: Find ```json ... ``` block
    json_match = re.search(r'```json\s*\n(.*?)\n\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Strategy 2: Find outermost { ... }
        brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if brace_match:
            json_str = brace_match.group(0)
        else:
            logger.warning("No JSON found in LLM response")
            return None

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON from response: %s", e)
        return None

    # Extract formulas — support both flat and nested formats
    if 'formulas' in data:
        formulas = data['formulas']
        description = data.get('description', '')
    else:
        # Assume the entire object is formulas
        description = data.pop('description', '')
        formulas = data

    # Validate: only keep recognized feature keys with string values
    valid_keys = set(FEATURE_NAMES + RAW_SLOTS)
    clean_formulas = {}
    for key, expr in formulas.items():
        if key in valid_keys and isinstance(expr, str):
            # Basic sanitization: reject dangerous patterns
            if _is_safe_expression(expr):
                clean_formulas[key] = expr
            else:
                logger.warning("Rejected unsafe formula for %s: %s", key, expr)

    if not clean_formulas:
        logger.warning("No valid formulas extracted from response")
        return None

    return FormulaSet(formulas=clean_formulas, description=description)


def _is_safe_expression(expression: str) -> bool:
    """
    Check if a formula expression is safe to evaluate.

    Rejects imports, function definitions, attribute access to dangerous
    builtins, and other potentially harmful patterns.

    Args:
        expression: The formula expression string.

    Returns:
        True if the expression appears safe.
    """
    # Reject dangerous patterns
    dangerous = [
        'import ', '__', 'exec(', 'eval(', 'compile(', 'open(',
        'getattr(', 'setattr(', 'delattr(', 'globals(', 'locals(',
        'dir(', 'vars(', 'type(', 'isinstance(', 'issubclass(',
        'lambda ', 'class ', 'def ', 'yield ', 'async ', 'await ',
        'os.', 'sys.', 'subprocess', 'shutil', 'pathlib',
        'input(', 'print(', 'breakpoint(',
    ]
    expr_lower = expression.lower()
    for pattern in dangerous:
        if pattern.lower() in expr_lower:
            return False

    # Check length — very long expressions are suspicious
    if len(expression) > 500:
        return False

    return True
