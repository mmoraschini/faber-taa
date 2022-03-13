from typing import Tuple, Union
from datetime import datetime, timedelta
import requests
from io import BytesIO

import yfinance as yf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


pd.options.mode.chained_assignment = None


class TickerNotFoundException(Exception):
    def __init__(self, message):            
        super().__init__(message)
        self.message = message
    
    def __str__(self):
        return self.message


def load_history(ticker_symbol: str, month: Union[int, str], year: Union[int, str]) -> Tuple[yf.Ticker, pd.DataFrame]:
    ticker = yf.Ticker(ticker_symbol)
    history = ticker.history("max")

    if len(history) == 0:
        raise TickerNotFoundException("Ticker " + ticker_symbol + " not found")
    
    history["Month"] = history.index.to_period("M")

    history = history.loc[:, ["Close", "Month"]]

    last_dom = history.index[0] + pd.tseries.offsets.BMonthEnd()
    history = history[history.index > last_dom]

    first_dom = history.index[-1].to_period("M").to_timestamp()
    history = history[history.index < first_dom]

    return ticker, history


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
                        name="Buy and hold"))
    fig.add_trace(go.Scatter(x=history.index, y=strategy_evolution,
                        mode="lines",
                        name="Strategy"))
    fig.add_trace(go.Scatter(x=flat_zones.index, y=flat_zones,
                        mode="lines",
                        name="Out of market periods"))

    if log:
        y_label = "Log Close Price"
    else:
        y_label = "Close Price"
    
    fig.update_layout(title=symbol, xaxis_title="Year", yaxis_title=y_label)
    
    if log:
        fig.update_yaxes(type="log")

    st.plotly_chart(fig)


SYM = None
MONTH = None
YEAR = None

st.title("Meb Faber Tactical Asset Allocation (TAA)")

response = requests.get("https://poweredby.yahoo.com/poweredby_yahoo_h_purple.png")
img = BytesIO(response.content)
st.image(img)

st.markdown("Repo of this project: https://github.com/mmoraschini/faber-taa")
st.write("The information obtained from this script is for instructional purposes only and should be verified before \
using it in any financial strategy. I am not a financial advisor and this project is not meant to give financial advices. \
Please, contact a registered financial advisor if you are interested in investing your money.")

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
    tax_prc = st.number_input(label="Capital gain tax (%)", value=float(26))
    ini_amount = st.number_input(label="Initial amount", value=10000)

    log = st.checkbox("Log y-axis", value=True)
    submit_button = st.form_submit_button(label="Run")

if submit_button:

    try:
        breakpoint()
        if (symbol != SYM) | (month != MONTH) | (year != YEAR):
            ticker, history = load_history(symbol, month, year)
            SYM = symbol
            MONTH = month
            YEAR = year
            sma = calc_10month_sma(history)

        if (month != "max") ^ (year != "max"):
            st.warning("To set a starting date both month and year must be different from 'max'")

        if (month != "max") & (year != "max"):
            start_date = datetime(int(year), int(month), 1)
            history = history[history.index >= start_date]
            sma = sma[sma.index >= start_date]

            if (sma.index[0].month != int(month)) | (sma.index[0].year != int(year)):
                st.warning(f"Requested starting date not available. Starting at {sma.index[0].year}-{sma.index[0].month}-1.")
        

        st.subheader("Info")

        try:
            st.write(f"Description: {ticker.info['longName']}")
        except KeyError:
            st.write(f"Description: not available")
        st.write(f"Exchange: {ticker.info['exchange']}")
        st.write(f"Currency: {ticker.info['currency']}")

        st.subheader("Buy and sell signals")

        plot_signals(symbol, history, sma, log)

        bh_evolution, strategy_evolution, flat_zones = calc_evolution(history, sma, tax_prc, ini_amount)

        st.subheader("Evolution of the strategy")

        plot_evolution(symbol, history, bh_evolution, strategy_evolution, flat_zones, log)

        st.subheader("Performance")

        delta_years = (bh_evolution.index[-1] - bh_evolution.index[0]) / timedelta(days=365)

        stats_df = pd.DataFrame(index=["Buy and hold", "Strategy"], columns=["Final amount", "CAGR", "Standard deviation"])
        stats_df.loc["Buy and hold", "Final amount"] = bh_evolution.iloc[-1]
        stats_df.loc["Strategy", "Final amount"] = strategy_evolution.iloc[-1]
        stats_df.loc["Buy and hold", "CAGR"] = ((bh_evolution.iloc[-1] / bh_evolution.iloc[0]) ** (1 / delta_years) - 1) * 100
        stats_df.loc["Strategy", "CAGR"] = ((strategy_evolution.iloc[-1] / strategy_evolution.iloc[0]) ** (1 / delta_years) - 1) * 100

        st.dataframe(stats_df.style.format("{:,.2f}"))

    except TickerNotFoundException as e:
        st.error(str(e))

# # For debugging purposes
# if __name__ == "__main__":
#     try:
#         ticker, history = load_history("IWQU.MI", 3, 2017)
#         sma = calc_10month_sma(history)
#         bh_evolution, strategy_evolution, flat_zones = calc_evolution(history, sma, 26, 10000)
#     except TickerNotFoundException as e:
#         print(e)