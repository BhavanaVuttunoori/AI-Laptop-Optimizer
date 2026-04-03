"""
config.py
Centralized configuration. All thresholds, paths, and constants live here.
Environment variables loaded from .env — no hardcoded secrets.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "system_metrics.db"
LOG_PATH = DATA_DIR / "app.log"
REPORT_DIR = DATA_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)


@dataclass
class ThresholdConfig:
    cpu_warning: float = 70.0
    cpu_critical: float = 85.0
    memory_warning: float = 70.0
    memory_critical: float = 85.0
    disk_warning: float = 80.0
    disk_critical: float = 95.0
    idle_days: int = 7
    heavy_app_cpu_floor: float = 1.0  # below this = idle background process


@dataclass
class AIConfig:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 1024
    temperature: float = 0.3
    # How many log lines to include in AI context
    context_window_rows: int = 20


@dataclass
class MonitorConfig:
    poll_interval_seconds: int = 5
    history_limit_rows: int = 5000  # max rows kept in DB before pruning
    prediction_intervals: int = 7


@dataclass
class AppConfig:
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    app_name: str = "AI Laptop Optimizer"
    version: str = "5.0.0"
    # Heavy apps that are checked for idle background usage
    heavy_app_names: tuple = (
        "chrome.exe", "msedge.exe", "firefox.exe",
        "code.exe", "teams.exe", "slack.exe",
        "zoom.exe", "skype.exe", "discord.exe",
        "spotify.exe", "steam.exe",
    )


# Singleton config instance used across all modules
config = AppConfig()