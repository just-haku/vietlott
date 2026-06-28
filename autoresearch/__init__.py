"""
Auto-Research Engine for the Vietlott Deterministic Universe Pipeline.

This package implements an autonomous research loop that uses LLM-guided
formula generation to discover deterministic patterns in lottery data.

Components:
    - LLMClient: Multi-provider LLM client (Google, Groq, DeepSeek, OpenAI, Anthropic)
    - FormulaSet: Formula representation, evaluation, and scoring
    - ResearchEngine: Main research loop orchestrator
"""

from autoresearch.llm_client import LLMClient
from autoresearch.formula import FormulaSet, FormulaEvaluator
from autoresearch.engine import ResearchEngine

__all__ = ['LLMClient', 'FormulaSet', 'FormulaEvaluator', 'ResearchEngine']
__version__ = '0.1.0'
