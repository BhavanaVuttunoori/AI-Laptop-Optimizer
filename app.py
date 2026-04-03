"""
app.py
Main Streamlit dashboard for AI Laptop Optimizer.
Clean tabbed layout, cached data collection, no business logic here.
"""

import logging
import time
from typing import Optional

import pandas as pd
import streamlit as st

from config import config
from database import initialize_db, fetch_metrics, fetch_recent_anomalies
from monitor import (
    collect_snapshot,
    evaluate_alerts,
    get_top_processes,
    get_heavy_background_processes,
    scan_idle_apps,
    clean_temp_files,
)
from anomaly_detector import (
    detect_anomalies,
    forecast_usage,
    compute_health_score,
    build_trend_dataframe,
)
from ai_advisor import get_recommendations, check_url_safety
from charts import (
    metric_timeseries,
    health_gauge,
    top_processes_bar,
    anomaly_scatter,
    metric_distribution,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.FileHandler(str(config.DATA_DIR / "app.log") if hasattr(config, "DATA_DIR") else "app.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Streamlit page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=config.app_name,
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Minimal CSS: tighten default padding and style alert boxes
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
    .metric-card {
        background: var(--background-secondary-color, #f7f7f7);
        border-radius: 10px;
        padding: 1rem 1.2rem;
        border: 1px solid rgba(150,150,150,0.15);
    }
    .alert-critical {
        background: rgba(232, 107, 91, 0.12);
        border-left: 3px solid #E86B5B;
        border-radius: 0 6px 6px 0;
        padding: 0.5rem 0.9rem;
        margin-bottom: 0.4rem;
        font-size: 0.9rem;
    }
    .alert-warning {
        background: rgba(232, 184, 91, 0.12);
        border-left: 3px solid #E8B85B;
        border-radius: 0 6px 6px 0;
        padding: 0.5rem 0.9rem;
        margin-bottom: 0.4rem;
        font-size: 0.9rem;
    }
    .rec-high   { border-left: 3px solid #E86B5B; padding: 0.5rem 0.8rem; border-radius: 0 6px 6px 0; margin-bottom: 0.5rem; }
    .rec-medium { border-left: 3px solid #E8B85B; padding: 0.5rem 0.8rem; border-radius: 0 6px 6px 0; margin-bottom: 0.5rem; }
    .rec-low    { border-left: 3px solid #5BB88A; padding: 0.5rem 0.8rem; border-radius: 0 6px 6px 0; margin-bottom: 0.5rem; }
    .verdict-safe       { color: #5BB88A; font-weight: 600; }
    .verdict-suspicious { color: #E8B85B; font-weight: 600; }
    .verdict-dangerous  { color: #E86B5B; font-weight: 600; }
    .verdict-unknown    { color: #888888; font-weight: 600; }
    h2 { font-size: 1.1rem !important; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"]      { padding: 0.4rem 1rem; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DB init (idempotent — safe to call on every run)
# ---------------------------------------------------------------------------
initialize_db()


# ---------------------------------------------------------------------------
# Cached data loaders
# Use st.cache_data with short TTL so dashboard feels live but not spammy.
# ---------------------------------------------------------------------------
@st.cache_data(ttl=config.monitor.poll_interval_seconds, show_spinner=False)
def _cached_snapshot():
    return collect_snapshot()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_processes():
    return get_top_processes(10)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_heavy():
    return get_heavy_background_processes()


@st.cache_data(ttl=120, show_spinner=False)
def _cached_idle_apps():
    return scan_idle_apps()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_metrics_df():
    return fetch_metrics()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_anomaly_history():
    return fetch_recent_anomalies(50)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_title, col_version = st.columns([8, 2])
with col_title:
    st.markdown(f"### {config.app_name}")
with col_version:
    st.caption(f"v{config.version}")

# ---------------------------------------------------------------------------
# Collect live data
# ---------------------------------------------------------------------------
with st.spinner("Collecting system data..."):
    snapshot = _cached_snapshot()
    alerts   = evaluate_alerts(snapshot)

# Show active alerts inline below the header
if alerts:
    for alert in alerts:
        cls = "alert-critical" if alert.level == "critical" else "alert-warning"
        st.markdown(
            f'<div class="{cls}">{alert.level.upper()}: {alert.message}</div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_processes, tab_ai, tab_history, tab_url = st.tabs([
    "Overview", "Processes", "AI Advisor", "History & Forecast", "URL Safety"
])


# ===========================================================================
# TAB: Overview
# ===========================================================================
with tab_overview:
    # Metric cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("CPU", f"{snapshot.cpu:.1f}%",
                  delta=None, help="Current CPU utilization across all cores")
    with col2:
        st.metric("Memory", f"{snapshot.memory:.1f}%",
                  delta=f"{snapshot.memory_available_gb} GB free")
    with col3:
        st.metric("Disk", f"{snapshot.disk:.1f}%",
                  delta=f"{snapshot.disk_free_gb} GB free")
    with col4:
        idle_apps = _cached_idle_apps()
        heavy_apps = _cached_heavy()
        df_hist = _cached_metrics_df()
        anomalies = detect_anomalies(df_hist) if len(df_hist) >= 30 else []
        anomaly_count = sum(1 for a in anomalies if a.is_anomaly)
        health = compute_health_score(snapshot, len(idle_apps), len(heavy_apps), anomaly_count)
        st.metric("Health Score", f"{health}/100")

    st.divider()

    col_gauge, col_info = st.columns([2, 3])
    with col_gauge:
        st.plotly_chart(health_gauge(health), use_container_width=True, config={"displayModeBar": False})

    with col_info:
        st.markdown("**Anomaly detection**")
        if not anomalies:
            st.caption("Not enough data yet. Collecting baseline...")
        else:
            for a in anomalies:
                flag = "ANOMALY" if a.is_anomaly else "normal"
                st.caption(
                    f"{a.metric.upper()}: {a.current_value:.1f}%  |  "
                    f"mean {a.mean_value:.1f}%  |  {flag}"
                )

        st.markdown("**Cleanup**")
        if st.button("Clean temporary files", type="secondary"):
            success, msg = clean_temp_files()
            if success:
                st.success(msg)
            else:
                st.error(msg)

    # Quick stats
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Idle apps detected:** {len(idle_apps)}")
        if idle_apps:
            with st.expander("Show idle apps"):
                rows = [{"Name": a.name, "Last used": a.last_accessed.strftime("%Y-%m-%d"), "Size (MB)": a.size_mb}
                        for a in idle_apps[:30]]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with c2:
        st.markdown(f"**Heavy background processes:** {len(heavy_apps)}")
        if heavy_apps:
            with st.expander("Show heavy background apps"):
                rows = [{"Name": p.name, "Memory (MB)": p.memory_mb, "Status": p.status}
                        for p in heavy_apps]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ===========================================================================
# TAB: Processes
# ===========================================================================
with tab_processes:
    procs = _cached_processes()
    if procs:
        st.plotly_chart(top_processes_bar(procs), use_container_width=True, config={"displayModeBar": False})
        st.divider()
        rows = [
            {
                "PID": p.pid,
                "Name": p.name,
                "CPU %": f"{p.cpu_percent:.1f}",
                "Memory MB": f"{p.memory_mb:.0f}",
                "Status": p.status,
            }
            for p in procs
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No process data available.")

    if st.button("Refresh process list"):
        st.cache_data.clear()
        st.rerun()


# ===========================================================================
# TAB: AI Advisor
# ===========================================================================
with tab_ai:
    st.markdown("AI-powered optimization recommendations using Claude.")

    idle_names  = [a.name for a in (_cached_idle_apps())]
    heavy_names = [p.name for p in (_cached_heavy())]
    anomaly_labels = [f"{a.metric} anomaly" for a in anomalies if a.is_anomaly]

    if not config.ai.anthropic_api_key:
        st.warning(
            "ANTHROPIC_API_KEY not set in your .env file. "
            "Using rule-based recommendations. "
            "Add your free API key to unlock AI-powered analysis."
        )

    with st.spinner("Generating recommendations..."):
        result = get_recommendations(
            snapshot.cpu, snapshot.memory, snapshot.disk,
            idle_names, heavy_names, anomaly_labels,
        )

    if result.error:
        st.error(result.error)
    else:
        if result.used_cache:
            st.caption("Showing cached recommendations.")

        st.markdown(f"**Summary:** {result.summary}")
        st.divider()

        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_recs = sorted(result.recommendations, key=lambda r: priority_order.get(r.priority, 9))

        for rec in sorted_recs:
            cls = f"rec-{rec.priority}"
            st.markdown(
                f'<div class="{cls}">'
                f'<strong>[{rec.priority.upper()}] {rec.title}</strong><br>'
                f'{rec.action}<br>'
                f'<small>Expected impact: {rec.estimated_impact}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )

    if st.button("Refresh recommendations", type="secondary"):
        st.cache_data.clear()
        st.rerun()


# ===========================================================================
# TAB: History & Forecast
# ===========================================================================
with tab_history:
    df = _cached_metrics_df()

    if df.empty:
        st.info("No historical data yet. The dashboard collects a snapshot each time it loads.")
    else:
        # Forecast
        forecasts = forecast_usage(df)
        trend_df = build_trend_dataframe(df, forecasts)

        st.plotly_chart(
            metric_timeseries(trend_df),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        if forecasts:
            st.markdown("**7-interval forecast**")
            cols = st.columns(3)
            for i, fc in enumerate(forecasts):
                with cols[i]:
                    arrow = "rising" if fc.trend == "rising" else "falling" if fc.trend == "falling" else "stable"
                    st.metric(
                        fc.metric.capitalize(),
                        f"{fc.predicted_values[-1]:.1f}%",
                        delta=fc.trend,
                    )
                    st.caption(f"R2: {fc.confidence_r2:.3f}")

        st.divider()
        st.plotly_chart(metric_distribution(df), use_container_width=True, config={"displayModeBar": False})

        # Anomaly history
        df_anomalies = _cached_anomaly_history()
        fig_anomalies = anomaly_scatter(df_anomalies)
        if fig_anomalies:
            st.divider()
            st.plotly_chart(fig_anomalies, use_container_width=True, config={"displayModeBar": False})

        # Raw data export
        with st.expander("Export raw data"):
            st.dataframe(df.tail(200), use_container_width=True)
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", data=csv, file_name="system_metrics.csv", mime="text/csv")


# ===========================================================================
# TAB: URL Safety
# ===========================================================================
with tab_url:
    st.markdown("Enter a URL to evaluate before visiting it.")

    url_input = st.text_input("URL", placeholder="https://example.com")

    if url_input:
        with st.spinner("Analyzing URL..."):
            result = check_url_safety(url_input)

        verdict_class = f"verdict-{result.verdict}"
        st.markdown(
            f'Verdict: <span class="{verdict_class}">{result.verdict.upper()}</span> '
            f'(confidence: {result.confidence})',
            unsafe_allow_html=True,
        )
        st.markdown(f"**Recommendation:** {result.recommendation}")
        if result.reasons:
            st.markdown("**Reasons:**")
            for r in result.reasons:
                st.markdown(f"- {r}")

    st.divider()
    st.caption(
        "Note: AI URL analysis provides an opinion based on patterns, not a definitive security scan. "
        "For production use, integrate a dedicated threat intelligence API such as VirusTotal."
    )

# ---------------------------------------------------------------------------
# Auto-refresh every N seconds
# ---------------------------------------------------------------------------
refresh = st.sidebar.slider("Auto-refresh (seconds)", 5, 60, 10)
st.sidebar.caption(f"Last snapshot: {snapshot.timestamp.strftime('%H:%M:%S')}")
time.sleep(0)  # yield to allow Streamlit to render
st.sidebar.button("Refresh now", on_click=st.cache_data.clear)