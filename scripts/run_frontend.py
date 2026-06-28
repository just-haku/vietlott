#!/usr/bin/env python3
"""
run_frontend.py — Start the web dashboard for monitoring auto-research.

Usage:
    python scripts/run_frontend.py                  # Start on port 5000
    python scripts/run_frontend.py --port 8080       # Custom port
    python scripts/run_frontend.py --host 0.0.0.0    # Allow external access
    python scripts/run_frontend.py --debug            # Debug mode

Cross-platform: Linux & Windows
"""

import sys
import os
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="Vietlott Dashboard — Web-based monitoring and control"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1, use 0.0.0.0 for external access)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode (auto-reload, verbose errors)"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically"
    )

    args = parser.parse_args()

    # Ensure features exist
    from core.analyzer import Analyzer
    features_path = os.path.join(PROJECT_ROOT, "data", "features.jsonl")
    if not os.path.exists(features_path):
        print("⚙️  Features not found. Running analyzer first...")
        analyzer = Analyzer()
        raw_path = os.path.join(PROJECT_ROOT, "dataset_raw.jsonl")
        analyzer.process_dataset(raw_path, os.path.join(PROJECT_ROOT, "data"))
        print("✅ Features extracted.\n")

    print("=" * 60)
    print("VIETLOTT DASHBOARD")
    print("=" * 60)
    print(f"🌐 Starting server at http://{args.host}:{args.port}")
    print(f"   Debug mode: {'ON' if args.debug else 'OFF'}")
    print(f"   Press Ctrl+C to stop.\n")

    # Import and run the Flask app
    from frontend.server import create_app

    app = create_app(PROJECT_ROOT)
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
