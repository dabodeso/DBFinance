from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Optional: AgGrid para click en cualquier celda
try:
    from st_aggrid import AgGrid, GridOptionsBuilder  # type: ignore
    AGGRID_OK = True
except Exception:
    AGGRID_OK = False

# Import local backend
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


def _calc_yoy(vals: List[float], mas_reciente_primero: bool = True) -> List[Optional[float]]:
    # Si el orden es "más reciente primero" (típico en yfinance), el YoY del índice i
    # se compara con i+1.
    out: List[Optional[float]] = [None] * len(vals)
    n = len(vals)
    if n <= 1:
        return out

    if mas_reciente_primero:
        for i in range(n - 1):
            prev = vals[i + 1]
            if prev is None or prev == 0:
                out[i] = None
            else:
                out[i] = (vals[i] / prev - 1.0) * 100.0
    else:
        for i in range(1, n):
            prev = vals[i - 1]
            if prev is None or prev == 0:
                out[i] = None
            else:
                out[i] = (vals[i] / prev - 1.0) * 100.0
    return out


def _plot_grouped_bars(df_numeric: pd.DataFrame, metrics: List[str], title: str) -> go.Figure:
    years = list(df_numeric.columns)
    mas_reciente_primero = True
    # Filtrar métricas inexistentes (por ejemplo, al cambiar de ticker)
    metrics = [m for m in metrics if m in df_numeric.index][:2]

    def to_float_list(metric: str) -> List[float]:
        vals = []
        for y in years:
            v = df_numeric.loc[metric, y]
            try:
                if pd.isna(v):
                    vals.append(0.0)
                else:
                    vals.append(float(v))
            except Exception:
                vals.append(0.0)
        return vals

    fig = go.Figure()

    colors = ["#1f77b4", "#ff7f0e"]
    for idx, metric in enumerate(metrics[:2]):
        vals = to_float_list(metric)
        yoy_vals = _calc_yoy(vals, mas_reciente_primero=mas_reciente_primero)

        yoy_txt: List[str] = []
        for i, yv in enumerate(yoy_vals):
            if yv is None:
                yoy_txt.append("YoY: N/A")
            else:
                yoy_txt.append(f"YoY: {yv:+.1f}%")

        fig.add_trace(
            go.Bar(
                name=metric,
                x=years,
                y=vals,
                marker_color=colors[idx % len(colors)],
                customdata=yoy_txt,
                hovertemplate="<b>%{x}</b><br>"
                f"{metric}: " + "%{y:.2f}<br>"
                "%{customdata[0]}<extra></extra>",
            )
        )

    template = "plotly_dark" if st.session_state.get("theme", "dark") == "dark" else "plotly_white"
    fig.update_layout(
        title=title,
        barmode="group" if len(metrics) == 2 else "relative",
        template=template,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        xaxis_title="Año",
        yaxis_title="Valor",
    )
    return fig


def _dividend_growth_chart(df_income: pd.DataFrame) -> Optional[go.Figure]:
    """
    Barras: dividendo anual (últimos 4 años disponibles).
    Línea: crecimiento YoY (%) en verde si sube, rojo si baja.
    """
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

        colors = []
        for v in yoy:
            if v is None:
                colors.append("rgba(0,0,0,0)")
            elif v >= 0:
                colors.append("#22c55e")  # verde
            else:
                colors.append("#ef4444")  # rojo

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(name="Dividendo anual", x=years, y=vals, marker_color="#1f77b4"),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                name="Crecimiento YoY (%)",
                x=years,
                y=[v if v is not None else None for v in yoy],
                mode="lines+markers+text",
                line=dict(color="#94a3b8", width=2),
                marker=dict(color=colors, size=10),
                text=[("" if v is None else f"{v:+.1f}%") for v in yoy],
                textposition="top center",
            ),
            secondary_y=True,
        )
        template = "plotly_dark" if st.session_state.get("theme", "dark") == "dark" else "plotly_white"
        fig.update_layout(
            title="Dividendos (últimos 4 años) y crecimiento YoY",
            template=template,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=60, b=40),
        )
        fig.update_xaxes(title_text="Año")
        fig.update_yaxes(title_text="Dividendo ($)", secondary_y=False)
        fig.update_yaxes(title_text="Crecimiento (%)", secondary_y=True)
        return fig
    except Exception:
        return None


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_all_tables(ticker: str):
    res_income = build_account_income_table(ticker)
    res_balance = build_balance_table(ticker)
    res_cf = build_cashflow_table(ticker)
    return res_income, res_balance, res_cf


def _coerce_max_two(selected: List[str]) -> List[str]:
    # Mantener las dos últimas selecciones (máx 2)
    return selected[-2:]


def _toggle_metric(selected: List[str], metric: str) -> List[str]:
    if metric in selected:
        selected = [m for m in selected if m != metric]
    else:
        selected = selected + [metric]
    return _coerce_max_two(selected)


def _style_selected_rows(df: pd.DataFrame, selected: List[str]):
    selected_set = set(selected)

    def highlight_row(row: pd.Series):
        if row.name in selected_set:
            return ["background-color: rgba(31, 119, 180, 0.25)"] * len(row)
        return [""] * len(row)

    return df.style.apply(highlight_row, axis=1)


def _clickable_table(
    df_fmt: pd.DataFrame,
    selected: List[str],
    *,
    state_prefix: str,
) -> List[str]:
    """
    Renderiza tabla sin columnas extra y usa la selección de fila de st.dataframe:
    - click en cualquier celda de la fila => selecciona esa fila
    - al detectar una nueva selección => toggle en 'selected'
    """
    # Streamlit devuelve el evento de selección; usamos "rerun" para capturar clics.
    event = st.dataframe(
        _style_selected_rows(df_fmt, selected),
        width="stretch",
        height=420,
        on_select="rerun",
        selection_mode="single-row",
        key=f"{state_prefix}_df",
    )

    # Guardamos el último índice clicado para no togglear en cada rerun
    last_key = f"{state_prefix}_last_clicked"
    if last_key not in st.session_state:
        st.session_state[last_key] = None

    clicked_metric: Optional[str] = None
    try:
        rows: List[int] = list(getattr(event, "selection", {}).get("rows", []))  # type: ignore[attr-defined]
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
    """
    Tabla sin columnas extra donde un click en cualquier celda selecciona la fila.
    UX deseada:
    - Click 1: añade esa métrica a la gráfica
    - Click 2 en otra fila: añade la segunda (máx 2)
    - Click 3 en otra fila: se mantiene máx 2 (sale la más antigua)
    - Click en una ya seleccionada: la quita
    """
    if not AGGRID_OK:
        return selected

    df_grid = df_fmt.reset_index().rename(columns={"index": "Métrica"})
    gb = GridOptionsBuilder.from_dataframe(df_grid)
    # La selección visual del grid será de 1 fila, pero la gráfica puede contener hasta 2 métricas.
    # Esto permite UX "click, click" sin Ctrl.
    gb.configure_selection("single", use_checkbox=False)
    gb.configure_grid_options(
        suppressRowClickSelection=False,
        rowSelection="single",
        headerHeight=34,
        rowHeight=32,
    )
    gb.configure_default_column(
        resizable=True,
        sortable=False,
        filter=False,
        wrapText=False,
    )
    gb.configure_column(
        "Métrica",
        pinned="left",
        width=260,
        cellStyle={"fontWeight": "600"},
    )
    grid_opts = gb.build()

    # Estética: zebra stripes + selección visible (modo claro/blanco+azul)
    if st.session_state.get("theme", "dark") == "light":
        custom_css = {
            ".ag-theme-streamlit": {
                "--ag-background-color": "#ffffff",
                "--ag-foreground-color": "#0f172a",
                "--ag-header-background-color": "rgba(31, 106, 165, 0.10)",
                "--ag-odd-row-background-color": "rgba(15, 23, 42, 0.03)",
                "--ag-row-hover-color": "rgba(31, 106, 165, 0.10)",
                "--ag-selected-row-background-color": "rgba(31, 106, 165, 0.16)",
                "--ag-font-size": "13px",
            }
        }
    else:
        custom_css = {
            ".ag-theme-streamlit": {
                "--ag-header-background-color": "rgba(31, 119, 180, 0.12)",
                "--ag-odd-row-background-color": "rgba(127, 127, 127, 0.06)",
                "--ag-row-hover-color": "rgba(31, 119, 180, 0.08)",
                "--ag-selected-row-background-color": "rgba(31, 119, 180, 0.18)",
                "--ag-font-size": "13px",
            }
        }

    resp = AgGrid(
        df_grid,
        gridOptions=grid_opts,
        # GridUpdateMode está deprecado en algunas versiones
        update_on=["selectionChanged"],
        allow_unsafe_jscode=False,
        fit_columns_on_grid_load=True,
        key=f"{state_prefix}_aggrid",
        height=420,
        theme="streamlit",
        custom_css=custom_css,
    )

    rows_any: Any = resp.get("selected_rows", None)
    metric: Optional[str] = None
    try:
        # Algunas versiones devuelven lista[dict]
        if isinstance(rows_any, list) and len(rows_any) > 0:
            metric = rows_any[0].get("Métrica")
        # Otras devuelven DataFrame
        elif isinstance(rows_any, pd.DataFrame) and not rows_any.empty:
            if "Métrica" in rows_any.columns:
                metric = rows_any.iloc[0].get("Métrica")
    except Exception:
        metric = None

    last_key = f"{state_prefix}_last_clicked"
    if last_key not in st.session_state:
        st.session_state[last_key] = None

    if metric is None:
        return selected

    metric = str(metric)
    # Evitar aplicar el mismo click dos veces por reruns
    if metric == st.session_state[last_key]:
        return selected
    st.session_state[last_key] = metric

    # Toggle + cola de 2 elementos
    if metric in selected:
        selected = [m for m in selected if m != metric]
    else:
        selected = selected + [metric]
        if len(selected) > 2:
            selected = selected[-2:]
    return selected


def main():
    st.set_page_config(page_title="Valoración de Acciones (Web)", layout="wide")
    st.title("Valoración de Acciones (web)")

    # Estado de sesión
    if "last_ticker" not in st.session_state:
        st.session_state.last_ticker = ""
    if "data" not in st.session_state:
        st.session_state.data = None
    if "sel_income" not in st.session_state:
        st.session_state.sel_income = []
    if "sel_balance" not in st.session_state:
        st.session_state.sel_balance = []
    if "sel_cf" not in st.session_state:
        st.session_state.sel_cf = []
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"

    # Toggle modo claro/oscuro (principalmente blanco y azul en claro)
    with st.sidebar:
        modo_claro = st.toggle("Modo claro", value=(st.session_state.theme == "light"))
        st.session_state.theme = "light" if modo_claro else "dark"

    if st.session_state.theme == "light":
        st.markdown(
            """
<style>
  .stApp { background: #ffffff; color: #0f172a; }
  h1, h2, h3, h4 { color: #0f172a; }
  /* acentos azules */
  a, .st-emotion-cache-10trblm, .st-emotion-cache-1dp5vir { color: #1f6aa5; }
  /* contenedores */
  div[data-testid="stVerticalBlockBorderWrapper"] { border-color: rgba(31,106,165,0.25); }
</style>
""",
            unsafe_allow_html=True,
        )

    with st.form("search_form", clear_on_submit=False):
        col1, col2 = st.columns([1, 1])
        with col1:
            ticker = st.text_input("Ticker", value=st.session_state.last_ticker or "AAPL").strip().upper()
        with col2:
            buscar = st.form_submit_button("Buscar")

    if buscar:
        try:
            with st.spinner("Cargando datos (yfinance)..."):
                res_income, res_balance, res_cf = load_all_tables(ticker)
            st.session_state.data = (res_income, res_balance, res_cf)
            st.session_state.last_ticker = ticker
            # Limpiar selecciones (por si el nuevo ticker no tiene esas métricas)
            inc_idx = list(res_income["df_numeric"].index)
            bal_idx = list(res_balance["df_numeric"].index)
            cf_idx = list(res_cf["df_numeric"].index)

            st.session_state.sel_income = [m for m in st.session_state.sel_income if m in inc_idx]
            st.session_state.sel_balance = [m for m in st.session_state.sel_balance if m in bal_idx]
            st.session_state.sel_cf = [m for m in st.session_state.sel_cf if m in cf_idx]

            # Defaults si están vacíos tras limpiar
            if not st.session_state.sel_income:
                st.session_state.sel_income = inc_idx[:2]
            if not st.session_state.sel_balance:
                st.session_state.sel_balance = bal_idx[:2]
            if not st.session_state.sel_cf:
                st.session_state.sel_cf = cf_idx[:2]
        except Exception as e:
            st.error(f"No se pudo cargar '{ticker}'. Detalle: {e}")

    if st.session_state.data is None:
        st.info("Introduce un ticker y pulsa 'Buscar'.")
        return
    res_income, res_balance, res_cf = st.session_state.data

    df_income = res_income["df_numeric"]
    df_income_fmt = res_income["df_formatted"]
    df_balance = res_balance["df_numeric"]
    df_balance_fmt = res_balance["df_formatted"]
    df_cf = res_cf["df_numeric"]
    df_cf_fmt = res_cf["df_formatted"]

    tab1, tab2, tab3, tab4 = st.tabs(["Cuenta de resultados", "Balance", "Flujos de caja", "Valoración"])

    with tab1:
        st.subheader("Tabla")
        if AGGRID_OK:
            st.session_state.sel_income = _aggrid_table_click_any_cell(
                df_income_fmt,
                st.session_state.sel_income,
                state_prefix="income",
            )
        else:
            st.session_state.sel_income = _clickable_table(
                df_income_fmt,
                st.session_state.sel_income,
                state_prefix="income",
            )
        metrics = st.session_state.sel_income
        if metrics:
            fig = _plot_grouped_bars(df_income, metrics, title="Cuenta de resultados")
            st.plotly_chart(fig, width="stretch")

    with tab2:
        st.subheader("Tabla")
        if AGGRID_OK:
            st.session_state.sel_balance = _aggrid_table_click_any_cell(
                df_balance_fmt,
                st.session_state.sel_balance,
                state_prefix="balance",
            )
        else:
            st.session_state.sel_balance = _clickable_table(
                df_balance_fmt,
                st.session_state.sel_balance,
                state_prefix="balance",
            )
        metrics = st.session_state.sel_balance
        if metrics:
            fig = _plot_grouped_bars(df_balance, metrics, title="Balance")
            st.plotly_chart(fig, width="stretch")

    with tab3:
        st.subheader("Tabla")
        if AGGRID_OK:
            st.session_state.sel_cf = _aggrid_table_click_any_cell(
                df_cf_fmt,
                st.session_state.sel_cf,
                state_prefix="cf",
            )
        else:
            st.session_state.sel_cf = _clickable_table(
                df_cf_fmt,
                st.session_state.sel_cf,
                state_prefix="cf",
            )
        metrics = st.session_state.sel_cf
        if metrics:
            fig = _plot_grouped_bars(df_cf, metrics, title="Flujos de caja")
            st.plotly_chart(fig, width="stretch")

    with tab4:
        st.subheader("Valoración por PER (escenarios)")

        # EPS actual: usamos el más reciente del backend
        eps_series = res_income.get("eps_series")
        eps_actual = None
        try:
            if eps_series is not None and len(eps_series) > 0:
                eps_actual = float(pd.Series(eps_series).sort_index(ascending=False).iloc[0])
        except Exception:
            eps_actual = None

        # Gráfico: EPS (barras), PER (línea), Net Margin (línea) últimos 4 años
        try:
            years_all = list(df_income.columns)
            years_4 = years_all[:4]
        except Exception:
            years_4 = []

        eps_by_year: dict[str, float] = {}
        try:
            if eps_series is not None:
                s = pd.Series(eps_series).sort_index(ascending=False).iloc[:4]
                # s.index puede ser int/datetime; lo convertimos a YYYY
                for idx, v in s.items():
                    y = str(getattr(idx, "year", None) or str(idx)[:4])[:4]
                    eps_by_year[y] = float(v)
        except Exception:
            eps_by_year = {}

        eps_vals_4: List[float] = []
        for y in years_4:
            try:
                eps_vals_4.append(float(eps_by_year.get(str(y), 0.0)))
            except Exception:
                eps_vals_4.append(0.0)

        # PER por año usando precio fin de año / EPS anual
        per_vals_4: List[Optional[float]] = []
        if years_4 and eps_by_year:
            per_vals_4 = per_last_4_years_from_eps(st.session_state.last_ticker, years_4, eps_by_year)
        else:
            per_vals_4 = [None] * len(years_4)

        # Net margin (%)
        net_margin_vals_4: List[Optional[float]] = []
        try:
            if "Net Margin (%)" in df_income.index:
                for y in years_4:
                    v = df_income.loc["Net Margin (%)", y]
                    net_margin_vals_4.append(None if pd.isna(v) else float(v))
            else:
                net_margin_vals_4 = [None] * len(years_4)
        except Exception:
            net_margin_vals_4 = [None] * len(years_4)

        if years_4:
            fig_val = make_subplots(specs=[[{"secondary_y": True}]])
            fig_val.add_trace(
                go.Bar(name="EPS", x=years_4, y=eps_vals_4, marker_color="#1f77b4"),
                secondary_y=False,
            )
            fig_val.add_trace(
                go.Scatter(
                    name="PER",
                    x=years_4,
                    y=[p if p is not None else None for p in per_vals_4],
                    mode="lines+markers",
                    line=dict(color="#ff7f0e", width=2),
                ),
                secondary_y=True,
            )
            fig_val.add_trace(
                go.Scatter(
                    name="Margen neto (%)",
                    x=years_4,
                    y=[m if m is not None else None for m in net_margin_vals_4],
                    mode="lines+markers",
                    line=dict(color="#2ca02c", width=2, dash="dot"),
                ),
                secondary_y=True,
            )
            fig_val.update_layout(
                title="EPS, PER y margen neto (últimos 4 años)",
                template="plotly_dark" if st.session_state.theme == "dark" else "plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=40, r=20, t=60, b=40),
            )
            fig_val.update_xaxes(title_text="Año")
            fig_val.update_yaxes(title_text="EPS ($)", secondary_y=False)
            fig_val.update_yaxes(title_text="PER / Margen (%)", secondary_y=True)
            st.plotly_chart(fig_val, width="stretch")

        if eps_actual is None:
            st.warning("No se pudo obtener el EPS actual para la valoración por PER.")
        else:
            with st.form("per_form", clear_on_submit=False):
                c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                with c1:
                    tasa_desc = st.number_input("Tasa descuento (%)", min_value=0.0, max_value=50.0, value=10.0, step=0.5)
                with c2:
                    crec_cons = st.number_input("Crec. conservador (%)", min_value=-50.0, max_value=50.0, value=5.0, step=0.5)
                    per_cons = st.number_input("PER conservador", min_value=0.0, max_value=100.0, value=15.0, step=1.0)
                with c3:
                    crec_real = st.number_input("Crec. realista (%)", min_value=-50.0, max_value=50.0, value=10.0, step=0.5)
                    per_real = st.number_input("PER realista", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
                with c4:
                    crec_opt = st.number_input("Crec. optimista (%)", min_value=-50.0, max_value=50.0, value=15.0, step=0.5)
                    per_opt = st.number_input("PER optimista", min_value=0.0, max_value=100.0, value=25.0, step=1.0)

                calcular_per = st.form_submit_button("Calcular precios")

            if calcular_per:
                r = tasa_desc / 100.0
                v_cons = per_valuation_intrinsic_value(eps_actual, crec_cons / 100.0, per_cons, r)
                v_real = per_valuation_intrinsic_value(eps_actual, crec_real / 100.0, per_real, r)
                v_opt = per_valuation_intrinsic_value(eps_actual, crec_opt / 100.0, per_opt, r)

                # Precio actual (para colorear resultados)
                price = None
                try:
                    info = res_income.get("info") or {}
                    price = info.get("currentPrice") or info.get("regularMarketPrice")
                    price = float(price) if price is not None else None
                except Exception:
                    price = None

                def colored_value(label: str, v: float):
                    if price is None:
                        st.metric(label, f"${v:.2f}")
                        return
                    barato = price < v
                    color = "#22c55e" if barato else "#ef4444"
                    status = "barato" if barato else "caro"
                    st.markdown(
                        f"""
<div style="line-height: 1.1;">
  <div style="font-weight: 700; margin-bottom: 6px;">{label}</div>
  <div>
    <span style="color:{color}; font-size: 1.6rem; font-weight: 800;">${v:.2f}</span>
    <span style="color:{color}; margin-left: 8px;">(vs ${price:.2f} → {status})</span>
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )

                c1, c2, c3 = st.columns(3)
                with c1:
                    colored_value("Conservador", v_cons)
                with c2:
                    colored_value("Realista", v_real)
                with c3:
                    colored_value("Optimista", v_opt)

        st.divider()
        st.subheader("Descuento de Dividendos (Gordon Growth)")

        d0 = get_dividend_last_full_year_from_income_table(df_income)
        if d0 is None:
            st.warning("No hay 'Dividendo Anual' suficiente para valorar por DDM.")
        else:
            fig_div = _dividend_growth_chart(df_income)
            if fig_div is not None:
                st.plotly_chart(fig_div, width="stretch")

            with st.form("ddm_form", clear_on_submit=False):
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    st.write(f"Dividendo anual base (D0): **${d0:.2f}**")
                with c2:
                    g = st.number_input("Crecimiento dividendo (%)", min_value=-50.0, max_value=50.0, value=5.0, step=0.5)
                with c3:
                    r = st.number_input("Tasa descuento DDM (%)", min_value=0.0, max_value=50.0, value=10.0, step=0.5)
                calcular_ddm = st.form_submit_button("Calcular DDM")

            if calcular_ddm:
                if r <= g:
                    st.error("La tasa de descuento debe ser mayor que el crecimiento esperado.")
                else:
                    valor = ddm_gordon_value(d0, g / 100.0, r / 100.0)
                    # Precio actual (para verde/rojo)
                    price = None
                    try:
                        info = res_income.get("info") or {}
                        price = info.get("currentPrice") or info.get("regularMarketPrice")
                        price = float(price) if price is not None else None
                    except Exception:
                        price = None

                    if price is None:
                        st.metric("Valor intrínseco (DDM)", f"${valor:.2f}")
                    else:
                        barato = price < valor
                        color = "#22c55e" if barato else "#ef4444"
                        status = "barato" if barato else "caro"
                        st.markdown(
                            f"""
<div style="line-height: 1.1;">
  <div style="font-weight: 700; margin-bottom: 6px;">Valor intrínseco (DDM)</div>
  <div>
    <span style="color:{color}; font-size: 1.6rem; font-weight: 800;">${valor:.2f}</span>
    <span style="color:{color}; margin-left: 8px;">(vs ${price:.2f} → {status})</span>
  </div>
</div>
""",
                            unsafe_allow_html=True,
                        )


if __name__ == "__main__":
    main()

