from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Import local backend
HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
from valoracion_backend import (  # noqa: E402
    build_account_income_table,
    build_balance_table,
    build_cashflow_table,
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

    fig.update_layout(
        title=title,
        barmode="group" if len(metrics) == 2 else "relative",
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        xaxis_title="Año",
        yaxis_title="Valor",
    )
    return fig


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_all_tables(ticker: str):
    res_income = build_account_income_table(ticker)
    res_balance = build_balance_table(ticker)
    res_cf = build_cashflow_table(ticker)
    return res_income, res_balance, res_cf


def main():
    st.set_page_config(page_title="Valoración de Acciones (Web)", layout="wide")
    st.title("Valoración de Acciones (web)")

    col1, col2 = st.columns([1, 1])
    with col1:
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
    with col2:
        buscar = st.button("Buscar")

    if not buscar:
        st.info("Introduce un ticker y pulsa 'Buscar'.")
        return

    try:
        with st.spinner("Cargando datos (yfinance)..."):
            res_income, res_balance, res_cf = load_all_tables(ticker)
    except Exception as e:
        st.error(f"No se pudo cargar '{ticker}'. Detalle: {e}")
        return

    df_income = res_income["df_numeric"]
    df_income_fmt = res_income["df_formatted"]
    df_balance = res_balance["df_numeric"]
    df_balance_fmt = res_balance["df_formatted"]
    df_cf = res_cf["df_numeric"]
    df_cf_fmt = res_cf["df_formatted"]

    tab1, tab2, tab3 = st.tabs(["Cuenta de resultados", "Balance", "Flujos de caja"])

    with tab1:
        st.subheader("Tabla")
        st.dataframe(df_income_fmt, use_container_width=True, height=420)

        st.subheader("Selecciona métricas para graficar")
        metrics = st.multiselect(
            "Métricas (1-2)",
            options=df_income.index.tolist(),
            default=df_income.index.tolist()[:2],
        )
        metrics = metrics[:2]
        if metrics:
            fig = _plot_grouped_bars(df_income, metrics, title="Cuenta de resultados")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Tabla")
        st.dataframe(df_balance_fmt, use_container_width=True, height=420)

        st.subheader("Selecciona métricas para graficar")
        metrics = st.multiselect(
            "Métricas (1-2)",
            options=df_balance.index.tolist(),
            default=df_balance.index.tolist()[:2],
        )
        metrics = metrics[:2]
        if metrics:
            fig = _plot_grouped_bars(df_balance, metrics, title="Balance")
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Tabla")
        st.dataframe(df_cf_fmt, use_container_width=True, height=420)

        st.subheader("Selecciona métricas para graficar")
        metrics = st.multiselect(
            "Métricas (1-2)",
            options=df_cf.index.tolist(),
            default=df_cf.index.tolist()[:2],
        )
        metrics = metrics[:2]
        if metrics:
            fig = _plot_grouped_bars(df_cf, metrics, title="Flujos de caja")
            st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()

