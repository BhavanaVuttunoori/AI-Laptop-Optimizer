"""
monitor.py
System resource monitoring with proper async-safe patterns.
Separates data collection from UI — this module has zero Streamlit imports.
"""

import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import psutil

from config import config
from database import insert_metric

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SystemSnapshot:
    cpu: float
    memory: float
    disk: float
    memory_available_gb: float
    disk_free_gb: float
    timestamp: datetime


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    status: str


@dataclass(frozen=True)
class IdleApp:
    name: str
    path: str
    last_accessed: datetime
    size_mb: float


@dataclass(frozen=True)
class AlertLevel:
    metric: str
    value: float
    level: str   # "warning" | "critical"
    message: str


def collect_snapshot() -> SystemSnapshot:
    """
    Read current CPU, memory, and disk stats.
    Persists to DB and returns a frozen snapshot.
    cpu_percent(interval=1) blocks for 1 second — acceptable for background threads.
    """
    cpu = psutil.cpu_percent(interval=1)
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")

    memory = vm.percent
    disk = du.percent
    memory_available_gb = round(vm.available / (1024 ** 3), 2)
    disk_free_gb = round(du.free / (1024 ** 3), 2)

    try:
        insert_metric(cpu, memory, disk)
    except Exception as exc:
        logger.warning("Failed to persist metric snapshot: %s", exc)

    return SystemSnapshot(
        cpu=cpu,
        memory=memory,
        disk=disk,
        memory_available_gb=memory_available_gb,
        disk_free_gb=disk_free_gb,
        timestamp=datetime.now(),
    )


def evaluate_alerts(snapshot: SystemSnapshot) -> List[AlertLevel]:
    """Return a list of active alerts based on configured thresholds."""
    alerts: List[AlertLevel] = []
    t = config.thresholds

    checks = [
        ("CPU", snapshot.cpu, t.cpu_warning, t.cpu_critical),
        ("Memory", snapshot.memory, t.memory_warning, t.memory_critical),
        ("Disk", snapshot.disk, t.disk_warning, t.disk_critical),
    ]
    for metric, value, warn, crit in checks:
        if value >= crit:
            alerts.append(AlertLevel(metric, value, "critical", f"{metric} is at {value:.1f}%"))
        elif value >= warn:
            alerts.append(AlertLevel(metric, value, "warning", f"{metric} is at {value:.1f}%"))
    return alerts


def get_top_processes(n: int = 10) -> List[ProcessInfo]:
    """Return the top N processes by CPU usage."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
        try:
            info = proc.info
            processes.append(ProcessInfo(
                pid=info["pid"],
                name=info["name"] or "unknown",
                cpu_percent=info["cpu_percent"] or 0.0,
                memory_mb=round((info["memory_info"].rss if info["memory_info"] else 0) / (1024 ** 2), 1),
                status=info["status"] or "unknown",
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)[:n]


def get_heavy_background_processes() -> List[ProcessInfo]:
    """
    Identify processes from the known-heavy list that are running
    but consuming almost no CPU (idle background resource hogs).
    """
    heavy_names = {n.lower() for n in config.heavy_app_names}
    results = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
        try:
            info = proc.info
            name = (info["name"] or "").lower()
            if name in heavy_names and (info["cpu_percent"] or 0) < config.thresholds.heavy_app_cpu_floor:
                results.append(ProcessInfo(
                    pid=info["pid"],
                    name=info["name"],
                    cpu_percent=info["cpu_percent"] or 0.0,
                    memory_mb=round((info["memory_info"].rss if info["memory_info"] else 0) / (1024 ** 2), 1),
                    status=info["status"] or "unknown",
                ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


def scan_idle_apps(days: Optional[int] = None) -> List[IdleApp]:
    """
    Walk Windows program directories and return executables not accessed
    within the idle threshold. Gracefully skips inaccessible paths.
    """
    threshold_days = days or config.thresholds.idle_days
    cutoff = datetime.now() - timedelta(days=threshold_days)
    idle: List[IdleApp] = []

    program_dirs = [
        d for d in [os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)")]
        if d and os.path.isdir(d)
    ]

    for base in program_dirs:
        for root, _, files in os.walk(base):
            for fname in files:
                if not fname.lower().endswith(".exe"):
                    continue
                full_path = os.path.join(root, fname)
                try:
                    atime = datetime.fromtimestamp(os.path.getatime(full_path))
                    if atime < cutoff:
                        size_mb = round(os.path.getsize(full_path) / (1024 ** 2), 2)
                        idle.append(IdleApp(
                            name=fname,
                            path=full_path,
                            last_accessed=atime,
                            size_mb=size_mb,
                        ))
                except (OSError, PermissionError):
                    continue
    return sorted(idle, key=lambda a: a.last_accessed)


def clean_temp_files() -> Tuple[bool, str]:
    """
    Delete the user's TEMP directory contents.
    Returns (success, message).
    """
    temp_dir = os.getenv("TEMP") or os.getenv("TMP")
    if not temp_dir or not os.path.isdir(temp_dir):
        return False, "TEMP directory not found."
    try:
        freed = 0
        for entry in os.scandir(temp_dir):
            try:
                if entry.is_file():
                    freed += entry.stat().st_size
                    os.remove(entry.path)
                elif entry.is_dir():
                    freed += sum(
                        f.stat().st_size for f in Path(entry.path).rglob("*") if f.is_file()
                    ) if False else 0  # skip recursive size for speed
                    shutil.rmtree(entry.path, ignore_errors=True)
            except (PermissionError, OSError):
                continue
        freed_mb = round(freed / (1024 ** 2), 1)
        return True, f"Temp files cleaned. Freed approximately {freed_mb} MB."
    except Exception as exc:
        logger.error("Failed to clean temp files: %s", exc)
        return False, f"Cleanup failed: {exc}"


# Import here to avoid circular import at module load time
from pathlib import Path