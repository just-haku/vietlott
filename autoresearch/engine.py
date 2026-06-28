"""
Research Engine — the main autonomous loop for formula discovery.

Orchestrates the cycle: build context → prompt LLM → parse formulas →
evaluate → keep improvements → log → repeat.

Thread-safe with graceful stop support via threading.Event.
"""

import csv
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from autoresearch.formula import (
    FormulaEvaluator,
    FormulaSet,
    parse_formula_response,
)
from autoresearch.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    'window_size': 10,
    'max_experiments': 100,
    'temperature': 0.7,
    'max_tokens': 4096,
    'results_path': 'data/results.tsv',
    'program_path': None,  # Auto-detected
    'improvement_threshold': 0.0001,  # Minimum score improvement to keep
    'context_history_size': 10,  # Number of recent experiments to show LLM
}


class ResearchEngine:
    """
    Autonomous research engine that uses LLM-guided formula generation
    to discover deterministic patterns in lottery data.

    The engine runs a loop:
    1. Build context from current best formulas and recent history
    2. Send to LLM with program.md instructions
    3. Parse LLM response to extract new FormulaSet
    4. Evaluate on train set (fit check), then test set (score)
    5. If test score improves → submit to BrainManager
    6. Log results to TSV
    7. Call callback for live UI updates
    8. Repeat

    Usage:
        engine = ResearchEngine(dataset, brain_manager, llm_client)
        engine.run(max_experiments=50, callback=my_callback)
    """

    def __init__(
        self,
        dataset: Any,
        brain_manager: Any,
        llm_client: LLMClient,
        config: Optional[dict] = None,
    ):
        """
        Initialize the research engine.

        Args:
            dataset: A Dataset instance with get_train(), get_test(),
                     get_sequences(window_size) methods.
            brain_manager: A BrainManager instance for persisting top brains.
            llm_client: An LLMClient instance for LLM API calls.
            config: Optional config overrides.
        """
        self._dataset = dataset
        self._brain_manager = brain_manager
        self._llm_client = llm_client
        self._config = {**DEFAULT_CONFIG, **(config or {})}

        # State
        self._experiment_history: list[dict] = []
        self._best_score: float = float('inf')
        self._best_formulas: Optional[FormulaSet] = None
        self._experiment_count: int = 0
        self._status: str = 'idle'  # idle, running, stopping, stopped
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Evaluator
        self._evaluator = FormulaEvaluator(
            window_size=self._config['window_size']
        )

        # Pre-build dataset sequences (cached for efficiency)
        self._train_sequences: Optional[list[dict]] = None
        self._test_sequences: Optional[list[dict]] = None

        # Load program.md
        self._program_template = self._load_program()

        # Ensure results directory exists
        results_path = Path(self._config['results_path'])
        results_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize with baseline if no brains exist
        self._initialize_baseline()

        logger.info("ResearchEngine initialized with config: %s", self._config)

    def _load_program(self) -> str:
        """Load the LLM program instructions from program.md."""
        program_path = self._config.get('program_path')
        if program_path:
            p = Path(program_path)
        else:
            p = Path(__file__).resolve().parent / 'program.md'

        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                return f.read()

        logger.warning("program.md not found at %s, using minimal prompt", p)
        return (
            "You are a formula discovery agent. Propose formulas that predict "
            "lottery features A-L from historical data. Output JSON with "
            "{description, formulas: {feature: expression}}."
        )

    def _get_sequences(self, split: str = 'train') -> list[dict]:
        """
        Get or cache dataset sequences for the given split.

        Args:
            split: 'train' or 'test'.

        Returns:
            List of {history, target} sequence dicts.
        """
        if split == 'train':
            if self._train_sequences is None:
                self._train_sequences = self._dataset.get_sequences(
                    window_size=self._config['window_size'],
                    split='train',
                )
            return self._train_sequences
        else:
            if self._test_sequences is None:
                self._test_sequences = self._dataset.get_sequences(
                    window_size=self._config['window_size'],
                    split='test',
                )
            return self._test_sequences

    def _initialize_baseline(self) -> None:
        """
        Initialize with baseline formulas if no brains exist.

        Sets the default naive predictor as the starting point so
        the LLM has something to improve upon.
        """
        try:
            best_brain = self._brain_manager.get_best()
            if best_brain and hasattr(best_brain, 'formulas') and best_brain.formulas:
                self._best_formulas = FormulaSet.from_dict({
                    'formulas': best_brain.formulas,
                    'description': getattr(best_brain, 'description', ''),
                })
                self._best_score = getattr(
                    best_brain, 'test_entropy_score', float('inf')
                )
                logger.info(
                    "Loaded best brain: score=%.6f, desc='%s'",
                    self._best_score,
                    self._best_formulas.description[:50],
                )
                return
        except Exception as e:
            logger.debug("No existing brains found: %s", e)

        # Fall back to baseline
        baseline = FormulaSet.default()
        try:
            test_sequences = self._get_sequences('test')
            self._best_score = baseline.score(test_sequences)
        except Exception:
            self._best_score = float('inf')

        self._best_formulas = baseline
        logger.info("Initialized with baseline. Score: %.6f", self._best_score)

    def _build_context(self) -> str:
        """
        Build the context string for the LLM prompt.

        Includes current best formulas, recent experiment history,
        and feature statistics.
        """
        # Current best formulas
        if self._best_formulas:
            formulas_str = json.dumps(self._best_formulas.to_dict(), indent=2)
        else:
            formulas_str = "(No formulas yet — this is the first experiment)"

        # Recent experiments
        recent = self._experiment_history[-self._config['context_history_size']:]
        if recent:
            history_lines = []
            for exp in recent:
                status_icon = '✓' if exp.get('improved') else '✗'
                history_lines.append(
                    f"  {status_icon} Exp #{exp['id']}: "
                    f"train={exp.get('train_score', '?'):.4f}, "
                    f"test={exp.get('test_score', '?'):.4f} — "
                    f"{exp.get('description', 'no description')[:80]}"
                )
            history_str = '\n'.join(history_lines)
        else:
            history_str = "(No experiments yet — you are the first!)"

        # Best description
        best_desc = (
            self._best_formulas.description
            if self._best_formulas else "None"
        )

        # Fill template
        prompt = self._program_template
        prompt = prompt.replace('{current_state}', formulas_str)
        prompt = prompt.replace(
            '{best_score}',
            f"{self._best_score:.6f}" if self._best_score != float('inf') else "N/A (first run)"
        )
        prompt = prompt.replace('{best_description}', best_desc)
        prompt = prompt.replace('{recent_history}', history_str)

        return prompt

    def run(
        self,
        max_experiments: Optional[int] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> list[dict]:
        """
        Run the main research loop.

        Args:
            max_experiments: Maximum number of experiments to run.
                            None = use config default.
            callback: Optional function called after each experiment
                      with the experiment result dict.

        Returns:
            List of all experiment result dicts.
        """
        max_exp = max_experiments or self._config['max_experiments']

        with self._lock:
            if self._status == 'running':
                logger.warning("Engine is already running")
                return self._experiment_history
            self._status = 'running'
            self._stop_event.clear()

        logger.info("Starting research loop (max_experiments=%d)", max_exp)

        try:
            while self._experiment_count < max_exp:
                if self._stop_event.is_set():
                    logger.info("Stop signal received. Halting.")
                    break

                result = self.run_single_experiment()

                if callback:
                    try:
                        callback(result)
                    except Exception as e:
                        logger.error("Callback error: %s", e)

        except Exception as e:
            logger.error("Research loop crashed: %s", e, exc_info=True)

        finally:
            with self._lock:
                self._status = 'stopped' if self._stop_event.is_set() else 'idle'

        logger.info(
            "Research loop finished. %d experiments, best score: %.6f",
            self._experiment_count,
            self._best_score,
        )
        return self._experiment_history

    def run_single_experiment(self) -> dict:
        """
        Execute a single research experiment.

        Returns:
            Experiment result dict with keys:
                id, timestamp, description, train_score, test_score,
                improved, status, formulas, duration_s
        """
        experiment_id = self._experiment_count + 1
        timestamp = datetime.now(timezone.utc).isoformat()
        start_time = time.monotonic()

        result: dict[str, Any] = {
            'id': experiment_id,
            'timestamp': timestamp,
            'description': '',
            'train_score': float('inf'),
            'test_score': float('inf'),
            'improved': False,
            'status': 'pending',
            'formulas': None,
            'duration_s': 0.0,
        }

        try:
            # 1. Build context prompt
            prompt = self._build_context()

            # 2. Call LLM
            logger.info("Experiment #%d: calling LLM...", experiment_id)
            llm_response = self._llm_client.generate(
                prompt=prompt,
                temperature=self._config['temperature'],
                max_tokens=self._config['max_tokens'],
            )

            # 3. Parse response
            new_formulas = parse_formula_response(llm_response)
            if new_formulas is None:
                result['status'] = 'parse_error'
                result['description'] = 'Failed to parse LLM response'
                logger.warning("Experiment #%d: parse error", experiment_id)
                self._finalize_experiment(result, start_time)
                return result

            result['description'] = new_formulas.description
            result['formulas'] = new_formulas.to_dict()

            # 4. Evaluate on train set
            train_sequences = self._get_sequences('train')
            train_score = new_formulas.score(train_sequences)
            result['train_score'] = round(train_score, 6)

            # 5. Evaluate on test set
            test_sequences = self._get_sequences('test')
            test_score = new_formulas.score(test_sequences)
            result['test_score'] = round(test_score, 6)

            logger.info(
                "Experiment #%d: train=%.6f, test=%.6f (best=%.6f)",
                experiment_id, train_score, test_score, self._best_score,
            )

            # 6. Check for improvement
            threshold = self._config['improvement_threshold']
            if test_score < (self._best_score - threshold):
                result['improved'] = True
                result['status'] = 'improved'
                self._best_score = test_score
                self._best_formulas = new_formulas

                # Submit to BrainManager
                self._submit_to_brain_manager(new_formulas, result)

                logger.info(
                    "★ Experiment #%d: NEW BEST! score=%.6f (%s)",
                    experiment_id, test_score, new_formulas.description[:50],
                )
            else:
                result['status'] = 'no_improvement'

        except Exception as e:
            result['status'] = 'error'
            result['description'] = f'Error: {str(e)[:200]}'
            logger.error(
                "Experiment #%d failed: %s", experiment_id, e, exc_info=True
            )

        self._finalize_experiment(result, start_time)
        return result

    def _finalize_experiment(self, result: dict, start_time: float) -> None:
        """Record experiment results and update counters."""
        result['duration_s'] = round(time.monotonic() - start_time, 2)

        with self._lock:
            self._experiment_history.append(result)
            self._experiment_count += 1

        # Log to TSV
        self._log_result(result)

    def _submit_to_brain_manager(
        self,
        formula_set: FormulaSet,
        result: dict,
    ) -> None:
        """
        Submit an improved formula set to the BrainManager for persistence.

        Creates a Brain object compatible with core.brain.Brain and
        submits it via brain_manager.submit().
        """
        try:
            brain_id = str(uuid.uuid4())[:8]
            brain_data = {
                'id': brain_id,
                'formulas': formula_set.formulas,
                'description': formula_set.description,
                'test_entropy_score': result['test_score'],
                'train_entropy_score': result['train_score'],
                'created_at': result['timestamp'],
                'experiment_id': result['id'],
            }

            # Try Brain dataclass first, fall back to dict submission
            try:
                from core.brain import Brain
                brain = Brain(**brain_data)
                self._brain_manager.submit(brain)
            except (ImportError, TypeError):
                # BrainManager might accept dicts directly
                self._brain_manager.submit(brain_data)

            logger.info("Brain %s submitted to BrainManager", brain_id)

        except Exception as e:
            logger.error("Failed to submit brain: %s", e)

    def _log_result(self, result: dict) -> None:
        """Append experiment result to the TSV log file."""
        results_path = Path(self._config['results_path'])
        results_path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = results_path.exists()
        try:
            with open(results_path, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter='\t')
                if not file_exists:
                    writer.writerow([
                        'experiment_id', 'timestamp', 'description',
                        'train_score', 'test_score', 'status', 'improved',
                        'duration_s',
                    ])
                writer.writerow([
                    result['id'],
                    result['timestamp'],
                    result.get('description', '')[:200],
                    result.get('train_score', ''),
                    result.get('test_score', ''),
                    result.get('status', ''),
                    result.get('improved', False),
                    result.get('duration_s', ''),
                ])
        except IOError as e:
            logger.error("Failed to write results TSV: %s", e)

    def stop(self) -> None:
        """
        Signal the engine to stop after the current experiment completes.

        This is thread-safe and can be called from any thread.
        """
        logger.info("Stop requested")
        with self._lock:
            self._status = 'stopping'
        self._stop_event.set()

    def get_status(self) -> dict:
        """
        Get current engine status.

        Returns:
            Dict with status, experiment_count, best_score, etc.
        """
        with self._lock:
            return {
                'status': self._status,
                'experiment_count': self._experiment_count,
                'best_score': self._best_score,
                'best_description': (
                    self._best_formulas.description
                    if self._best_formulas else None
                ),
                'total_improvements': sum(
                    1 for e in self._experiment_history if e.get('improved')
                ),
                'config': dict(self._config),
            }

    def get_history(self) -> list[dict]:
        """
        Get all experiment results.

        Returns:
            List of experiment result dicts (copies to prevent mutation).
        """
        with self._lock:
            return list(self._experiment_history)

    def get_best_formulas(self) -> Optional[FormulaSet]:
        """Return the current best FormulaSet, or None."""
        return self._best_formulas

    def __repr__(self) -> str:
        return (
            f"ResearchEngine(experiments={self._experiment_count}, "
            f"best_score={self._best_score:.6f}, "
            f"status='{self._status}')"
        )
