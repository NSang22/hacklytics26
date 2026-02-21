import plotly.graph_objects as go
import plotly.express as px
from plotly.io import to_html

EMOTION_COLORS = {
    "frustration": "#ef4444",
    "confusion":   "#f97316",
    "delight":     "#22c55e",
    "surprise":    "#3b82f6",
    "engagement":  "#a855f7",
    "boredom":     "#6b7280",
}

STATE_BAND_COLORS = {
    "tutorial":       "rgba(59,130,246,0.10)",
    "puzzle_room":    "rgba(249,115,22,0.10)",
    "surprise_event": "rgba(168,85,247,0.10)",
    "gauntlet":       "rgba(239,68,68,0.10)",
    "victory":        "rgba(34,197,94,0.10)",
}


def build_chart(rows: list[dict]) -> str:
    if not rows:
        return "<p style='color:#94a3b8;padding:2rem;'>No data returned for this query.</p>"

    cols = {k.lower() for k in rows[0].keys()}
    norm = [{k.lower(): v for k, v in r.items()} for r in rows]

    if "t_second" in cols:
        return _timeline(norm)
    if "time_delta_sec" in cols and cols & {"avg_confusion", "confusion"}:
        return _scatter(norm)
    if "health_score" in cols:
        return _health_bar(norm)
    if "dfa_state" in cols:
        return _state_heatmap(norm)
    return _table(norm)


def _state_heatmap(rows: list[dict]) -> str:
    states = [r.get("dfa_state", "") for r in rows]
    cols   = set(rows[0].keys())
    fig    = go.Figure()

    if "avg_frustration" in cols:
        frustration = [r.get("avg_frustration") or 0 for r in rows]
        heart_rate  = [r.get("avg_heart_rate")  or 0 for r in rows]

        fig.add_trace(go.Bar(
            name="Avg Frustration",
            x=states,
            y=frustration,
            marker_color=[
                "#ef4444" if v > 0.6 else "#f97316" if v > 0.3 else "#22c55e"
                for v in frustration
            ],
            text=[f"{v:.2f}" for v in frustration],
            textposition="outside",
        ))
        if any(h > 0 for h in heart_rate):
            fig.add_trace(go.Scatter(
                name="Avg Heart Rate (bpm)",
                x=states,
                y=heart_rate,
                mode="lines+markers",
                marker=dict(color="#3b82f6", size=10),
                line=dict(color="#3b82f6", width=2),
                yaxis="y2",
            ))
        fig.update_layout(
            title="Frustration Heatmap by DFA State",
            yaxis=dict(title="Frustration Score (0–1)", range=[0, 1.2]),
            yaxis2=dict(title="Heart Rate (bpm)", overlaying="y", side="right"),
            **_dark_layout(),
        )

    else:
        emotion_cols = [c for c in EMOTION_COLORS if c in cols]
        for emotion in emotion_cols:
            fig.add_trace(go.Bar(
                name=emotion.capitalize(),
                x=states,
                y=[r.get(emotion) or 0 for r in rows],
                marker_color=EMOTION_COLORS[emotion],
            ))
        fig.update_layout(
            title="Emotions by DFA State",
            barmode="group",
            yaxis=dict(title="Score (0–1)", range=[0, 1.1]),
            **_dark_layout(),
        )

    return to_html(fig, include_plotlyjs="cdn", full_html=False)


def _scatter(rows: list[dict]) -> str:
    y_col = "avg_confusion" if "avg_confusion" in rows[0] else "confusion"

    fig = px.scatter(
        rows,
        x="time_delta_sec",
        y=y_col,
        color="dfa_state" if "dfa_state" in rows[0] else None,
        text="dfa_state"  if "dfa_state" in rows[0] else None,
        title="Time Delta vs. Confusion — Where Players Got Stuck",
        labels={
            "time_delta_sec": "Extra Time vs. Optimal (seconds)",
            y_col: "Avg Confusion Score",
        },
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_traces(marker=dict(size=14), textposition="top center")
    fig.add_vline(
        x=0,
        line_dash="dash",
        line_color="#64748b",
        annotation_text="On Time",
        annotation_font_color="#94a3b8",
    )
    fig.update_layout(**_dark_layout())
    return to_html(fig, include_plotlyjs="cdn", full_html=False)


def _health_bar(rows: list[dict]) -> str:
    sessions = [r.get("session_id", f"Session {i+1}")[:14] for i, r in enumerate(rows)]
    scores   = [r.get("health_score") or 0 for r in rows]

    fig = go.Figure(go.Bar(
        x=sessions,
        y=scores,
        marker_color=[
            "#22c55e" if s >= 0.8 else "#f97316" if s >= 0.5 else "#ef4444"
            for s in scores
        ],
        text=[f"{s:.2f}" for s in scores],
        textposition="outside",
    ))
    fig.add_hline(
        y=0.8,
        line_dash="dot",
        line_color="#22c55e",
        annotation_text="Target ≥ 0.8",
        annotation_font_color="#22c55e",
    )
    fig.update_layout(
        title="Playtest Health Score by Session",
        yaxis=dict(title="Health Score", range=[0, 1.15]),
        **_dark_layout(),
    )
    return to_html(fig, include_plotlyjs="cdn", full_html=False)


def _timeline(rows: list[dict]) -> str:
    t   = [r.get("t_second", 0) for r in rows]
    fig = go.Figure()

    for emotion, color in EMOTION_COLORS.items():
        if emotion in rows[0]:
            fig.add_trace(go.Scatter(
                name=emotion.capitalize(),
                x=t,
                y=[r.get(emotion) for r in rows],
                mode="lines",
                line=dict(color=color, width=2),
            ))

    if "dfa_state" in rows[0]:
        _add_state_bands(fig, rows, t)

    fig.update_layout(
        title="Emotion Timeline",
        xaxis=dict(title="Time (seconds)"),
        yaxis=dict(title="Score (0–1)", range=[0, 1.1]),
        **_dark_layout(),
    )
    return to_html(fig, include_plotlyjs="cdn", full_html=False)


def _add_state_bands(fig: go.Figure, rows: list[dict], t: list):
    current_state = None
    band_start    = 0

    for i, row in enumerate(rows):
        state = row.get("dfa_state")
        if state != current_state:
            if current_state is not None:
                fig.add_vrect(
                    x0=band_start,
                    x1=t[i - 1],
                    fillcolor=STATE_BAND_COLORS.get(current_state, "rgba(255,255,255,0.05)"),
                    line_width=0,
                    annotation_text=current_state,
                    annotation_position="top left",
                    annotation_font=dict(color="#94a3b8", size=11),
                )
            current_state = state
            band_start    = t[i]


def _table(rows: list[dict]) -> str:
    cols = list(rows[0].keys())
    fig  = go.Figure(go.Table(
        header=dict(
            values=[c.upper() for c in cols],
            fill_color="#1e293b",
            font=dict(color="white", size=13),
            align="left",
            line_color="#334155",
        ),
        cells=dict(
            values=[[r.get(c) for r in rows] for c in cols],
            fill_color="#0f172a",
            font=dict(color="#94a3b8", size=12),
            align="left",
            line_color="#1e293b",
        ),
    ))
    fig.update_layout(**_dark_layout())
    return to_html(fig, include_plotlyjs="cdn", full_html=False)


def _dark_layout() -> dict:
    return dict(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#e2e8f0", family="Inter, system-ui, sans-serif"),
        legend=dict(bgcolor="#1e293b", bordercolor="#334155", borderwidth=1),
        margin=dict(l=60, r=60, t=70, b=60),
        hoverlabel=dict(bgcolor="#1e293b", bordercolor="#334155", font_color="white"),
    )
