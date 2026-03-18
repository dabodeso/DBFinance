from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf


def _year_from_col(col: Any) -> Optional[int]:
    try:
        y = getattr(col, "year", None)
        if y is not None:
            return int(y)
    except Exception:
        pass
    try:
        s = str(col)
        return int(s[:4])
    except Exception:
        return None


def format_currency_compact(val: Any) -> str:
    if pd.isna(val):
        return "N/A"
    try:
        v = float(val)
    except Exception:
        return "N/A"

    if abs(v) >= 1e9:
        return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.2f}K"
    return f"${v:.2f}"


def format_percent_1dp(val: Any) -> str:
    if pd.isna(val):
        return "N/A"
    try:
        return f"{float(val):.1f}%"
    except Exception:
        return "N/A"


def format_shares_compact(val: Any) -> str:
    if pd.isna(val):
        return "N/A"
    try:
        v = float(val)
    except Exception:
        return "N/A"

    if abs(v) >= 1e9:
        return f"{v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{v/1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"{v/1e3:.2f}K"
    return f"{v:,.0f}"


def extract_eps(income_stmt: pd.DataFrame, ticker_obj: yf.Ticker) -> Optional[pd.Series]:
    posibles_nombres = [
        "Diluted EPS",
        "Basic EPS",
        "Diluted Earnings Per Share",
        "Basic Earnings Per Share",
        "Earnings Per Share",
        "EPS - Earnings Per Share",
    ]
    for nombre in posibles_nombres:
        if nombre in income_stmt.index:
            return income_stmt.loc[nombre].dropna()

    # Fallback: earnings
    try:
        earnings = ticker_obj.earnings
        if earnings is not None and not earnings.empty and "Earnings" in earnings.columns:
            return earnings["Earnings"].dropna()
    except Exception:
        pass

    try:
        earn = ticker_obj.get_earnings(freq="yearly")
        if earn is not None and not earn.empty:
            if "Earnings" in earn.columns:
                return earn["Earnings"].dropna()
            if len(earn.columns) > 0:
                return earn.iloc[:, 0].dropna()
    except Exception:
        pass

    return None


def _format_financials_table(
    df_numeric: pd.DataFrame,
) -> pd.DataFrame:
    df_fmt = df_numeric.astype(object).copy()
    for idx in df_numeric.index:
        for col in df_numeric.columns:
            val = df_numeric.loc[idx, col]
            if idx == "Shares Outstanding":
                df_fmt.loc[idx, col] = format_shares_compact(val)
            elif str(idx).endswith("(%)") or str(idx).endswith(" (%)"):
                df_fmt.loc[idx, col] = format_percent_1dp(val)
            else:
                df_fmt.loc[idx, col] = format_currency_compact(val)
    return df_fmt


def compute_dividendo_anual_alineado(ticker_obj: yf.Ticker, income_cols: List[Any]) -> Optional[pd.Series]:
    try:
        dividends = ticker_obj.dividends
        if dividends is None or dividends.empty:
            return None
        div_anual = dividends.groupby(dividends.index.year).sum()
        if div_anual.empty:
            return None

        div_vals: List[Any] = []
        for col in income_cols:
            y = _year_from_col(col)
            div_vals.append(div_anual.get(y, pd.NA))
        return pd.Series(div_vals, index=income_cols)
    except Exception:
        return None


def build_account_income_table(
    ticker: str,
) -> Dict[str, Any]:
    """
    Devuelve:
      - df_numeric: tabla para "Cuenta de resultados" (valores numéricos)
      - df_formatted: tabla para mostrar (strings formateados)
      - eps_series: serie de EPS (para valoración)
      - years: lista de columnas (string)
    """
    ticker_obj = yf.Ticker(ticker)
    info = ticker_obj.info  # puede estar vacío si el ticker no existe
    if not info:
        raise ValueError("Ticker no encontrado o sin datos.")

    income_stmt = ticker_obj.income_stmt
    if income_stmt is None or income_stmt.empty:
        raise ValueError("No se encontraron estados financieros (income statement).")

    n_cols = len(income_stmt.columns)
    if n_cols < 2:
        raise ValueError("Datos insuficientes en income statement.")

    income_stmt = income_stmt.iloc[:, : min(5, n_cols)]

    eps_series = extract_eps(income_stmt, ticker_obj)
    if eps_series is None or len(eps_series) < 2:
        raise ValueError("EPS insuficiente para el análisis.")

    metricas_income = {
        "Total Revenue": ["Total Revenue", "Operating Revenue", "Revenue", "Gross Revenue"],
        "Cost of Revenue": ["Cost of Revenue", "Cost Of Revenue", "Cost of Goods Sold"],
        "Gross Profit": ["Gross Profit"],
        "Operating Expenses": ["Operating Expense", "Operating Expenses"],
        "R&D": ["Research And Development", "Research And Development Expense"],
        "SG&A": ["Selling General And Administration", "Selling And Marketing Expense"],
        "EBITDA": ["EBITDA", "Normalized EBITDA"],
        "EBIT": ["EBIT", "Operating Income", "Earnings Before Interest And Taxes"],
        "Interest Expense": ["Interest Expense", "Net Interest Income"],
        "Income Before Tax": ["Income Before Tax", "Pretax Income"],
        "Net Income": [
            "Net Income",
            "Net Income Common Stockholders",
            "Net Income Including Noncontrolling Interests",
        ],
        "Basic EPS": ["Basic EPS", "Basic Earnings Per Share"],
        "Diluted EPS": ["Diluted EPS", "Diluted Earnings Per Share"],
    }

    datos: Dict[str, pd.Series] = {}
    for nombre_esp, posibles in metricas_income.items():
        valor = None
        for p in posibles:
            if p in income_stmt.index:
                valor = income_stmt.loc[p]
                break
        if valor is not None:
            datos[nombre_esp] = valor

    # Shares Outstanding desde balance_sheet
    try:
        bs = ticker_obj.balance_sheet
        if bs is not None and not bs.empty:
            metricas_shares = ["Share Issued", "Ordinary Shares Number", "Common Stock Shares Outstanding"]
            for nombre in metricas_shares:
                if nombre in bs.index:
                    shares_series = bs.loc[nombre].dropna()
                    if not shares_series.empty:
                        shares_aligned = shares_series.reindex(income_stmt.columns)
                        datos["Shares Outstanding"] = shares_aligned
                        break
    except Exception:
        pass

    # EBITDA fallback
    try:
        if "EBITDA" not in datos or (datos["EBITDA"].isna().all()):
            for name in ["EBIT", "Operating Income", "Earnings Before Interest And Taxes"]:
                if name in income_stmt.index:
                    ebit = income_stmt.loc[name]
                    break
            else:
                ebit = None

            if ebit is not None:
                cf = ticker_obj.cashflow
                if cf is not None and not cf.empty:
                    da_names = [
                        "Depreciation And Amortization",
                        "Depreciation & Amortization",
                        "Depreciation",
                    ]
                    da = None
                    for dn in da_names:
                        if dn in cf.index:
                            da = cf.loc[dn]
                            break
                    if da is not None:
                        datos["EBITDA"] = ebit.add(da, fill_value=0)
    except Exception:
        pass

    # Dividendo anual alineado con los años del income statement
    div_anual = compute_dividendo_anual_alineado(ticker_obj, list(income_stmt.columns))
    if div_anual is not None and not div_anual.empty:
        datos["Dividendo Anual"] = div_anual

    # Márgenes (%)
    try:
        if "Total Revenue" in datos:
            ingresos = datos["Total Revenue"].astype(float)
            eps = 1e-9
            if "Gross Profit" in datos:
                gp = datos["Gross Profit"].astype(float)
                datos["Gross Margin (%)"] = (gp / (ingresos.replace(0, eps))) * 100
            if "EBIT" in datos:
                ebit = datos["EBIT"].astype(float)
                datos["Operating Margin (%)"] = (ebit / (ingresos.replace(0, eps))) * 100
            if "Net Income" in datos:
                ni = datos["Net Income"].astype(float)
                datos["Net Margin (%)"] = (ni / (ingresos.replace(0, eps))) * 100
    except Exception:
        pass

    if not datos:
        raise ValueError("No se encontraron métricas para la cuenta de resultados.")

    df_numeric = pd.DataFrame(datos).T

    orden_preferido = [
        "Total Revenue",
        "Cost of Revenue",
        "Gross Profit",
        "Gross Margin (%)",
        "Operating Expenses",
        "R&D",
        "SG&A",
        "EBITDA",
        "EBIT",
        "Operating Margin (%)",
        "Interest Expense",
        "Income Before Tax",
        "Net Income",
        "Net Margin (%)",
        "Basic EPS",
        "Diluted EPS",
        "Dividendo Anual",
        "Shares Outstanding",
    ]
    existentes = [m for m in orden_preferido if m in df_numeric.index]
    resto = [m for m in df_numeric.index if m not in existentes]
    df_numeric = df_numeric.loc[existentes + resto]

    # Compactar columnas a años (str "YYYY")
    df_numeric.columns = [str(_year_from_col(c) or c)[:4] for c in df_numeric.columns]

    df_formatted = _format_financials_table(df_numeric)
    years = list(df_numeric.columns)

    return {
        "df_numeric": df_numeric,
        "df_formatted": df_formatted,
        "eps_series": eps_series,
        "years": years,
        "info": info,
    }


def build_balance_table(ticker: str) -> Dict[str, Any]:
    ticker_obj = yf.Ticker(ticker)
    info = ticker_obj.info
    if not info:
        raise ValueError("Ticker no encontrado o sin datos.")

    bs = ticker_obj.balance_sheet
    if bs is None or bs.empty:
        raise ValueError("No se encontraron datos de balance (balance_sheet).")

    n_cols = len(bs.columns)
    bs = bs.iloc[:, : min(5, n_cols)]

    metricas_balance = {
        # Activos corrientes
        "Total Current Assets": ["Total Current Assets"],
        "Cash And Cash Equivalents": [
            "Cash And Cash Equivalents",
            "Cash And Short Term Investments",
            "Cash",
        ],
        "Short Term Investments": ["Short Term Investments"],
        "Accounts Receivable": ["Net Receivables", "Accounts Receivable"],
        "Inventory": ["Inventory"],
        "Other Current Assets": ["Other Current Assets"],
        # Activos no corrientes
        "Property Plant Equipment": [
            "Property Plant Equipment",
            "Net Property Plant And Equipment",
            "Property Plant And Equipment",
        ],
        "Goodwill": ["Goodwill"],
        "Intangible Assets": ["Intangible Assets"],
        "Long Term Investments": ["Long Term Investments"],
        "Other Non Current Assets": ["Other Non Current Assets", "Other Assets"],
        # Totales de activos
        "Total Assets": ["Total Assets"],
        # Pasivos corrientes
        "Total Current Liabilities": ["Total Current Liabilities"],
        "Accounts Payable": ["Accounts Payable"],
        "Short Term Debt": ["Short Long Term Debt", "Short Term Debt"],
        "Other Current Liabilities": ["Other Current Liabilities"],
        # Pasivos no corrientes
        "Long Term Debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
        "Other Non Current Liabilities": ["Other Non Current Liabilities"],
        # Totales pasivo y equity
        "Total Liabilities": ["Total Liab", "Total Liabilities"],
        "Total Debt": [],  # calculado luego
        "Total Equity": ["Total Stockholder Equity", "Total Equity"],
    }

    datos: Dict[str, pd.Series] = {}
    for nombre_esp, posibles in metricas_balance.items():
        if not posibles:
            continue
        valor = None
        for p in posibles:
            if p in bs.index:
                valor = bs.loc[p]
                break
        if valor is not None:
            datos[nombre_esp] = valor

    # Total Debt = Short Term Debt + Long Term Debt cuando existan
    try:
        s = datos.get("Short Term Debt", None)
        l = datos.get("Long Term Debt", None)
        if s is not None or l is not None:
            datos["Total Debt"] = (s if s is not None else 0) + (l if l is not None else 0)
    except Exception:
        pass

    if not datos:
        raise ValueError("No se encontraron métricas de balance.")

    df_numeric = pd.DataFrame(datos).T
    df_numeric.columns = [str(_year_from_col(c) or c)[:4] for c in df_numeric.columns]

    df_formatted = df_numeric.astype(object).copy()
    for idx in df_formatted.index:
        for col in df_formatted.columns:
            df_formatted.loc[idx, col] = format_currency_compact(df_numeric.loc[idx, col])

    orden_balance = [
        "Total Current Assets",
        "Cash And Cash Equivalents",
        "Short Term Investments",
        "Accounts Receivable",
        "Inventory",
        "Other Current Assets",
        "Property Plant Equipment",
        "Goodwill",
        "Intangible Assets",
        "Long Term Investments",
        "Other Non Current Assets",
        "Total Assets",
        "Total Current Liabilities",
        "Accounts Payable",
        "Short Term Debt",
        "Other Current Liabilities",
        "Long Term Debt",
        "Other Non Current Liabilities",
        "Total Liabilities",
        "Total Debt",
        "Total Equity",
    ]
    existentes = [m for m in orden_balance if m in df_numeric.index]
    resto = [m for m in df_numeric.index if m not in existentes]
    df_numeric = df_numeric.loc[existentes + resto]
    df_formatted = df_formatted.loc[existentes + resto]

    return {
        "df_numeric": df_numeric,
        "df_formatted": df_formatted,
        "years": list(df_numeric.columns),
        "info": info,
    }


def build_cashflow_table(ticker: str) -> Dict[str, Any]:
    ticker_obj = yf.Ticker(ticker)
    info = ticker_obj.info
    if not info:
        raise ValueError("Ticker no encontrado o sin datos.")

    cf = ticker_obj.cashflow
    if cf is None or cf.empty:
        raise ValueError("No se encontraron datos de cashflow (cashflow).")

    n_cols = len(cf.columns)
    cf = cf.iloc[:, : min(5, n_cols)]

    metricas_cf = {
        # Operaciones
        "Cash From Operating Activities": [
            "Total Cash From Operating Activities",
            "Operating Cash Flow",
        ],
        "Depreciation & Amortization (CF)": [
            "Depreciation",
            "Depreciation And Amortization",
        ],
        # Inversión
        "Capital Expenditures": [
            "Capital Expenditures",
            "Capital Expenditure",
        ],
        "Acquisitions": [
            "Acquisitions Net",
            "Acquisition Of Business",
        ],
        "Other Investing Cash Flow": [
            "Other Investing Cash Flow Items",
            "Other Cashflows From Investing Activities",
        ],
        # Financiación
        "Interest Paid": [
            "Interest Paid",
            "Cash Paid for Interest",
        ],
        "Dividends Paid": [
            "Dividends Paid",
            "Cash Dividends Paid",
        ],
        "Share Repurchases": [
            "Repurchase Of Stock",
            "Common Stock Repurchased",
        ],
        "Share Issuance": [
            "Issuance Of Stock",
            "Proceeds From Issuance Of Common Stock",
        ],
        "Net Borrowings": [
            "Net Borrowings",
            "Net Borrowings Long Term Debt",
        ],
        "Other Financing Cash Flow": [
            "Other Cashflows From Financing Activities",
            "Other Financing Cash Flow Items",
        ],
        # Totales
        "Free Cash Flow": ["Free Cash Flow"],
        "Net Income (Cashflow)": ["Net Income"],
    }

    datos: Dict[str, pd.Series] = {}
    for nombre_esp, posibles in metricas_cf.items():
        valor = None
        for p in posibles:
            if p in cf.index:
                valor = cf.loc[p]
                break
        if valor is not None:
            datos[nombre_esp] = valor

    if not datos:
        raise ValueError("No se encontraron métricas de cashflow.")

    df_numeric = pd.DataFrame(datos).T
    df_numeric.columns = [str(_year_from_col(c) or c)[:4] for c in df_numeric.columns]

    df_formatted = df_numeric.astype(object).copy()
    for idx in df_formatted.index:
        for col in df_formatted.columns:
            df_formatted.loc[idx, col] = format_currency_compact(df_numeric.loc[idx, col])

    orden_cf = [
        "Cash From Operating Activities",
        "Depreciation & Amortization (CF)",
        "Capital Expenditures",
        "Acquisitions",
        "Other Investing Cash Flow",
        "Interest Paid",
        "Dividends Paid",
        "Share Repurchases",
        "Share Issuance",
        "Net Borrowings",
        "Other Financing Cash Flow",
        "Free Cash Flow",
        "Net Income (Cashflow)",
    ]
    existentes = [m for m in orden_cf if m in df_numeric.index]
    resto = [m for m in df_numeric.index if m not in existentes]
    df_numeric = df_numeric.loc[existentes + resto]
    df_formatted = df_formatted.loc[existentes + resto]

    return {
        "df_numeric": df_numeric,
        "df_formatted": df_formatted,
        "years": list(df_numeric.columns),
        "info": info,
    }

