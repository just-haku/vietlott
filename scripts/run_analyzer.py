#!/usr/bin/env python3
"""
run_analyzer.py — Parse dataset_raw.jsonl and extract all mathematical features.

Usage:
    python scripts/run_analyzer.py                   # Process full dataset
    python scripts/run_analyzer.py --verify-example   # Verify SOUL.md example (draw #00014)
    python scripts/run_analyzer.py --stats            # Show feature statistics

Cross-platform: Linux & Windows
"""

import sys
import os
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.analyzer import Analyzer


def main():
    parser = argparse.ArgumentParser(
        description="Vietlott Feature Extractor — Extract deterministic features from lottery data"
    )
    parser.add_argument(
        "--input", "-i",
        default=os.path.join(PROJECT_ROOT, "dataset_raw.jsonl"),
        help="Path to raw dataset JSONL file (default: dataset_raw.jsonl)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=os.path.join(PROJECT_ROOT, "data"),
        help="Output directory for processed features (default: data/)"
    )
    parser.add_argument(
        "--verify-example",
        action="store_true",
        help="Verify feature extraction against SOUL.md example (draw #00014)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show summary statistics for extracted features"
    )

    args = parser.parse_args()
    analyzer = Analyzer()

    # Verification mode
    if args.verify_example:
        print("=" * 60)
        print("VERIFICATION: SOUL.md Example (Draw #00014)")
        print("=" * 60)
        try:
            analyzer.verify_example()
            print("\n✅ All assertions passed! Feature extraction is correct.")
        except AssertionError as e:
            print(f"\n❌ Verification FAILED: {e}")
            sys.exit(1)
        return

    # Process full dataset
    print("=" * 60)
    print("VIETLOTT FEATURE EXTRACTOR")
    print("=" * 60)
    print(f"Input:  {args.input}")
    print(f"Output: {args.output_dir}")
    print()

    if not os.path.exists(args.input):
        print(f"❌ Input file not found: {args.input}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    results = analyzer.process_dataset(args.input, args.output_dir)

    # Handle both return types: list of features or dict with metadata
    if isinstance(results, list):
        features = results
        total = len(features)
        skipped = 0
    else:
        features = results.get('features', [])
        total = results.get('total', len(features))
        skipped = results.get('skipped', 0)

    print(f"\n✅ Processed {total} draws")
    print(f"   Saved features to: {args.output_dir}/features.jsonl")
    print(f"   Saved features to: {args.output_dir}/features.csv")
    if skipped:
        print(f"   ⚠️  Skipped {skipped} invalid records")

    # Stats mode
    if args.stats:
        print("\n" + "=" * 60)
        print("FEATURE STATISTICS")
        print("=" * 60)
        _print_stats(features)


def _print_stats(features):
    """Print summary statistics for extracted features."""
    if not features:
        print("No features to analyze.")
        return

    feature_keys = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
    print(f"\n{'Feature':<12} {'Min':>8} {'Max':>8} {'Mean':>10} {'Median':>8}")
    print("-" * 50)

    for key in feature_keys:
        values = [f[key] for f in features if key in f]
        if values:
            values_sorted = sorted(values)
            n = len(values)
            mean_val = sum(values) / n
            median_val = values_sorted[n // 2] if n % 2 else (values_sorted[n // 2 - 1] + values_sorted[n // 2]) / 2
            print(f"{key:<12} {min(values):>8.1f} {max(values):>8.1f} {mean_val:>10.2f} {median_val:>8.1f}")


if __name__ == "__main__":
    main()
