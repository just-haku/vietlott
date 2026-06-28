# 🎱 SOUL — Vietlott Deterministic Universe Pipeline

> *"God does not play dice with the universe."* — Albert Einstein

A cross-platform (Linux & Windows) AI-powered pipeline that investigates whether the universe is truly random or deterministic, using Vietlott lottery data as a high-entropy experimental dataset.

## 🧠 Concept

If the universe is deterministic, then even lottery numbers—the pinnacle of human-designated randomness—should exhibit predictability when analyzed through the right mathematical lens. This project extracts **19 deterministic features** from historical lottery draws and uses an **AI auto-research engine** to discover simple mathematical formulas that predict future draws.

### The Axiom of Simplicity
> All complex formulas and behaviors in the universe can be recreated by a finite set of simple mathematical operations.

## 📊 Features Extracted

**Primary Features (A-L):**
| Feature | Name | Description |
|---------|------|-------------|
| A | Main Sum | Sum of 6 main numbers |
| B | Main Sum Root | Digital root of A |
| C | Total Sum | Sum of all 7 numbers |
| D | Total Sum Root | Digital root of C |
| E | Main Tens Sum | Sum of tens digits (main) |
| F | Main Tens Root | Digital root of E |
| G | Main Units Sum | Sum of units digits (main) |
| H | Main Units Root | Digital root of G |
| I | Total Tens Sum | Sum of tens digits (all) |
| J | Total Tens Root | Digital root of I |
| K | Total Units Sum | Sum of units digits (all) |
| L | Total Units Root | Digital root of K |

**Modular Mappings (M1-M7):** For each of the 7 numbers:
- **Ends-with mapping**: Last digit → percentage bucket (1→10%, ..., 9→90%, 0→100%)
- **Modulo-5 mapping**: x%5 → percentage bucket (1→20%, 2→40%, ..., 0→100%)

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Extract features from lottery data
python scripts/run_analyzer.py

# 3. Verify against SOUL.md example
python scripts/run_analyzer.py --verify-example

# 4. Start the web dashboard
python scripts/run_frontend.py

# 5. Start auto-research (headless)
python scripts/run_research.py --provider google --api-key YOUR_KEY
```

## 🏗️ Architecture

```
vietlott/
├── SOUL.md                    # Philosophy & mathematical specifications
├── dataset_raw.jsonl          # Raw Vietlott lottery draws (1288 records)
├── core/                      # Data pipeline
│   ├── analyzer.py            # Feature extraction (A-L, M1-M7)
│   ├── dataset.py             # Train/test split & sequence access
│   └── brain.py               # Top-5 brain persistence
├── autoresearch/              # AI research engine
│   ├── engine.py              # Auto-research loop
│   ├── llm_client.py          # Multi-provider LLM client (Google, Groq, etc.)
│   ├── formula.py             # Formula representation & evaluation
│   └── program.md             # LLM agent instructions
├── frontend/                  # Web dashboard
│   ├── server.py              # Flask backend + REST API
│   └── static/                # Modular lazy-loaded JS + CSS
├── brains/                    # Persisted top-5 brains
├── data/                      # Processed features
└── scripts/                   # CLI entry points
```

## 🔬 Auto-Research Engine

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch), the engine runs an autonomous loop:

1. **Propose** — LLM suggests mathematical formula set
2. **Evaluate** — Formulas tested against training data
3. **Score** — Prediction entropy computed on held-out test set
4. **Keep or Discard** — Better brains saved, worse ones discarded
5. **Repeat** — With full experiment history as context

### Supported LLM Providers
- **Google** (Gemma4 27B IT — default)
- **Groq**
- **DeepSeek**
- **OpenAI**
- **Anthropic**

### Brain Management
The top 5 brains (formula sets with lowest prediction entropy on test data) are persisted to `brains/`.

## 🖥️ Dashboard

A premium dark-mode web dashboard with:
- **Leaderboard** — Top-5 brains with expandable formula details
- **Experiment Timeline** — Score history chart
- **AI Response Panel** — Live LLM conversation feed
- **Configuration** — Provider/model/API key settings
- **Data Explorer** — Interactive feature visualizations
- **LLM Endpoint** — Direct AI interaction for testing

## 📈 Dataset

- **Source**: Vietlott Power 6/55
- **Range**: 2017-08-01 to 2025-12-30
- **Records**: 1,288 draws
- **Split**: 80% training (Study/Homework) / 20% test (Exam)
- **Numbers**: 6 main (1-55) + 1 special (1-55)

## 📄 License

This project is for educational and research purposes only.
