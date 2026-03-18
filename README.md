# Valoración de Acciones - Análisis Financiero

Aplicación de escritorio para análisis y valoración de acciones utilizando datos de Yahoo Finance.

## Requisitos

- Python 3.8 o superior
- customtkinter
- yfinance
- pandas

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
python app_valoracion.py
```

En Windows, si `python` no está en el PATH:
```bash
py -3 app_valoracion.py
```

## Funcionalidades

### 1. Buscador
- Ingrese el ticker de la acción (ej: AAPL, MSFT, GOOGL)
- La aplicación valida el ticker y carga los datos de Yahoo Finance
- Se requieren al menos 5 años de datos históricos

### 2. Pestaña Estados Financieros
Muestra una tabla con los últimos 5 años de:
- **Ventas (Total Revenue)**
- **Coste de Ventas (Cost of Revenue)**
- **EBITDA** (o calculado como EBIT + Depreciación y Amortización si no está disponible)
- **Ingresos Netos (Net Income)**

### 3. Pestaña Valoración (Modelo de Proyección de EPS)
- **Crecimiento histórico de EPS**: 1, 3 y 5 años (CAGR)
- **Escenarios de proyección**:
  - Conservador, Medio y Optimista
  - Crecimiento anual esperado (%)
  - PER (Ratio Precio/Beneficio) futuro
- **Tasa de descuento**: 10% por defecto
- **Valor intrínseco estimado** para cada escenario (proyección a 5 años, descontado al valor presente)

## Fórmula de Valoración

Para cada escenario:
1. EPS proyectado a 5 años = EPS actual × (1 + crecimiento)^5
2. Precio futuro estimado = EPS proyectado × PER futuro
3. Valor intrínseco = Precio futuro / (1 + tasa descuento)^5

## Notas

- Los tickers deben ser válidos en Yahoo Finance (ej: AAPL para Apple, MSFT para Microsoft)
- Algunas empresas pueden no tener EBITDA reportado directamente; en ese caso se calcula
- La aplicación usa modo oscuro por defecto
