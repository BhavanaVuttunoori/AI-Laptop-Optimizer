# AI Laptop Optimizer

A production-grade laptop performance monitor and optimizer built with Python, Streamlit, and the Anthropic Claude API. Combines real-time system monitoring, ML-based anomaly detection, predictive forecasting, and AI-driven optimization recommendations in a single dashboard.

---

## Features

**Real-time monitoring**
- CPU, memory, and disk usage with configurable alert thresholds
- Top processes by CPU consumption
- Heavy background app detection (idle resource hogs)
- Idle application scanner (unused executables)

**Machine learning**
- Anomaly detection using IsolationForest (flags unusual resource spikes)
- 7-interval usage forecasting using LinearRegression
- Health score (0-100) computed from weighted metrics

**AI recommendations**
- Structured optimization suggestions via Claude (claude-haiku) — fast and free tier compatible
- Prompt hashing to avoid redundant API calls (cached in SQLite)
- Rule-based fallback when API key is not configured

**URL safety analysis**
- Claude-powered URL risk assessment with structured JSON output
- Heuristic fallback for offline use

**Data persistence**
- SQLite storage (no external database required)
- CSV export for external analysis
- Automatic row pruning to prevent unbounded growth

---

## Tech stack

| Layer | Technology |
|---|---|
| Dashboard | Streamlit 1.35+ |
| System data | psutil |
| Visualization | Plotly |
| ML | scikit-learn (IsolationForest, LinearRegression) |
| AI | Anthropic Python SDK (Claude Haiku) |
| Storage | SQLite via Python stdlib sqlite3 |
| Config | python-dotenv |

---

## Installation

**1. Clone the repository**
```bash
git clone https://github.com/BhavanaVuttunoori/AI-Laptop-Optimizer.git
cd AI-Laptop-Optimizer
```

**2. Create a virtual environment**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**
```bash
copy .env.example .env
# Edit .env and add your Anthropic API key (free at console.anthropic.com)
```

**5. Run the app**
```bash
streamlit run app.py
```

---

## Project structure

```
ai_laptop_optimizer/
    app.py               # Streamlit dashboard — UI only
    config.py            # All configuration and thresholds
    database.py          # SQLite persistence layer
    monitor.py           # System data collection (psutil)
    anomaly_detector.py  # ML analysis and forecasting
    ai_advisor.py        # Anthropic Claude integration
    charts.py            # Plotly chart builders
    requirements.txt
    .env.example
    data/                # Created automatically on first run
        system_metrics.db
        app.log
        reports/
```

---

## Configuration

All thresholds and settings are in `config.py`. No code changes are needed for common adjustments:

```python
ThresholdConfig(
    cpu_warning=70.0,       # alert threshold
    cpu_critical=85.0,      # critical threshold
    memory_warning=70.0,
    memory_critical=85.0,
    disk_warning=80.0,
    disk_critical=95.0,
    idle_days=7,            # days before an app is considered idle
)
```

---

## Anthropic API key

The app works without an API key (rule-based fallback). For AI-powered recommendations:

1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Generate a free API key
3. Add it to your `.env` file as `ANTHROPIC_API_KEY`

The app uses `claude-haiku-4-5` — the fastest and most cost-efficient Claude model.

---

## Supported platforms

- Windows 10 / 11 (primary — idle app scanner uses Windows program directories)
- macOS and Linux supported for all features except idle app scanning

---

## License

Open-source. Free to use and modify.

---

**Created by Bhavana Vuttunoori**