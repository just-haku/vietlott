#!/usr/bin/env python3
"""
run_research.py — Start the auto-research loop to discover predictive formulas.

Usage:
    python scripts/run_research.py                          # Start with defaults
    python scripts/run_research.py --provider google         # Use Google Gemma4
    python scripts/run_research.py --provider groq           # Use Groq
    python scripts/run_research.py --max-experiments 100     # Limit experiments
    python scripts/run_research.py --api-key YOUR_KEY        # Pass API key directly

Cross-platform: Linux & Windows
"""

import sys
import os
import argparse
import signal
import time

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="Vietlott Auto-Research Engine — Discover deterministic formulas"
    )
    parser.add_argument(
        "--provider", "-p",
        default="google",
        choices=["google", "groq", "deepseek", "openai", "anthropic"],
        help="LLM provider (default: google)"
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model name override (default: provider-specific)"
    )
    parser.add_argument(
        "--api-key", "-k",
        default=None,
        help="API key (or set via env var, e.g., GOOGLE_API_KEY)"
    )
    parser.add_argument(
        "--max-experiments", "-n",
        type=int,
        default=None,
        help="Maximum number of experiments to run (default: unlimited)"
    )
    parser.add_argument(
        "--window-size", "-w",
        type=int,
        default=10,
        help="Sliding window size for feature sequences (default: 10)"
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.join(PROJECT_ROOT, "data"),
        help="Directory with processed features (default: data/)"
    )

    args = parser.parse_args()

    # Lazy imports after path setup
    from core.analyzer import Analyzer
    from core.dataset import Dataset
    from core.brain import BrainManager
    from autoresearch.llm_client import LLMClient
    from autoresearch.engine import ResearchEngine

    # Step 1: Ensure features are extracted
    features_path = os.path.join(args.data_dir, "features.jsonl")
    if not os.path.exists(features_path):
        print("⚙️  Features not found. Running analyzer first...")
        analyzer = Analyzer()
        raw_path = os.path.join(PROJECT_ROOT, "dataset_raw.jsonl")
        analyzer.process_dataset(raw_path, args.data_dir)
        print("✅ Features extracted.\n")

    # Step 2: Load dataset
    print("=" * 60)
    print("VIETLOTT AUTO-RESEARCH ENGINE")
    print("=" * 60)

    dataset = Dataset(features_path, window_size=args.window_size)
    print(f"Dataset loaded: {len(dataset.get_train())} train / {len(dataset.get_test())} test draws")

    # Step 3: Initialize components
    brain_manager = BrainManager(os.path.join(PROJECT_ROOT, "brains"))

    llm_client = LLMClient(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        config_path=os.path.join(PROJECT_ROOT, "config.json")
    )
    print(f"LLM Provider: {llm_client.get_config()['provider']} / {llm_client.get_config()['model']}")

    # Step 4: Setup research engine
    engine = ResearchEngine(
        dataset=dataset,
        brain_manager=brain_manager,
        llm_client=llm_client,
    )

    # Graceful shutdown on Ctrl+C
    def signal_handler(sig, frame):
        print("\n\n⏹️  Stopping research loop gracefully...")
        engine.stop()

    signal.signal(signal.SIGINT, signal_handler)

    # Step 5: Run
    def on_experiment(result):
        status = "✅ IMPROVED" if result.get('improved') else "❌ discarded"
        print(f"\n  Experiment #{result.get('experiment_id', '?')}: {status}")
        print(f"    Score: train={result.get('train_score', '?'):.4f}, test={result.get('test_score', '?'):.4f}")
        if result.get('description'):
            print(f"    Description: {result['description'][:80]}")
        best = brain_manager.get_leaderboard()
        if best:
            print(f"    Best test score so far: {best[0].test_entropy_score:.4f}")

    print(f"\n🚀 Starting research loop (max experiments: {args.max_experiments or '∞'})")
    print("   Press Ctrl+C to stop gracefully.\n")

    engine.run(max_experiments=args.max_experiments, callback=on_experiment)

    print("\n" + "=" * 60)
    print("RESEARCH SESSION COMPLETE")
    print("=" * 60)
    status = engine.get_status()
    print(f"Total experiments: {status.get('experiment_count', 0)}")

    leaderboard = brain_manager.get_leaderboard()
    if leaderboard:
        print(f"\nTop {len(leaderboard)} Brains:")
        for i, brain in enumerate(leaderboard, 1):
            print(f"  #{i}: score={brain.test_entropy_score:.4f} — {brain.description[:60]}")
    else:
        print("\nNo brains qualified for the leaderboard.")


if __name__ == "__main__":
    main()
