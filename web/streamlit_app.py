from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

try:
    from st_aggrid import AgGrid, GridOptionsBuilder  # type: ignore
    AGGRID_OK = True
except Exception:
    AGGRID_OK = False

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
from valoracion_backend import (  # noqa: E402
    build_account_income_table,
    build_balance_table,
    build_cashflow_table,
    ddm_gordon_value,
    get_dividend_last_full_year_from_income_table,
    per_last_4_years_from_eps,
    per_valuation_intrinsic_value,
)

# ─────────────────────────────────────────────
#  CSS estilo Apple
# ─────────────────────────────────────────────

_APPLE_DARK = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Reset & base */
html, body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                 "SF Pro Text", "Inter", "Helvetica Neue", Arial, sans-serif !important;
    background: #000000 !important;
    color: #f5f5f7 !important;
    -webkit-font-smoothing: antialiased;
}

/* Cuerpo principal */
section.main > div { background: #000000 !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #1c1c1e !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}
section[data-testid="stSidebar"] * { color: #f5f5f7 !important; }

/* Título principal */
h1 { font-size: 2.2rem !important; font-weight: 700 !important;
     letter-spacing: -0.03em !important; color: #f5f5f7 !important; }
h2, h3 { font-weight: 600 !important; letter-spacing: -0.02em !important;
          color: #f5f5f7 !important; }
h4, h5 { font-weight: 500 !important; color: #ebebf5 !important; }

/* Tabs */
div[data-testid="stTabs"] button {
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    color: #98989d !important;
    border-bottom: 2px solid transparent !important;
    padding: 8px 16px !important;
    transition: color 0.2s, border-color 0.2s !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #2997ff !important;
    border-bottom: 2px solid #2997ff !important;
}

/* Botones principales y de formulario */
.stButton > button,
button[kind="primaryFormSubmit"],
button[kind="secondaryFormSubmit"],
div[data-testid="stFormSubmitButton"] > button,
button[data-testid="baseButton-primaryFormSubmit"],
button[data-testid="baseButton-secondaryFormSubmit"] {
    background: #2997ff !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 980px !important;
    padding: 8px 22px !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    cursor: pointer !important;
    transition: background 0.2s !important;
}
.stButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover,
button[data-testid="baseButton-primaryFormSubmit"]:hover {
    background: #0077ed !important;
}
/* Texto interior del botón (span/p que Streamlit mete dentro) */
div[data-testid="stFormSubmitButton"] > button *,
.stButton > button * {
    color: #ffffff !important;
}

/* Botones stepper (+/−) de number_input — modo oscuro */
div[data-testid="stNumberInput"] button,
.stNumberInput button {
    background: rgba(255,255,255,0.08) !important;
    color: #f5f5f7 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 6px !important;
}

/* Inputs */
input[type="text"], .stTextInput input {
    background: #1c1c1e !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
    color: #f5f5f7 !important;
    padding: 8px 14px !important;
    font-size: 0.95rem !important;
    transition: border-color 0.2s !important;
}
input[type="text"]:focus, .stTextInput input:focus {
    border-color: #2997ff !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(41,151,255,0.20) !important;
}

/* Number inputs */
input[type="number"] {
    background: #1c1c1e !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
    color: #f5f5f7 !important;
    padding: 6px 12px !important;
}
input[type="number"]:focus {
    border-color: #2997ff !important;
    box-shadow: 0 0 0 3px rgba(41,151,255,0.20) !important;
}

/* Labels */
label, .stTextInput label, .stNumberInput label {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #98989d !important;
    letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
}

/* Divider */
hr { border-color: rgba(255,255,255,0.08) !important; }

/* Info / warning / error */
div[data-testid="stAlertContainer"] {
    border-radius: 12px !important;
    border: none !important;
}

/* Plotly charts */
div[data-testid="stPlotlyChart"] {
    background: #1c1c1e !important;
    border-radius: 16px !important;
    padding: 8px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
}

/* Formularios / containers */
div[data-testid="stForm"] {
    background: #1c1c1e !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 16px !important;
    padding: 16px 20px !important;
}

/* Contenedor AgGrid: card con borde sutil */
div[class*="stAgGrid"], div[data-testid="stAgGridComponent"] {
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.18); border-radius: 999px; }
</style>
"""

_APPLE_LIGHT = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                 "SF Pro Text", "Inter", "Helvetica Neue", Arial, sans-serif !important;
    background: #f5f5f7 !important;
    color: #1d1d1f !important;
    -webkit-font-smoothing: antialiased;
}

section.main > div { background: #f5f5f7 !important; }

section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid rgba(0,0,0,0.08) !important;
}
section[data-testid="stSidebar"] * { color: #1d1d1f !important; }

h1 { font-size: 2.2rem !important; font-weight: 700 !important;
     letter-spacing: -0.03em !important; color: #1d1d1f !important; }
h2, h3 { font-weight: 600 !important; letter-spacing: -0.02em !important;
          color: #1d1d1f !important; }
h4, h5 { font-weight: 500 !important; color: #3a3a3c !important; }

div[data-testid="stTabs"] button {
    font-size: 0.9rem !important; font-weight: 500 !important;
    color: #6e6e73 !important;
    border-bottom: 2px solid transparent !important;
    padding: 8px 16px !important;
    transition: color 0.2s, border-color 0.2s !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #0071e3 !important;
    border-bottom: 2px solid #0071e3 !important;
}

.stButton > button,
button[kind="primaryFormSubmit"],
button[kind="secondaryFormSubmit"],
div[data-testid="stFormSubmitButton"] > button,
button[data-testid="baseButton-primaryFormSubmit"],
button[data-testid="baseButton-secondaryFormSubmit"] {
    background: #0071e3 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 980px !important;
    padding: 8px 22px !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    cursor: pointer !important;
    transition: background 0.2s !important;
}
.stButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover,
button[data-testid="baseButton-primaryFormSubmit"]:hover {
    background: #005bbf !important;
}
/* Texto interior del botón */
div[data-testid="stFormSubmitButton"] > button *,
.stButton > button * {
    color: #ffffff !important;
}

/* Botones stepper (+/−) de number_input — modo claro */
div[data-testid="stNumberInput"] button,
.stNumberInput button {
    background: #f5f5f7 !important;
    color: #6e6e73 !important;
    border: 1px solid rgba(0,0,0,0.12) !important;
    border-radius: 6px !important;
}
div[data-testid="stNumberInput"] button:hover,
.stNumberInput button:hover {
    background: #e8e8ed !important;
    color: #1d1d1f !important;
}

input[type="text"], .stTextInput input {
    background: #ffffff !important;
    border: 1px solid rgba(0,0,0,0.15) !important;
    border-radius: 10px !important;
    color: #1d1d1f !important;
    padding: 8px 14px !important;
    font-size: 0.95rem !important;
    transition: border-color 0.2s !important;
}
input[type="text"]:focus, .stTextInput input:focus {
    border-color: #0071e3 !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(0,113,227,0.18) !important;
}

input[type="number"] {
    background: #ffffff !important;
    border: 1px solid rgba(0,0,0,0.15) !important;
    border-radius: 10px !important;
    color: #1d1d1f !important;
    padding: 6px 12px !important;
}
input[type="number"]:focus {
    border-color: #0071e3 !important;
    box-shadow: 0 0 0 3px rgba(0,113,227,0.18) !important;
}

label, .stTextInput label, .stNumberInput label {
    font-size: 0.82rem !important; font-weight: 500 !important;
    color: #6e6e73 !important; letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
}

hr { border-color: rgba(0,0,0,0.08) !important; }

div[data-testid="stAlertContainer"] {
    border-radius: 12px !important; border: none !important;
}

div[data-testid="stPlotlyChart"] {
    background: #ffffff !important;
    border-radius: 16px !important;
    padding: 8px !important;
    border: 1px solid rgba(0,0,0,0.06) !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
}

div[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1px solid rgba(0,0,0,0.08) !important;
    border-radius: 16px !important;
    padding: 16px 20px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05) !important;
}

/* Contenedor AgGrid: card con sombra suave */
div[class*="stAgGrid"], div[data-testid="stAgGridComponent"] {
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid rgba(0,0,0,0.06) !important;
    box-shadow: 0 2px 16px rgba(0,0,0,0.07) !important;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 999px; }
</style>
"""


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _calc_yoy(vals: List[float], mas_reciente_primero: bool = True) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(vals)
    n = len(vals)
    if n <= 1:
        return out
    if mas_reciente_primero:
        for i in range(n - 1):
            prev = vals[i + 1]
            out[i] = None if (prev is None or prev == 0) else (vals[i] / prev - 1.0) * 100.0
    else:
        for i in range(1, n):
            prev = vals[i - 1]
            out[i] = None if (prev is None or prev == 0) else (vals[i] / prev - 1.0) * 100.0
    return out


def _chart_theme(dark: bool) -> dict:
    """Devuelve los colores base para gráficos según el tema."""
    if dark:
        return dict(
            paper_bg="#1c1c1e", plot_bg="#1c1c1e",
            font_col="#f5f5f7", axis_col="#ebebf5",
            tick_col="#98989d", grid_col="rgba(255,255,255,0.07)",
            line_col="rgba(255,255,255,0.15)",
        )
    return dict(
        paper_bg="#ffffff", plot_bg="#ffffff",
        font_col="#1d1d1f", axis_col="#1d1d1f",
        tick_col="#3a3a3c", grid_col="rgba(0,0,0,0.07)",
        line_col="rgba(0,0,0,0.15)",
    )


def _apply_axis_style(fig: go.Figure, t: dict, secondary: bool = False) -> None:
    """Aplica colores de ejes a todos los ejes del gráfico."""
    axis_style = dict(
        title_font=dict(color=t["axis_col"]),
        tickfont=dict(color=t["tick_col"]),
        gridcolor=t["grid_col"],
        linecolor=t["line_col"],
        zerolinecolor=t["line_col"],
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)


def _plot_grouped_bars(df_numeric: pd.DataFrame, metrics: List[str], title: str) -> go.Figure:
    years = list(df_numeric.columns)
    metrics = [m for m in metrics if m in df_numeric.index][:2]

    dark = st.session_state.get("theme", "dark") == "dark"
    t = _chart_theme(dark)
    accent = ["#2997ff", "#ff9f0a"] if dark else ["#0071e3", "#ff9500"]

    def to_float_list(metric: str) -> List[float]:
        vals = []
        for y in years:
            v = df_numeric.loc[metric, y]
            try:
                vals.append(0.0 if pd.isna(v) else float(v))
            except Exception:
                vals.append(0.0)
        return vals

    fig = go.Figure()
    for idx, metric in enumerate(metrics):
        vals = to_float_list(metric)
        yoy_vals = _calc_yoy(vals)
        yoy_txt = ["YoY: N/A" if yv is None else f"YoY: {yv:+.1f}%" for yv in yoy_vals]
        fig.add_trace(go.Bar(
            name=metric, x=years, y=vals,
            marker_color=accent[idx % len(accent)],
            marker_line_width=0,
            customdata=yoy_txt,
            hovertemplate="<b>%{x}</b><br>" + f"{metric}: " + "%{y:.2f}<br>%{customdata[0]}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=t["font_col"], family="Inter, -apple-system")),
        barmode="group" if len(metrics) == 2 else "relative",
        paper_bgcolor=t["paper_bg"], plot_bgcolor=t["plot_bg"],
        font=dict(color=t["font_col"], family="Inter, -apple-system"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=12, color=t["font_col"])),
        margin=dict(l=40, r=20, t=60, b=40),
        xaxis=dict(title="Año"),
        yaxis=dict(title="Valor"),
        bargap=0.25, bargroupgap=0.08,
    )
    _apply_axis_style(fig, t)
    return fig


def _dividend_growth_chart(df_income: pd.DataFrame) -> Optional[go.Figure]:
    if df_income is None or df_income.empty or "Dividendo Anual" not in df_income.index:
        return None
    try:
        s = df_income.loc["Dividendo Anual"].dropna()
        if s.empty:
            return None
        years = list(s.index[:4])
        vals = [float(s.loc[y]) for y in years]
        if len(vals) < 2:
            return None

        yoy: List[Optional[float]] = [None] * len(vals)
        for i in range(len(vals) - 1):
            prev = vals[i + 1]
            yoy[i] = None if prev == 0 else (vals[i] / prev - 1) * 100

        dark = st.session_state.get("theme", "dark") == "dark"
        t = _chart_theme(dark)
        bar_col = "#2997ff" if dark else "#0071e3"

        pt_colors = [
            "rgba(0,0,0,0)" if v is None else ("#34c759" if v >= 0 else "#ff3b30")
            for v in yoy
        ]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(
            name="Dividendo anual", x=years, y=vals,
            marker_color=bar_col, marker_line_width=0,
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            name="Crecimiento YoY (%)", x=years,
            y=[v if v is not None else None for v in yoy],
            mode="lines+markers+text",
            line=dict(color=t["tick_col"], width=2),
            marker=dict(color=pt_colors, size=10),
            text=[("" if v is None else f"{v:+.1f}%") for v in yoy],
            textposition="top center",
            textfont=dict(color=pt_colors, size=12, family="Inter, -apple-system"),
        ), secondary_y=True)

        fig.update_layout(
            title=dict(text="Dividendos (últimos 4 años) y crecimiento YoY",
                       font=dict(size=15, color=t["font_col"], family="Inter, -apple-system")),
            paper_bgcolor=t["paper_bg"], plot_bgcolor=t["plot_bg"],
            font=dict(color=t["font_col"], family="Inter, -apple-system"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(color=t["font_col"])),
            margin=dict(l=40, r=20, t=60, b=40),
        )
        axis_style = dict(
            title_font=dict(color=t["axis_col"]),
            tickfont=dict(color=t["tick_col"]),
            gridcolor=t["grid_col"],
            linecolor=t["line_col"],
        )
        fig.update_yaxes(title_text="Dividendo ($)", **axis_style, secondary_y=False)
        fig.update_yaxes(title_text="Crecimiento (%)", **axis_style, secondary_y=True)
        fig.update_xaxes(**axis_style)
        return fig
    except Exception:
        return None


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_all_tables(ticker: str, fmp_api_key: str):
    res_income = build_account_income_table(ticker, api_key=fmp_api_key)
    res_balance = build_balance_table(ticker, api_key=fmp_api_key)
    res_cf = build_cashflow_table(ticker, api_key=fmp_api_key)
    return res_income, res_balance, res_cf


def _coerce_max_two(selected: List[str]) -> List[str]:
    return selected[-2:]


def _toggle_metric(selected: List[str], metric: str) -> List[str]:
    if metric in selected:
        selected = [m for m in selected if m != metric]
    else:
        selected = selected + [metric]
    return _coerce_max_two(selected)


def _style_selected_rows(df: pd.DataFrame, selected: List[str]):
    selected_set = set(selected)
    dark = st.session_state.get("theme", "dark") == "dark"
    hl = "rgba(41,151,255,0.20)" if dark else "rgba(0,113,227,0.12)"

    def highlight_row(row: pd.Series):
        if row.name in selected_set:
            return [f"background-color: {hl}; font-weight: 600"] * len(row)
        return [""] * len(row)

    return df.style.apply(highlight_row, axis=1)


def _clickable_table(df_fmt: pd.DataFrame, selected: List[str], *, state_prefix: str) -> List[str]:
    event = st.dataframe(
        _style_selected_rows(df_fmt, selected),
        width="stretch", height=420,
        on_select="rerun", selection_mode="single-row",
        key=f"{state_prefix}_df",
    )
    last_key = f"{state_prefix}_last_clicked"
    if last_key not in st.session_state:
        st.session_state[last_key] = None

    clicked_metric: Optional[str] = None
    try:
        rows: List[int] = list(getattr(event, "selection", {}).get("rows", []))
        if rows:
            clicked_metric = df_fmt.index[rows[0]]
    except Exception:
        clicked_metric = None

    if clicked_metric is not None and clicked_metric != st.session_state[last_key]:
        st.session_state[last_key] = clicked_metric
        selected = _toggle_metric(selected, str(clicked_metric))
    return selected


def _aggrid_table_click_any_cell(
    df_fmt: pd.DataFrame,
    selected: List[str],
    *,
    state_prefix: str,
) -> List[str]:
    if not AGGRID_OK:
        return _clickable_table(df_fmt, selected, state_prefix=state_prefix)

    dark = st.session_state.get("theme", "dark") == "dark"
    accent_color = "#2997ff" if dark else "#0071e3"

    # ── La clave del fix: el estado de selección va en los DATOS,
    #    no en la lista hardcodeada del JsCode.  AgGrid re-pinta las
    #    celdas en cada rerun porque los datos cambian, mientras que
    #    el JsCode compilado con una lista fija queda cacheado.
    df_grid = df_fmt.reset_index().rename(columns={"index": "Métrica"})
    df_grid["_sel"] = df_grid["Métrica"].isin(selected)

    from st_aggrid import JsCode  # noqa: PLC0415

    metric_cell_style = JsCode(f"""
function(params) {{
    if (params.data && params.data._sel === true) {{
        return {{
            fontWeight: '700',
            color: '{accent_color}',
            borderLeft: '3px solid {accent_color}',
            paddingLeft: '13px',
            textAlign: 'left',
        }};
    }}
    return {{
        fontWeight: '600',
        textAlign: 'left',
        paddingLeft: '16px',
        borderLeft: '3px solid transparent',
    }};
}}
""")

    gb = GridOptionsBuilder.from_dataframe(df_grid)
    gb.configure_selection("single", use_checkbox=False)
    gb.configure_grid_options(
        suppressRowClickSelection=False,
        rowSelection="single",
        headerHeight=38,
        rowHeight=40,
        suppressCellFocus=True,
        enableCellTextSelection=False,
    )
    gb.configure_default_column(
        resizable=True, sortable=False, filter=False, wrapText=False,
        cellStyle={"textAlign": "right", "letterSpacing": "0.01em"},
        headerClass="apple-header",
    )
    gb.configure_column(
        "Métrica", pinned="left", width=240,
        cellStyle=metric_cell_style,
        headerClass="apple-header",
    )
    # Ocultar la columna auxiliar _sel
    gb.configure_column("_sel", hide=True)
    grid_opts = gb.build()

    if dark:
        bg        = "#1c1c1e"
        fg        = "#f5f5f7"
        header_bg = "#1c1c1e"
        header_fg = "#98989d"
        odd_bg    = "rgba(255,255,255,0.025)"
        hover_bg  = "rgba(41,151,255,0.09)"
        sel_bg    = "rgba(41,151,255,0.14)"
        border    = "rgba(255,255,255,0.07)"
        sep       = "rgba(255,255,255,0.06)"
    else:
        bg        = "#ffffff"
        fg        = "#1d1d1f"
        header_bg = "#ffffff"
        header_fg = "#6e6e73"
        odd_bg    = "rgba(0,0,0,0.018)"
        hover_bg  = "rgba(0,113,227,0.07)"
        sel_bg    = "rgba(0,113,227,0.10)"
        border    = "rgba(0,0,0,0.07)"
        sep       = "rgba(0,0,0,0.06)"

    # Selector base según el tema que AgGrid va a aplicar
    base = ".ag-theme-streamlit" if dark else ".ag-theme-alpine"

    custom_css = {
        # ── Variables CSS (funciona bien en dark/streamlit) ──────────────
        base: {
            "--ag-background-color": bg,
            "--ag-foreground-color": fg,
            "--ag-header-background-color": header_bg,
            "--ag-header-foreground-color": header_fg,
            "--ag-odd-row-background-color": odd_bg,
            "--ag-row-hover-color": hover_bg,
            "--ag-selected-row-background-color": sel_bg,
            "--ag-border-color": border,
            "--ag-row-border-color": sep,
            "--ag-cell-horizontal-border": "none",
            "--ag-font-size": "13px",
            "--ag-font-family": "Inter, -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif",
            "--ag-grid-size": "5px",
            "--ag-list-item-height": "40px",
        },
        # ── Overrides directos (necesario en light/alpine para ganar al tema) ──
        f"{base} .ag-root-wrapper": {
            "background-color": f"{bg} !important",
            "color": f"{fg} !important",
            "border-radius": "14px !important",
            "overflow": "hidden !important",
            "border": f"1px solid {border} !important",
        },
        f"{base} .ag-header": {
            "background-color": f"{header_bg} !important",
            "border-bottom": f"1px solid {sep} !important",
        },
        f"{base} .ag-header-cell-text": {
            "font-size": "11px !important",
            "font-weight": "500 !important",
            "letter-spacing": "0.06em !important",
            "text-transform": "uppercase !important",
            "color": f"{header_fg} !important",
        },
        f"{base} .ag-header-cell": {
            "border-right": "none !important",
            "padding-left": "16px !important",
        },
        f"{base} .ag-row": {
            "background-color": f"{bg} !important",
            "color": f"{fg} !important",
            "border-bottom": f"1px solid {sep} !important",
        },
        f"{base} .ag-row-odd": {
            "background-color": f"{odd_bg} !important",
        },
        f"{base} .ag-cell": {
            "border-right": "none !important",
            "padding-right": "20px !important",
            "display": "flex !important",
            "align-items": "center !important",
            "color": f"{fg} !important",
        },
        f"{base} .ag-row-selected": {
            "background-color": f"{sel_bg} !important",
        },
        f"{base} .ag-row-selected .ag-cell": {
            "background-color": "transparent !important",
        },
        f"{base} .ag-row:hover": {
            "background-color": f"{hover_bg} !important",
            "cursor": "pointer !important",
        },
        f"{base} .ag-pinned-left-cols-container": {
            "border-right": f"1px solid {sep} !important",
            "background-color": f"{bg} !important",
        },
        f"{base} .ag-pinned-left-header": {
            "background-color": f"{header_bg} !important",
        },
    }

    # En modo claro usamos "alpine" para romper la herencia de la paleta oscura de Streamlit.
    # En modo oscuro usamos "streamlit" que ya va bien.
    aggrid_theme = "streamlit" if dark else "alpine"

    resp = AgGrid(
        df_grid, gridOptions=grid_opts,
        update_on=["selectionChanged"],
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        key=f"{state_prefix}_aggrid",
        height=440, theme=aggrid_theme,
        custom_css=custom_css,
    )

    rows_any: Any = resp.get("selected_rows", None)
    clicked: Optional[str] = None
    try:
        if isinstance(rows_any, list) and len(rows_any) > 0:
            clicked = rows_any[0].get("Métrica")
        elif isinstance(rows_any, pd.DataFrame) and not rows_any.empty:
            if "Métrica" in rows_any.columns:
                clicked = rows_any.iloc[0].get("Métrica")
    except Exception:
        clicked = None

    if clicked is None:
        return selected

    clicked = str(clicked)

    # Protección contra re-renders sin nuevo clic real:
    # AgGrid devuelve siempre la fila seleccionada aunque no se haya clicado de nuevo.
    # Usamos last_key solo para detectar si es un clic NUEVO (distinto al anterior).
    last_key = f"{state_prefix}_last_clicked"
    if last_key not in st.session_state:
        st.session_state[last_key] = None

    prev = st.session_state[last_key]

    # Es un clic nuevo si cambia la fila seleccionada en AgGrid
    if clicked == prev:
        # Misma fila que la última vez → no es un clic nuevo, no hacemos nada
        return selected

    # Nuevo clic: actualizar last_key y hacer toggle
    st.session_state[last_key] = clicked

    if clicked in selected:
        selected = [m for m in selected if m != clicked]
    else:
        selected = (selected + [clicked])[-2:]
    return selected


def _colored_value_html(label: str, v: float, price: Optional[float]) -> str:
    if price is None:
        return f'<div style="margin-bottom:8px"><span style="font-weight:700">{label}</span><br><span style="font-size:1.5rem;font-weight:800">${v:.2f}</span></div>'
    barato = price < v
    color = "#34c759" if barato else "#ff3b30"
    status = "barato" if barato else "caro"
    return (
        f'<div style="margin-bottom:8px">'
        f'<div style="font-size:0.78rem;font-weight:500;letter-spacing:0.05em;text-transform:uppercase;'
        f'color:#98989d;margin-bottom:4px">{label}</div>'
        f'<span style="color:{color};font-size:1.6rem;font-weight:800">${v:.2f}</span>'
        f'<span style="color:{color};margin-left:10px;font-size:0.9rem">'
        f'vs ${price:.2f} → {status}</span>'
        f'</div>'
    )


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    st.set_page_config(page_title="DB Finance", page_icon="📈", layout="wide")

    # ── Estado de sesión ────────────────────────
    defaults = {
        "last_ticker": "", "data": None,
        "sel_income": [], "sel_balance": [], "sel_cf": [],
        "theme": "dark",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Sidebar ──────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Ajustes")
        modo_claro = st.toggle("Modo claro", value=(st.session_state.theme == "light"))
        st.session_state.theme = "light" if modo_claro else "dark"

        # API key — robusta: intenta secrets, luego vacío
        fmp_key = ""
        try:
            fmp_key = st.secrets.get("FMP_API_KEY", "")
        except Exception:
            pass
        if not fmp_key:
            st.error("Falta `FMP_API_KEY` en Secrets.")

        st.markdown("---")
        st.markdown(
            "<div style='font-size:0.75rem;color:#6e6e73'>Datos: Financial Modeling Prep</div>",
            unsafe_allow_html=True,
        )

    # ── Inyectar CSS según tema ──────────────────
    st.markdown(_APPLE_LIGHT if st.session_state.theme == "light" else _APPLE_DARK,
                unsafe_allow_html=True)

    # ── Header ───────────────────────────────────
    st.markdown("# DB Finance")
    st.markdown(
        "<p style='color:#6e6e73;margin-top:-12px;margin-bottom:24px;font-size:1rem'>"
        "Análisis fundamental y valoración de acciones</p>",
        unsafe_allow_html=True,
    )

    # ── Buscador ─────────────────────────────────
    with st.form("search_form", clear_on_submit=False):
        c1, c2, c3 = st.columns([2, 1, 5])
        with c1:
            ticker = st.text_input(
                "Ticker", value=st.session_state.last_ticker or "AAPL",
                placeholder="AAPL, MSFT, AMZN…",
            ).strip().upper()
        with c2:
            st.markdown("<div style='margin-top:24px'>", unsafe_allow_html=True)
            buscar = st.form_submit_button("Buscar")
            st.markdown("</div>", unsafe_allow_html=True)

    if buscar and fmp_key:
        try:
            with st.spinner(f"Cargando {ticker}…"):
                res_income, res_balance, res_cf = load_all_tables(ticker, fmp_key)
            st.session_state.data = (res_income, res_balance, res_cf)
            st.session_state.last_ticker = ticker

            inc_idx = list(res_income["df_numeric"].index)
            bal_idx = list(res_balance["df_numeric"].index)
            cf_idx  = list(res_cf["df_numeric"].index)

            st.session_state.sel_income  = [m for m in st.session_state.sel_income  if m in inc_idx] or inc_idx[:2]
            st.session_state.sel_balance = [m for m in st.session_state.sel_balance if m in bal_idx] or bal_idx[:2]
            st.session_state.sel_cf      = [m for m in st.session_state.sel_cf      if m in cf_idx]  or cf_idx[:2]
        except Exception as e:
            st.error(f"No se pudo cargar '{ticker}'. Detalle: {e}")

    if st.session_state.data is None:
        st.markdown(
            "<div style='margin-top:40px;text-align:center;color:#6e6e73'>"
            "Introduce un ticker y pulsa <b>Buscar</b> para comenzar."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    res_income, res_balance, res_cf = st.session_state.data
    df_income     = res_income["df_numeric"]
    df_income_fmt = res_income["df_formatted"]
    df_balance    = res_balance["df_numeric"]
    df_balance_fmt = res_balance["df_formatted"]
    df_cf         = res_cf["df_numeric"]
    df_cf_fmt     = res_cf["df_formatted"]

    # Nombre de la empresa si está disponible
    ticker_label = st.session_state.last_ticker
    try:
        info = res_income.get("info") or {}
        nombre = info.get("companyName") or info.get("longName") or ticker_label
        precio_actual: Optional[float] = None
        p = info.get("price") or info.get("currentPrice") or info.get("regularMarketPrice")
        if p:
            precio_actual = float(p)
    except Exception:
        nombre = ticker_label
        precio_actual = None

    st.markdown(
        f"<h2 style='margin-bottom:4px'>{nombre} "
        f"<span style='font-size:1rem;color:#6e6e73'>{ticker_label}</span></h2>",
        unsafe_allow_html=True,
    )
    if precio_actual:
        dark = st.session_state.theme == "dark"
        acc = "#2997ff" if dark else "#0071e3"
        st.markdown(
            f"<p style='color:{acc};font-size:1.3rem;font-weight:600;margin-top:0'>"
            f"${precio_actual:,.2f}</p>",
            unsafe_allow_html=True,
        )

    # ── Tabs ──────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Cuenta de resultados", "Balance", "Flujos de caja", "Valoración"]
    )

    dark = st.session_state.theme == "dark"
    hint_color = "#98989d"
    sel_color  = "#2997ff" if dark else "#0071e3"

    def _render_tab(df_num, df_fmt, sel_key, prefix, title):
        st.session_state[sel_key] = _aggrid_table_click_any_cell(
            df_fmt, st.session_state[sel_key], state_prefix=prefix,
        )
        metrics = st.session_state[sel_key]

        # Hint debajo de la tabla
        if metrics:
            chips = "".join(
                f"<span style='display:inline-block;background:{sel_color}22;"
                f"color:{sel_color};border:1px solid {sel_color}44;"
                f"border-radius:20px;padding:2px 12px;font-size:12px;"
                f"font-weight:600;margin-right:6px'>{m}</span>"
                for m in metrics
            )
            st.markdown(
                f"<div style='margin-top:6px;margin-bottom:10px'>{chips}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='margin-top:6px;margin-bottom:10px;"
                f"font-size:12px;color:{hint_color}'>"
                "Toca una fila para añadirla a la gráfica · máx. 2</div>",
                unsafe_allow_html=True,
            )

        if metrics:
            fig = _plot_grouped_bars(df_num, metrics, title=title)
            st.plotly_chart(fig, width="stretch")

    with tab1:
        _render_tab(df_income, df_income_fmt, "sel_income", "income", "Cuenta de resultados")

    with tab2:
        _render_tab(df_balance, df_balance_fmt, "sel_balance", "balance", "Balance")

    with tab3:
        _render_tab(df_cf, df_cf_fmt, "sel_cf", "cf", "Flujos de caja")

    # ── Tab Valoración ────────────────────────────
    with tab4:
        # EPS actual
        eps_series = res_income.get("eps_series")
        eps_actual: Optional[float] = None
        try:
            if eps_series is not None and len(eps_series) > 0:
                eps_actual = float(pd.Series(eps_series).sort_index(ascending=False).iloc[0])
        except Exception:
            pass

        years_all = list(df_income.columns)
        years_4 = years_all[:4]

        eps_by_year: dict[str, float] = {}
        try:
            if eps_series is not None:
                s = pd.Series(eps_series).sort_index(ascending=False).iloc[:4]
                for idx, v in s.items():
                    y = str(getattr(idx, "year", None) or str(idx)[:4])[:4]
                    eps_by_year[y] = float(v)
        except Exception:
            pass

        eps_vals_4 = [float(eps_by_year.get(str(y), 0.0)) for y in years_4]

        per_vals_4: List[Optional[float]] = [None] * len(years_4)
        if years_4 and eps_by_year:
            try:
                per_vals_4 = per_last_4_years_from_eps(
                    st.session_state.last_ticker, years_4, eps_by_year, api_key=fmp_key
                )
            except Exception:
                pass

        net_margin_vals_4: List[Optional[float]] = [None] * len(years_4)
        try:
            if "Net Margin (%)" in df_income.index:
                for i, y in enumerate(years_4):
                    v = df_income.loc["Net Margin (%)", y]
                    net_margin_vals_4[i] = None if pd.isna(v) else float(v)
        except Exception:
            pass

        # ─ Gráfico EPS / PER / Margen
        if years_4:
            dark = st.session_state.theme == "dark"
            t = _chart_theme(dark)
            bar_col   = "#2997ff" if dark else "#0071e3"
            per_col   = "#ff9f0a" if dark else "#ff9500"

            fig_val = make_subplots(specs=[[{"secondary_y": True}]])
            fig_val.add_trace(go.Bar(
                name="EPS", x=years_4, y=eps_vals_4,
                marker_color=bar_col, marker_line_width=0,
            ), secondary_y=False)
            fig_val.add_trace(go.Scatter(
                name="PER", x=years_4,
                y=[p if p is not None else None for p in per_vals_4],
                mode="lines+markers", line=dict(color=per_col, width=2),
                marker=dict(size=7),
            ), secondary_y=True)
            fig_val.add_trace(go.Scatter(
                name="Margen neto (%)", x=years_4,
                y=[m if m is not None else None for m in net_margin_vals_4],
                mode="lines+markers", line=dict(color="#34c759", width=2, dash="dot"),
                marker=dict(size=7),
            ), secondary_y=True)
            fig_val.update_layout(
                title=dict(text="EPS, PER y margen neto — últimos 4 años",
                           font=dict(size=15, color=t["font_col"], family="Inter, -apple-system")),
                paper_bgcolor=t["paper_bg"], plot_bgcolor=t["paper_bg"],
                font=dict(color=t["font_col"], family="Inter, -apple-system"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            bgcolor="rgba(0,0,0,0)", font=dict(color=t["font_col"])),
                margin=dict(l=40, r=20, t=60, b=40),
            )
            axis_style = dict(
                title_font=dict(color=t["axis_col"]),
                tickfont=dict(color=t["tick_col"]),
                gridcolor=t["grid_col"],
                linecolor=t["line_col"],
            )
            fig_val.update_xaxes(**axis_style)
            fig_val.update_yaxes(title_text="EPS ($)", **axis_style, secondary_y=False)
            fig_val.update_yaxes(title_text="PER / Margen (%)", **axis_style, secondary_y=True)
            st.plotly_chart(fig_val, width="stretch")

        # ─ PER escenarios
        st.markdown("### Valoración por PER — escenarios")
        if eps_actual is None:
            st.warning("No se pudo obtener el EPS actual.")
        else:
            with st.form("per_form", clear_on_submit=False):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    tasa_desc = st.number_input("Tasa descuento (%)", 0.0, 50.0, 10.0, 0.5)
                with c2:
                    crec_cons = st.number_input("Crecimiento conservador (%)", -50.0, 50.0, 5.0, 0.5)
                    per_cons  = st.number_input("PER conservador", 0.0, 200.0, 15.0, 1.0)
                with c3:
                    crec_real = st.number_input("Crecimiento realista (%)", -50.0, 50.0, 10.0, 0.5)
                    per_real  = st.number_input("PER realista", 0.0, 200.0, 20.0, 1.0)
                with c4:
                    crec_opt = st.number_input("Crecimiento optimista (%)", -50.0, 50.0, 15.0, 0.5)
                    per_opt  = st.number_input("PER optimista", 0.0, 200.0, 25.0, 1.0)
                calcular_per = st.form_submit_button("Calcular precios")

            if calcular_per:
                r = tasa_desc / 100.0
                v_cons = per_valuation_intrinsic_value(eps_actual, crec_cons / 100.0, per_cons, r)
                v_real = per_valuation_intrinsic_value(eps_actual, crec_real / 100.0, per_real, r)
                v_opt  = per_valuation_intrinsic_value(eps_actual, crec_opt  / 100.0, per_opt,  r)

                price_for_color = precio_actual
                if price_for_color is None:
                    try:
                        i = res_income.get("info") or {}
                        p = i.get("currentPrice") or i.get("regularMarketPrice")
                        price_for_color = float(p) if p else None
                    except Exception:
                        pass

                html_vals = "".join([
                    _colored_value_html("Conservador", v_cons, price_for_color),
                    _colored_value_html("Realista",    v_real, price_for_color),
                    _colored_value_html("Optimista",   v_opt,  price_for_color),
                ])
                st.markdown(
                    f"<div style='display:flex;gap:40px;margin-top:12px'>{html_vals}</div>",
                    unsafe_allow_html=True,
                )

        st.divider()

        # ─ DDM
        st.markdown("### Descuento de Dividendos — Gordon Growth")
        d0 = get_dividend_last_full_year_from_income_table(df_income)
        if d0 is None:
            st.warning("No hay datos de dividendo suficientes para DDM.")
        else:
            fig_div = _dividend_growth_chart(df_income)
            if fig_div is not None:
                st.plotly_chart(fig_div, width="stretch")

            with st.form("ddm_form", clear_on_submit=False):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(
                        f"<div style='margin-top:8px'><span style='font-size:0.8rem;color:#6e6e73;"
                        f"text-transform:uppercase;letter-spacing:0.05em'>Dividendo base (D0)</span>"
                        f"<br><span style='font-size:1.4rem;font-weight:700'>${d0:.2f}</span></div>",
                        unsafe_allow_html=True,
                    )
                with c2:
                    g = st.number_input("Crecimiento dividendo (%)", -50.0, 50.0, 5.0, 0.5)
                with c3:
                    r_ddm = st.number_input("Tasa descuento (%)", 0.0, 50.0, 10.0, 0.5)
                calcular_ddm = st.form_submit_button("Calcular DDM")

            if calcular_ddm:
                if r_ddm <= g:
                    st.error("La tasa de descuento debe ser mayor que el crecimiento esperado.")
                else:
                    valor = ddm_gordon_value(d0, g / 100.0, r_ddm / 100.0)
                    price_for_color = precio_actual
                    if price_for_color is None:
                        try:
                            i = res_income.get("info") or {}
                            p = i.get("currentPrice") or i.get("regularMarketPrice")
                            price_for_color = float(p) if p else None
                        except Exception:
                            pass
                    st.markdown(
                        _colored_value_html("Valor intrínseco (DDM)", valor, price_for_color),
                        unsafe_allow_html=True,
                    )


if __name__ == "__main__":
    main()
