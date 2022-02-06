from typing import Tuple, Union
from datetime import datetime

import yfinance as yf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


pd.options.mode.chained_assignment = None


def load_history(ticker_symbol: str, month: Union[int, str], year: Union[int, str]) -> pd.DataFrame:
    ticker = yf.Ticker(ticker_symbol)
    history = ticker.history("max")
    history["Month"] = history.index.to_period("M")

    history = history.loc[:, ["Close", "Month"]]

    last_dom = history.index[0] + pd.tseries.offsets.BMonthEnd()
    history = history[history.index > last_dom]

    first_dom = history.index[-1].to_period("M").to_timestamp()
    history = history[history.index < first_dom]

    if (month != "max") and (year != "max"):
        start_date = datetime(int(year), int(month), 1)
        history = history[history.index >= start_date]

    return history


def calc_10month_sma(history: pd.DataFrame) -> pd.DataFrame:
    month_groups = pd.DataFrame(index=history["Month"].unique(), columns=["MonthSum", "MonthCount"])
    month_groups["MonthSum"] = history.groupby("Month")["Close"].sum()
    month_groups["MonthCount"] = history.groupby("Month")["Close"].count()
    sma = month_groups.rolling(10).sum().dropna()
    sma["SMA"] = sma["MonthSum"] / sma["MonthCount"]
    sma.drop(["MonthSum", "MonthCount"], axis=1, inplace=True)
    history.drop(history.index[history.index < sma.index[0].to_timestamp()], inplace=True)
    sma.set_index(history.reset_index().groupby("Month").last()["Date"], inplace=True)
    sma["Close"] = history["Close"]
    sma["In"] = (sma["Close"] > sma["SMA"]).astype(int)
    sma["Buy"] = sma["In"].diff() == 1
    sma["Sell"] = sma["In"].diff() == -1

    return sma


def calc_evolution(history: pd.DataFrame, sma: pd.DataFrame,
                   tax_prc: float, ini_amount: int) -> Tuple[pd.Series, pd.Series, pd.Series]:
    
    history["In"] = sma["In"].diff()
    history["In"] = history["In"].fillna(0)
    first_sell = history[history["In"] == -1].index[0]
    first_buy = history[history["In"] == 1].index[0]
    if first_sell < first_buy:
        history.loc[history.index[0], "In"] = 1
    history["In"] = history["In"].cumsum()
    history["ChangePct"] = history["Close"].pct_change() + 1
    history.loc[history.index[0], "ChangePct"] = 1
    history["ChangePctStrategy"] = history["ChangePct"]
    history.loc[history["In"] != 1, "ChangePctStrategy"] = 1

    bh_evolution = history["ChangePct"].cumprod() * ini_amount

    history["Date"] = history.index
    gain = history.groupby((history["In"] != history["In"].shift()).cumsum())[["In", "ChangePct", "Date"]].agg({
        "In": "prod",
        "ChangePct": ["prod", lambda x: x.iloc[:-1].prod()],
        "Date": "last"
    })
    gain.set_index(gain["Date"]["last"], inplace=True, drop=True)
    change_pct_prod = (gain["ChangePct"]["prod"] - 1) * (1 - (tax_prc / 100)) + 1
    change_pct_prod_but_last = gain["ChangePct"]["<lambda_0>"]
    gain.drop("ChangePct", axis=1, inplace=True)
    gain["ChangePct"] = change_pct_prod / change_pct_prod_but_last
    gain = gain.droplevel(1, axis=1)
    gain.loc[gain["In"] == 0, "ChangePct"] = 1

    history.loc[gain.index, "ChangePctStrategy"] = gain["ChangePct"]

    strategy_evolution = history["ChangePctStrategy"].cumprod() * ini_amount
    
    flat_zones = pd.Series(index=history.index, data=np.nan)
    flat_zones[history["In"] == 0] = strategy_evolution[history["In"] != 1]

    return bh_evolution, strategy_evolution, flat_zones


def plot_signals(symbol: str, history: pd.DataFrame, sma: pd.DataFrame, log: bool):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history.index, y=history["Close"],
                        mode="lines",
                        name="Close price"))
    fig.add_trace(go.Scatter(x=sma.index, y=sma["SMA"],
                        mode="lines",
                        name="10 Months SMA"))
    fig.add_trace(go.Scatter(x=sma[sma["Buy"]].index, y=sma[sma["Buy"]]["SMA"] * 1.2,
                        mode="markers",
                        marker_color="green",
                        marker_symbol="triangle-down",
                        name="Buy signals"))
    fig.add_trace(go.Scatter(x=sma[sma["Sell"]].index, y=sma[sma["Sell"]]["SMA"] * 1.2,
                        mode="markers",
                        marker_color="red",
                        marker_symbol="triangle-down",
                        name="Sell signals"))
    
    if log:
        y_label = "Log Close Price"
    else:
        y_label = "Close Price"
    
    fig.update_layout(title=symbol, xaxis_title="Year", yaxis_title=y_label)
    
    if log:
        fig.update_yaxes(type="log")

    st.plotly_chart(fig)


def plot_evolution(symbol: str, history: pd.DataFrame, bh_evolution: pd.Series,
                   strategy_evolution: pd.Series, flat_zones: pd.Series, log: bool):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history.index, y=bh_evolution,
                        mode="lines",
                        name="Original"))
    fig.add_trace(go.Scatter(x=history.index, y=strategy_evolution,
                        mode="lines",
                        name="Strategy"))
    fig.add_trace(go.Scatter(x=flat_zones.index, y=flat_zones,
                        mode="lines",
                        name="Flat zones"))
    
    if log:
        y_label = "Log Close Price"
    else:
        y_label = "Close Price"
    
    fig.update_layout(title=symbol, xaxis_title="Year", yaxis_title=y_label)
    
    if log:
        fig.update_yaxes(type="log")

    st.plotly_chart(fig)


st.title("Meb Faber Tactical Asset Allocation (TAA)")
st.subheader("Ticker and parameters")

with st.form(key="symbol_form"):
    st.markdown("**Symbol to load**")
    st.write("Specify the exchange using a dot followed by the name of the exchange, e.g., 'IWQU.MI'")
    symbol = st.text_input(label="Enter ticker", value="^GSPC")

    st.markdown("**Starting date**")
    month_col, year_col = st.columns(2)
    month = month_col.selectbox("Month", ["max"] + list(range(1, 13)))
    year = year_col.selectbox("Year", ["max"] + list(range(1900, datetime.today().year + 1)))
    
    st.markdown("**Taxes and costs**")
    # trad_cost = st.number_input(label="Trading cost", value=float(2.95))
    tax_prc = st.number_input(label="Capital gain %", value=float(26))
    ini_amount = st.number_input(label="Initial amount", value=10000)

    log = st.checkbox("Log y-axis", value=True)
    submit_button = st.form_submit_button(label="Run")

if submit_button:

    history = load_history(symbol, month, year)
    sma = calc_10month_sma(history)

    st.subheader("Buy and sell signals")

    plot_signals(symbol, history, sma, log)

    bh_evolution, strategy_evolution, flat_zones = calc_evolution(history, sma, tax_prc, ini_amount)

    st.subheader("Evolution of the strategy")

    plot_evolution(symbol, history, bh_evolution, strategy_evolution, flat_zones, log)

# For debugging purposes
# if __name__ == "__main__":
#     history = load_history("^GSPC", "max", "max")
#     sma = calc_10month_sma(history)
#     bh_evolution, strategy_evolution, flat_zones = calc_evolution(history, sma, 2.95, 26, 10000)