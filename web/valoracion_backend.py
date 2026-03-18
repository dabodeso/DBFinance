from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from fmp_client import (
    FMPError,
    balance_sheet,
    cash_flow,
    dividends as fmp_dividends,
    get_api_key,
    historical_price_eod_full,
    income_statement,
    profile as fmp_profile,
    quote as fmp_quote,
)


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


def _year_from_date_str(s: Any) -> Optional[str]:
    try:
        return str(s)[:4]
    except Exception:
        return None


def _records_to_year_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    records: lista de dicts (cada dict es un periodo) con campos como date/calendarYear.
    Devuelve DataFrame index=campos, columns=años (YYYY) en orden más reciente -> antiguo.
    """
    if not records:
        return pd.DataFrame()
    # ordenar por date desc si existe
    def _key(rec):
        return str(rec.get("date") or rec.get("calendarYear") or "")

    recs = sorted(records, key=_key, reverse=True)
    years: List[str] = []
    for r in recs:
        y = r.get("calendarYear") or _year_from_date_str(r.get("date"))
        if y is None:
            continue
        years.append(str(y))
    # construir tabla por keys numéricas
    keys = set()
    for r in recs:
        keys.update(r.keys())
    # eliminar metadatos
    for k in ["symbol", "reportedCurrency", "cik", "fillingDate", "acceptedDate", "period", "link", "finalLink"]:
        keys.discard(k)
    # mantener date/calendarYear para no mezclarlos con métricas
    keys.discard("date")
    keys.discard("calendarYear")

    data: Dict[str, List[Any]] = {}
    for k in sorted(keys):
        row: List[Any] = []
        for r in recs:
            row.append(r.get(k, pd.NA))
        data[k] = row
    df = pd.DataFrame(data, index=years).T
    # columns: years in recs order (may repeat if missing); keep first 5 unique
    # normalize duplicate columns by grouping first occurrence
    df = df.loc[:, ~df.columns.duplicated()]
    return df


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


def compute_dividendo_anual_fmp(api_key: str, symbol: str) -> Optional[pd.Series]:
    try:
        divs = fmp_dividends(symbol, api_key=api_key)
        if not divs:
            return None
        df = pd.DataFrame(divs)
        if "date" not in df.columns:
            return None
        # algunos campos: dividend/adjDividend
        amount_col = "dividend" if "dividend" in df.columns else ("adjDividend" if "adjDividend" in df.columns else None)
        if amount_col is None:
            return None
        df["year"] = df["date"].astype(str).str.slice(0, 4)
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")
        anual = df.groupby("year")[amount_col].sum().sort_index(ascending=False)
        # intentar excluir año actual si parece parcial: si estamos en ese año, quítalo
        try:
            from datetime import datetime

            cur = str(datetime.utcnow().year)
            if cur in anual.index and len(anual.index) > 1:
                anual = anual.drop(index=cur)
        except Exception:
            pass
        return anual.iloc[:5]
    except Exception:
        return None


def build_account_income_table(
    ticker: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Devuelve:
      - df_numeric: tabla para "Cuenta de resultados" (valores numéricos)
      - df_formatted: tabla para mostrar (strings formateados)
      - eps_series: serie de EPS (para valoración)
      - years: lista de columnas (string)
    """
    key = get_api_key(api_key)
    inc_records = income_statement(ticker, api_key=key, limit=5, period="annual")
    if not inc_records:
        raise ValueError("No se encontraron estados financieros (income statement) en FMP.")

    inc_df = _records_to_year_df(inc_records)
    if inc_df.empty:
        raise ValueError("Income statement vacío.")

    # map FMP keys -> etiquetas
    keymap = {
        "Total Revenue": ["revenue"],
        "Cost of Revenue": ["costOfRevenue"],
        "Gross Profit": ["grossProfit"],
        "Total Expenses": ["totalExpenses"],
        "Operating Expenses": ["operatingExpenses"],
        "R&D": ["researchAndDevelopmentExpenses", "researchAndDevelopmentExpense"],
        "SG&A": ["sellingGeneralAndAdministrativeExpenses"],
        "Selling And Marketing": ["sellingAndMarketingExpenses"],
        "General And Administrative": ["generalAndAdministrativeExpenses"],
        "Depreciation & Amortization": ["depreciationAndAmortization"],
        "EBITDA": ["ebitda"],
        "Operating Income": ["operatingIncome"],
        "EBIT": ["ebit"],
        "Interest Expense": ["interestExpense"],
        "Income Before Tax": ["incomeBeforeTax"],
        "Income Tax Expense": ["incomeTaxExpense"],
        "Net Income": ["netIncome"],
        "Basic EPS": ["eps"],
        "Diluted EPS": ["epsdiluted", "epsDiluted"],
        "Shares Outstanding": ["weightedAverageShsOut", "weightedAverageShsOutDil"],
    }

    datos: Dict[str, pd.Series] = {}
    for label, keys in keymap.items():
        for k in keys:
            if k in inc_df.index:
                datos[label] = inc_df.loc[k]
                break

    # Dividendo anual desde endpoint de dividendos (años completos)
    div_anual = compute_dividendo_anual_fmp(key, ticker)
    if div_anual is not None and not div_anual.empty:
        # alinear a columnas del income (años)
        aligned = div_anual.reindex(inc_df.columns)
        datos["Dividendo Anual"] = aligned

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

    # Ratios adicionales
    try:
        if "Income Tax Expense" in datos and "Income Before Tax" in datos:
            tax = datos["Income Tax Expense"].astype(float)
            pretax = datos["Income Before Tax"].astype(float)
            eps = 1e-9
            datos["Effective Tax Rate (%)"] = (tax / (pretax.replace(0, eps))) * 100
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
        "Total Expenses",
        "Operating Expenses",
        "R&D",
        "SG&A",
        "Selling And Marketing",
        "General And Administrative",
        "Depreciation & Amortization",
        "EBITDA",
        "Operating Income",
        "EBIT",
        "Operating Margin (%)",
        "Interest Expense",
        "Income Before Tax",
        "Income Tax Expense",
        "Effective Tax Rate (%)",
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
    df_numeric.columns = [str(c)[:4] for c in df_numeric.columns]

    df_formatted = _format_financials_table(df_numeric)
    years = list(df_numeric.columns)

    # info: quote+profile
    info: Dict[str, Any] = {}
    try:
        info.update(fmp_profile(ticker, api_key=key) or {})
    except Exception:
        pass
    try:
        q = fmp_quote(ticker, api_key=key) or {}
        info["currentPrice"] = q.get("price") or q.get("previousClose") or q.get("open")
    except Exception:
        pass

    return {
        "df_numeric": df_numeric,
        "df_formatted": df_formatted,
        # eps_series: reconstruida desde df_numeric si existe
        "eps_series": df_numeric.loc["Diluted EPS"].dropna() if "Diluted EPS" in df_numeric.index else (df_numeric.loc["Basic EPS"].dropna() if "Basic EPS" in df_numeric.index else None),
        "years": years,
        "info": info,
        "raw": {"income_statement": inc_records},
    }


def build_balance_table(ticker: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    key = get_api_key(api_key)
    bs_records = balance_sheet(ticker, api_key=key, limit=5, period="annual")
    if not bs_records:
        raise ValueError("No se encontraron datos de balance (FMP).")
    bs_df = _records_to_year_df(bs_records)
    if bs_df.empty:
        raise ValueError("Balance vacío.")

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
        "Total Non Current Assets": ["Total Non Current Assets"],
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
        "Total Non Current Liabilities": ["Total Non Current Liabilities"],
        "Long Term Debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
        "Other Non Current Liabilities": ["Other Non Current Liabilities"],
        # Totales pasivo y equity
        "Total Liabilities": ["Total Liab", "Total Liabilities"],
        "Total Debt": [],  # calculado luego
        "Total Equity": ["Total Stockholder Equity", "Total Equity"],
    }

    # map FMP keys -> etiquetas
    keymap = {
        "Total Current Assets": ["totalCurrentAssets"],
        "Cash And Cash Equivalents": ["cashAndCashEquivalents"],
        "Short Term Investments": ["shortTermInvestments"],
        "Accounts Receivable": ["netReceivables", "accountReceivables"],
        "Inventory": ["inventory"],
        "Other Current Assets": ["otherCurrentAssets"],
        "Total Non Current Assets": ["totalNonCurrentAssets"],
        "Property Plant Equipment": ["propertyPlantEquipmentNet"],
        "Goodwill": ["goodwill"],
        "Intangible Assets": ["intangibleAssets"],
        "Long Term Investments": ["longTermInvestments"],
        "Other Non Current Assets": ["otherNonCurrentAssets"],
        "Total Assets": ["totalAssets"],
        "Total Current Liabilities": ["totalCurrentLiabilities"],
        "Accounts Payable": ["accountPayables"],
        "Short Term Debt": ["shortTermDebt"],
        "Other Current Liabilities": ["otherCurrentLiabilities"],
        "Total Non Current Liabilities": ["totalNonCurrentLiabilities"],
        "Long Term Debt": ["longTermDebt"],
        "Other Non Current Liabilities": ["otherNonCurrentLiabilities"],
        "Total Liabilities": ["totalLiabilities"],
        "Total Equity": ["totalStockholdersEquity", "totalEquity"],
    }

    datos: Dict[str, pd.Series] = {}
    for label, keys in keymap.items():
        for k in keys:
            if k in bs_df.index:
                datos[label] = bs_df.loc[k]
                break

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
    df_numeric.columns = [str(c)[:4] for c in df_numeric.columns]

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
        "Total Non Current Assets",
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
        "Total Non Current Liabilities",
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

    info: Dict[str, Any] = {}
    try:
        info.update(fmp_profile(ticker, api_key=key) or {})
    except Exception:
        pass
    try:
        q = fmp_quote(ticker, api_key=key) or {}
        info["currentPrice"] = q.get("price") or q.get("previousClose") or q.get("open")
    except Exception:
        pass

    return {
        "df_numeric": df_numeric,
        "df_formatted": df_formatted,
        "years": list(df_numeric.columns),
        "info": info,
        "raw": {"balance_sheet": bs_records},
    }


def build_cashflow_table(ticker: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    key = get_api_key(api_key)
    cf_records = cash_flow(ticker, api_key=key, limit=5, period="annual")
    if not cf_records:
        raise ValueError("No se encontraron datos de cashflow (FMP).")
    cf_df = _records_to_year_df(cf_records)
    if cf_df.empty:
        raise ValueError("Cashflow vacío.")

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
        "Change in Working Capital": [
            "Change In Working Capital",
            "Change in Working Capital",
        ],
        # Inversión
        "Capital Expenditures": [
            "Capital Expenditures",
            "Capital Expenditure",
        ],
        "Investments": [
            "Investments",
            "Purchase Of Investments",
            "Sale Of Investments",
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
        "Debt Issuance": [
            "Proceeds From Issuance Of Debt",
            "Issuance Of Debt",
        ],
        "Debt Repayment": [
            "Repayment Of Debt",
            "Repayment Of Long Term Debt",
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

    keymap = {
        "Cash From Operating Activities": ["operatingCashFlow"],
        "Depreciation & Amortization (CF)": ["depreciationAndAmortization"],
        "Change in Working Capital": ["changeInWorkingCapital"],
        "Capital Expenditures": ["capitalExpenditure"],
        "Investments": ["purchasesOfInvestments", "salesMaturitiesOfInvestments"],
        "Acquisitions": ["acquisitionsNet"],
        "Other Investing Cash Flow": ["otherInvestingActivites"],
        "Interest Paid": ["interestPaid"],
        "Dividends Paid": ["dividendsPaid"],
        "Share Repurchases": ["commonStockRepurchased"],
        "Share Issuance": ["commonStockIssued"],
        "Debt Issuance": ["debtIssuance"],
        "Debt Repayment": ["debtRepayment"],
        "Net Borrowings": ["netBorrowings"],
        "Other Financing Cash Flow": ["otherFinancingActivites"],
        "Free Cash Flow": ["freeCashFlow"],
        "Net Income (Cashflow)": ["netIncome"],
    }

    datos: Dict[str, pd.Series] = {}
    for label, keys in keymap.items():
        for k in keys:
            if k in cf_df.index:
                datos[label] = cf_df.loc[k]
                break

    if not datos:
        raise ValueError("No se encontraron métricas de cashflow.")

    df_numeric = pd.DataFrame(datos).T
    df_numeric.columns = [str(c)[:4] for c in df_numeric.columns]

    df_formatted = df_numeric.astype(object).copy()
    for idx in df_formatted.index:
        for col in df_formatted.columns:
            df_formatted.loc[idx, col] = format_currency_compact(df_numeric.loc[idx, col])

    orden_cf = [
        "Cash From Operating Activities",
        "Depreciation & Amortization (CF)",
        "Change in Working Capital",
        "Capital Expenditures",
        "Investments",
        "Acquisitions",
        "Other Investing Cash Flow",
        "Interest Paid",
        "Dividends Paid",
        "Share Repurchases",
        "Share Issuance",
        "Debt Issuance",
        "Debt Repayment",
        "Net Borrowings",
        "Other Financing Cash Flow",
        "Free Cash Flow",
        "Net Income (Cashflow)",
    ]
    existentes = [m for m in orden_cf if m in df_numeric.index]
    resto = [m for m in df_numeric.index if m not in existentes]
    df_numeric = df_numeric.loc[existentes + resto]
    df_formatted = df_formatted.loc[existentes + resto]

    info: Dict[str, Any] = {}
    try:
        info.update(fmp_profile(ticker, api_key=key) or {})
    except Exception:
        pass
    try:
        q = fmp_quote(ticker, api_key=key) or {}
        info["currentPrice"] = q.get("price") or q.get("previousClose") or q.get("open")
    except Exception:
        pass

    return {
        "df_numeric": df_numeric,
        "df_formatted": df_formatted,
        "years": list(df_numeric.columns),
        "info": info,
        "raw": {"cash_flow": cf_records},
    }


def eps_growth_cagr(eps_series: pd.Series, years: int) -> Optional[float]:
    """
    CAGR de EPS en % para un número de años, usando la serie (cualquier orden).
    Devuelve porcentaje (ej. 12.3), o None si no hay datos suficientes.
    """
    if eps_series is None or len(eps_series) < years + 1:
        return None
    eps_sorted = eps_series.sort_index(ascending=False)
    vals = eps_sorted.values.astype(float)
    if len(vals) < years + 1:
        return None
    if vals[years] == 0:
        return None
    try:
        return ((vals[0] / vals[years]) ** (1 / years) - 1) * 100
    except Exception:
        return None


def per_valuation_intrinsic_value(
    eps_actual: float,
    crecimiento_anual: float,
    per_futuro: float,
    tasa_descuento: float,
    years: int = 5,
) -> float:
    """
    Valoración por PER proyectando EPS 'years' años y descontando el precio futuro.
    crecimiento_anual y tasa_descuento en formato decimal (ej 0.10).
    """
    eps_futuro = eps_actual * ((1 + crecimiento_anual) ** years)
    precio_futuro = eps_futuro * per_futuro
    valor_presente = precio_futuro / ((1 + tasa_descuento) ** years)
    return float(valor_presente)


def ddm_gordon_value(dividendo_anual: float, crecimiento: float, tasa_descuento: float) -> float:
    """
    Gordon Growth Model (DDM):
      valor = D1 / (r - g), donde D1 = D0 * (1+g)
    crecimiento y tasa_descuento en formato decimal (ej 0.05).
    """
    d1 = float(dividendo_anual) * (1 + crecimiento)
    return float(d1 / (tasa_descuento - crecimiento))


def get_dividend_last_full_year_from_income_table(df_income_numeric: pd.DataFrame) -> Optional[float]:
    """
    Usa la fila 'Dividendo Anual' del income table (años completos) y devuelve el
    más reciente disponible (columna más a la izquierda / primer valor no N/A).
    """
    if df_income_numeric is None or df_income_numeric.empty:
        return None
    if "Dividendo Anual" not in df_income_numeric.index:
        return None
    try:
        serie = df_income_numeric.loc["Dividendo Anual"].dropna()
        if serie.empty:
            return None
        # columnas están como strings "YYYY" ya, orden más reciente primero (por construcción)
        return float(serie.iloc[0])
    except Exception:
        return None


def per_last_4_years_from_eps(
    ticker: str,
    years: List[str],
    eps_by_year: Dict[str, float],
    api_key: Optional[str] = None,
) -> List[Optional[float]]:
    """
    Calcula PER por año usando:
      PER_y = Close(fin de año) / EPS_y
    years: lista de años (string) en el orden deseado para el gráfico (idealmente más reciente -> más antiguo)
    eps_by_year: dict { "YYYY": eps_float }
    """
    per_vals: List[Optional[float]] = []
    key = get_api_key(api_key)
    hist = None
    try:
        hist = historical_price_eod_full(ticker, api_key=key)
    except Exception:
        hist = None

    for y in years:
        try:
            year_int = int(str(y)[:4])
            eps_y = float(eps_by_year.get(str(year_int), float("nan")))
            if eps_y == 0 or pd.isna(eps_y):
                per_vals.append(None)
                continue

            # hist puede ser dict con campo histórico; intentamos formatos comunes
            close = None
            if isinstance(hist, dict):
                series = hist.get("historical") or hist.get("historicalStockList") or hist.get("data")
                if isinstance(series, list):
                    # buscar último día de diciembre o del año
                    dec = [d for d in series if str(d.get("date", "")).startswith(f"{year_int}-12")]
                    cand = dec if dec else [d for d in series if str(d.get("date", "")).startswith(f"{year_int}-")]
                    if cand:
                        # asume que vienen ordenados desc; si no, ordenamos
                        cand = sorted(cand, key=lambda d: str(d.get("date", "")), reverse=True)
                        close = cand[0].get("close")
            if close is None:
                per_vals.append(None)
                continue

            close = float(close)
            per_vals.append(close / eps_y)
        except Exception:
            per_vals.append(None)

    return per_vals


