"""
ai_advisor.py
Anthropic Claude integration for system optimization recommendations.
Uses claude-haiku (free tier friendly, fast) with:
  - Prompt hashing to avoid duplicate API calls
  - Structured JSON output for machine-readable recommendations
  - Graceful degradation to rule-based fallback
  - URL safety analysis
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import List, Optional

import anthropic

from config import config
from database import cache_ai_recommendation, fetch_cached_recommendation

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    category: str       # "cpu" | "memory" | "disk" | "apps" | "general"
    priority: str       # "high" | "medium" | "low"
    title: str
    action: str
    estimated_impact: str


@dataclass
class AIAdvisorResult:
    recommendations: List[Recommendation]
    summary: str
    used_cache: bool
    error: Optional[str] = None


@dataclass
class URLSafetyResult:
    url: str
    verdict: str          # "safe" | "suspicious" | "dangerous" | "unknown"
    confidence: str       # "high" | "medium" | "low"
    reasons: List[str]
    recommendation: str


def _build_system_prompt() -> str:
    return (
        "You are an expert system administrator and performance optimization specialist. "
        "Analyze laptop performance data and respond ONLY with valid JSON — no markdown, no prose. "
        "Your JSON must match exactly the schema provided in the user message."
    )


def _build_user_prompt(
    cpu: float,
    memory: float,
    disk: float,
    idle_app_names: List[str],
    heavy_app_names: List[str],
    anomalies: List[str],
) -> str:
    return f"""
Laptop metrics:
- CPU: {cpu:.1f}%
- Memory: {memory:.1f}%
- Disk: {disk:.1f}%
- Idle apps (unused >7 days): {idle_app_names[:10]}
- Heavy background apps (low CPU, high memory): {heavy_app_names}
- Detected anomalies: {anomalies}

Respond with ONLY this JSON structure (no other text):
{{
  "summary": "<2-sentence overall assessment>",
  "recommendations": [
    {{
      "category": "<cpu|memory|disk|apps|general>",
      "priority": "<high|medium|low>",
      "title": "<short action title>",
      "action": "<specific actionable step>",
      "estimated_impact": "<expected improvement>"
    }}
  ]
}}

Include 3 to 6 recommendations. Order by priority (high first).
"""


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _parse_recommendations(raw_json: str) -> AIAdvisorResult:
    try:
        data = json.loads(raw_json)
        recs = [
            Recommendation(
                category=r.get("category", "general"),
                priority=r.get("priority", "medium"),
                title=r.get("title", ""),
                action=r.get("action", ""),
                estimated_impact=r.get("estimated_impact", ""),
            )
            for r in data.get("recommendations", [])
        ]
        return AIAdvisorResult(
            recommendations=recs,
            summary=data.get("summary", "Analysis complete."),
            used_cache=False,
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Failed to parse AI JSON response: %s", exc)
        return _fallback_recommendations(0, 0, 0)


def get_recommendations(
    cpu: float,
    memory: float,
    disk: float,
    idle_app_names: List[str],
    heavy_app_names: List[str],
    anomalies: List[str],
) -> AIAdvisorResult:
    """
    Main entry point for AI recommendations.
    Checks cache first, falls back to rule-based if API unavailable.
    """
    if not config.ai.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using rule-based fallback.")
        return _fallback_recommendations(cpu, memory, disk)

    prompt = _build_user_prompt(cpu, memory, disk, idle_app_names, heavy_app_names, anomalies)
    prompt_hash = _hash_prompt(prompt)

    # Check cache
    cached = fetch_cached_recommendation(prompt_hash)
    if cached:
        result = _parse_recommendations(cached)
        result = AIAdvisorResult(
            recommendations=result.recommendations,
            summary=result.summary,
            used_cache=True,
        )
        return result

    try:
        client = anthropic.Anthropic(api_key=config.ai.anthropic_api_key)
        message = client.messages.create(
            model=config.ai.model,
            max_tokens=config.ai.max_tokens,
            system=_build_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        cache_ai_recommendation(prompt_hash, raw)
        return _parse_recommendations(raw)

    except anthropic.AuthenticationError:
        logger.error("Invalid Anthropic API key.")
        return AIAdvisorResult(
            recommendations=[],
            summary="",
            used_cache=False,
            error="Invalid API key. Check ANTHROPIC_API_KEY in your .env file.",
        )
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit — using fallback.")
        return _fallback_recommendations(cpu, memory, disk)
    except Exception as exc:
        logger.error("Unexpected AI error: %s", exc)
        return _fallback_recommendations(cpu, memory, disk)


def _fallback_recommendations(cpu: float, memory: float, disk: float) -> AIAdvisorResult:
    """Rule-based recommendations when API is unavailable."""
    t = config.thresholds
    recs: List[Recommendation] = []

    if cpu >= t.cpu_critical:
        recs.append(Recommendation("cpu", "high", "Reduce CPU load",
            "Open Task Manager and terminate processes consuming >20% CPU that are not critical.",
            "May reduce CPU by 20-40%"))
    elif cpu >= t.cpu_warning:
        recs.append(Recommendation("cpu", "medium", "Monitor CPU usage",
            "Check for runaway processes using Task Manager. Consider closing browser tabs.",
            "May reduce CPU by 10-20%"))

    if memory >= t.memory_critical:
        recs.append(Recommendation("memory", "high", "Free memory immediately",
            "Close unused browser windows, restart memory-heavy applications.",
            "May free 1-4 GB RAM"))
    elif memory >= t.memory_warning:
        recs.append(Recommendation("memory", "medium", "Reduce memory pressure",
            "Close idle applications. Check for memory leaks in long-running apps.",
            "May free 500 MB - 2 GB"))

    if disk >= t.disk_critical:
        recs.append(Recommendation("disk", "high", "Free disk space urgently",
            "Run Disk Cleanup, empty Recycle Bin, delete Downloads older than 30 days.",
            "May free 5-20 GB"))
    elif disk >= t.disk_warning:
        recs.append(Recommendation("disk", "medium", "Clean up disk space",
            "Delete temp files, clear browser cache, uninstall unused applications.",
            "May free 2-10 GB"))

    if not recs:
        recs.append(Recommendation("general", "low", "System is healthy",
            "Continue monitoring. Schedule a cleanup in 30 days.",
            "Maintains current performance"))

    return AIAdvisorResult(
        recommendations=recs,
        summary="Rule-based analysis (AI unavailable). Connect an Anthropic API key for detailed insights.",
        used_cache=False,
    )


def check_url_safety(url: str) -> URLSafetyResult:
    """
    Use Claude to evaluate whether a URL appears safe.
    Falls back to a basic structural check if API is unavailable.
    """
    if not config.ai.anthropic_api_key:
        return _basic_url_check(url)

    prompt = f"""
Analyze this URL for safety: {url}

Respond ONLY with this JSON (no other text):
{{
  "verdict": "<safe|suspicious|dangerous|unknown>",
  "confidence": "<high|medium|low>",
  "reasons": ["<reason 1>", "<reason 2>"],
  "recommendation": "<one sentence advice>"
}}
"""
    try:
        client = anthropic.Anthropic(api_key=config.ai.anthropic_api_key)
        message = client.messages.create(
            model=config.ai.model,
            max_tokens=256,
            system="You are a cybersecurity expert. Analyze URLs for safety indicators. Respond only in JSON.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        data = json.loads(raw)
        return URLSafetyResult(
            url=url,
            verdict=data.get("verdict", "unknown"),
            confidence=data.get("confidence", "low"),
            reasons=data.get("reasons", []),
            recommendation=data.get("recommendation", ""),
        )
    except Exception as exc:
        logger.warning("URL safety check failed: %s", exc)
        return _basic_url_check(url)


def _basic_url_check(url: str) -> URLSafetyResult:
    """Structural heuristic URL check — no external calls."""
    from urllib.parse import urlparse
    import re

    suspicious_patterns = [
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",  # raw IP address
        r"(free|win|prize|click|login|secure|verify|update)\w*\.(xyz|tk|ml|ga|cf)",
        r"bit\.ly|tinyurl|goo\.gl",  # URL shorteners
        r"paypal|amazon|google|microsoft|apple.*\.(ru|cn|cc|pw|top)",  # brand impersonation TLDs
    ]

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return URLSafetyResult(url, "suspicious", "high",
                ["Non-standard URL scheme"], "Do not open this URL.")

        domain = parsed.netloc.lower()
        reasons = []
        for pattern in suspicious_patterns:
            if re.search(pattern, domain):
                reasons.append(f"Matches suspicious pattern: {pattern}")

        if not parsed.scheme == "https":
            reasons.append("Uses unencrypted HTTP")

        if reasons:
            return URLSafetyResult(url, "suspicious", "medium", reasons,
                "Proceed with caution. Verify the source before clicking.")

        return URLSafetyResult(url, "safe", "low",
            ["No obvious red flags detected (basic check only)"],
            "Basic check passed. For full analysis, configure an API key.")

    except Exception as exc:
        return URLSafetyResult(url, "unknown", "low",
            [f"Could not parse URL: {exc}"], "Do not open this URL.")