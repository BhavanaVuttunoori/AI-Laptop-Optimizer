from typing import List, Optional
import pandas as pd
import plotly.graph_objects as go

METRIC_COLORS = {"cpu": "#5B6FE8", "memory": "#E86B5B", "disk": "#5BB8E8"}
PALETTE = {"bg": "rgba(0,0,0,0)", "grid": "rgba(150,150,150,0.12)",
           "text": "#888888", "border": "rgba(150,150,150,0.2)"}


def _base_layout(title: str = "", height: int = 320) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=14, color=PALETTE["text"]), x=0.0, xanchor="left"),
        paper_bgcolor=PALETTE["bg"], plot_bgcolor=PALETTE["bg"],
        margin=dict(l=0, r=0, t=36 if title else 8, b=0),
        height=height,
        legend=dict(orientation="h", y=-0.18, font=dict(size=11, color=PALETTE["text"])),
        xaxis=dict(showgrid=False, zeroline=False,
                   tickfont=dict(size=10, color=PALETTE["text"]),
                   showline=True, linecolor=PALETTE["border"]),
        yaxis=dict(showgrid=True, gridcolor=PALETTE["grid"], zeroline=False,
                   tickfont=dict(size=10, color=PALETTE["text"]),
                   range=[0, 105], showline=False),
        hovermode="x unified",
    )


def metric_timeseries(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for metric, color in METRIC_COLORS.items():
        if metric not in df.columns:
            continue
        if "source" in df.columns:
            hist = df[df["source"] == "historical"]
            fore = df[df["source"] == "forecast"]
        else:
            hist, fore = df, pd.DataFrame()
        fig.add_trace(go.Scatter(
            x=hist["timestamp"], y=hist[metric],
            name=metric.capitalize(), mode="lines",
            line=dict(color=color, width=1.8),
            hovertemplate="%{y:.1f}%"))
        if not fore.empty and metric in fore.columns:
            fig.add_trace(go.Scatter(
                x=fore["timestamp"], y=fore[metric],
                name=metric.capitalize() + " forecast", mode="lines",
                line=dict(color=color, width=1.5, dash="dot"), opacity=0.6,
                hovertemplate="%{y:.1f}% (forecast)"))
    fig.update_layout(**_base_layout("Usage over time"))
    return fig


def health_gauge(score: int) -> go.Figure:
    color = "#5BB88A" if score >= 70 else "#E8B85B" if score >= 40 else "#E86B5B"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(font=dict(size=36, color=color)),
        gauge=dict(
            axis=dict(range=[0, 100], tickfont=dict(size=10, color=PALETTE["text"])),
            bar=dict(color=color, thickness=0.6),
            bgcolor=PALETTE["bg"], borderwidth=0,
            steps=[
                dict(range=[0,  40], color="rgba(232,107,91,0.12)"),
                dict(range=[40, 70], color="rgba(232,184,91,0.12)"),
                dict(range=[70,100], color="rgba(91,184,138,0.12)"),
            ],
        ),
    ))
    fig.update_layout(paper_bgcolor=PALETTE["bg"],
                      margin=dict(l=16, r=16, t=16, b=0), height=200)
    return fig


def top_processes_bar(processes) -> go.Figure:
    if not processes:
        return go.Figure()
    names    = [p.name[:24] for p in processes]
    cpu_vals = [p.cpu_percent for p in processes]
    mem_vals = [p.memory_mb  for p in processes]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=cpu_vals, orientation="h",
        name="CPU %", marker_color=METRIC_COLORS["cpu"], opacity=0.85))
    fig.add_trace(go.Bar(y=names, x=mem_vals, orientation="h",
        name="Memory MB", marker_color=METRIC_COLORS["memory"], opacity=0.85))
    layout = _base_layout("Top processes", height=340)
    layout["barmode"] = "group"
    layout["yaxis"]["autorange"] = "reversed"
    layout["yaxis"]["range"] = None
    fig.update_layout(**layout)
    return fig


def anomaly_scatter(df_anomalies: pd.DataFrame) -> Optional[go.Figure]:
    if df_anomalies.empty:
        return None
    color_map = {"cpu": METRIC_COLORS["cpu"], "memory": METRIC_COLORS["memory"],
                 "disk": METRIC_COLORS["disk"]}
    fig = go.Figure()
    for metric in df_anomalies["metric"].unique():
        sub = df_anomalies[df_anomalies["metric"] == metric]
        fig.add_trace(go.Scatter(
            x=sub["timestamp"], y=sub["value"], mode="markers",
            name=metric.capitalize(),
            marker=dict(size=8, color=color_map.get(metric, "#888"), symbol="x"),
            hovertemplate="Value: %{y:.1f}%<br>Score: %{customdata:.3f}",
            customdata=sub["score"].values,
        ))
    fig.update_layout(**_base_layout("Detected anomalies"))
    return fig


def metric_distribution(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for metric, color in METRIC_COLORS.items():
        if metric not in df.columns:
            continue
        fig.add_trace(go.Box(y=df[metric], name=metric.capitalize(),
            marker_color=color, line_color=color, opacity=0.8, boxmean=True))
    layout = _base_layout("Metric distribution")
    layout["yaxis"]["title"] = dict(text="Usage %",
                                    font=dict(size=10, color=PALETTE["text"]))
    fig.update_layout(**layout)
    return fig