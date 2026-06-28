"""
Core package for the Vietlott Deterministic Universe Pipeline.

Exports the primary classes used across the pipeline:
- Analyzer: Feature extraction engine (12 features A-L + 7 modular mappings M1-M7)
- DatasetManager: Train/test splitting and sequence windowing
- Brain / BrainManager: Leaderboard persistence for top-5 formula brains
"""

from core.analyzer import Analyzer
from core.dataset import DatasetManager
from core.brain import Brain, BrainManager

__all__ = ["Analyzer", "DatasetManager", "Brain", "BrainManager"]
