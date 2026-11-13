
import streamlit as st
import pandas as pd
import numpy as np
import urllib.request
import json

st.set_page_config(
    page_title="TIBOT AUTOMATIC",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
.stApp {background-color:#080d0b;color:#e8f5ed}
h1,h2,h3 {color:#20d878 !important}
[data-testid="stMetric"] {
    background:#101a14;
    border:1px solid #1d5735;
    padding:14px;
    border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

MARKETS = {
    "Bitcoin (BTC/USD)": "XBTUSD",
    "Ethereum (ETH/USD)": "ETHUSD"
}

INTERVALS = {
    "15 minutes": 15,
    "1 heure": 60,
    "4 heures": 240,
    "1 jour": 1440
}

def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TIBOT-AUTOMATIC/1.0"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


@st.cache_data(ttl=10)
def get_ticker(pair):
    url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
    data = get_json(url)

    if data.get("error"):
        raise ValueError(", ".join(data["error"]))

    key = next(iter(data["result"]))
    return float(data["result"][key]["c"][0])


@st.cache_data(ttl=10)
def get_market_data(pair, interval):
    url = (
        "https://api.kraken.com/0/public/OHLC"
        f"?pair={pair}&interval={interval}"
    )
    data = get_json(url)

    if data.get("error"):
        raise ValueError(", ".join(data["error"]))

    result = data["result"]
    key = next(k for k in result if k != "last")

    df = pd.DataFrame(
        result[key],
        columns=[
            "time", "open", "high", "low",
            "close", "vwap", "volume", "count"
        ]
    )

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])

    df["time"] = pd.to_datetime(
        pd.to_numeric(df["time"]),
        unit="s",
        utc=True
    ).dt.tz_convert("America/Toronto")

    # Retire la bougie qui peut être encore en formation
    if len(df) > 1:
        df = df.iloc[:-1].copy()

    return df.reset_index(drop=True)


def calculate_indicators(df):
    df = df.copy()

    df["SMA20"] = df["close"].rolling(20).mean()
    df["SMA50"] = df["close"].rolling(50).mean()

    change = df["close"].diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)

    avg_gain = gains.ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()

    avg_loss = losses.ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = (100 - 100 / (1 + rs)).fillna(50)

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()

    df["MACD"] = ema12 - ema26
    df["SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    return df


def analyze(df):
    last = df.iloc[-1]
    observations = []

    if last["close"] > last["SMA20"]:
        observations.append("Cours au-dessus de la moyenne mobile 20.")
    else:
        observations.append("Cours sous la moyenne mobile 20.")

    if last["SMA20"] > last["SMA50"]:
        observations.append("Moyenne 20 au-dessus de la moyenne 50.")
    else:
        observations.append("Moyenne 20 sous la moyenne 50.")

    if last["RSI"] >= 70:
        observations.append("RSI élevé : zone de surachat possible.")
    elif last["RSI"] <= 30:
        observations.append("RSI bas : zone de survente possible.")
    else:
        observations.append("RSI dans une zone intermédiaire.")

    if last["MACD"] > last["SIGNAL"]:
        observations.append("MACD au-dessus de sa ligne de signal.")
    else:
        observations.append("MACD sous sa ligne de signal.")

    bullish = sum([
        last["close"] > last["SMA20"],
        last["SMA20"] > last["SMA50"],
        last["MACD"] > last["SIGNAL"]
    ])

    if bullish == 3 and last["RSI"] < 70:
        status = "PLUSIEURS SIGNAUX HAUSSIERS À ÉTUDIER"
    elif bullish == 0:
        status = "PLUSIEURS SIGNAUX BAISSIERS À ÉTUDIER"
    else:
        status = "SIGNAUX MIXTES — CONFIRMATION NÉCESSAIRE"

    return status, observations


st.title("📈 TIBOT AUTOMATIC")
st.caption("MARKET ANALYSIS TERMINAL • KRAKEN LIVE DATA")

st.success("Surveillance automatique activée • Aucune transaction automatique")

col1, col2 = st.columns(2)

with col1:
    selected_markets = st.multiselect(
        "Marchés à surveiller",
        list(MARKETS.keys()),
        default=list(MARKETS.keys())
    )

with col2:
    selected_interval = st.selectbox(
        "Intervalle du graphique",
        list(INTERVALS.keys()),
        index=1
    )

st.divider()

@st.fragment(run_every="30s")
def live_dashboard():
    st.caption(
        "⟳ Actualisation automatique toutes les 30 secondes"
    )

    for market_name in selected_markets:
        pair = MARKETS[market_name]

        st.subheader(market_name)

        try:
            price = get_ticker(pair)
            raw = get_market_data(
                pair, INTERVALS[selected_interval]
            )
            df = calculate_indicators(raw)

            if len(df) < 60:
                st.warning("Données insuffisantes pour les indicateurs.")
                continue

            last = df.iloc[-1]
            status, observations = analyze(df)

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "PRIX ACTUEL",
                f"${price:,.2f}",
                help="Dernier prix communiqué par Kraken."
            )
            c2.metric("RSI 14", f"{last['RSI']:.1f}")
            c3.metric("MACD", f"{last['MACD']:.2f}")

            st.markdown("#### Graphique du marché")

            chart = df.set_index("time")[
                ["close", "SMA20", "SMA50"]
            ]
            st.line_chart(chart, height=350)

            st.markdown("#### Volume")
            st.bar_chart(
                df.set_index("time")[["volume"]],
                height=150
            )

            st.markdown("#### Analyse de TIBOT")
            st.info(status)

            for item in observations:
                st.write("• " + item)

            st.caption(
                "Dernière bougie clôturée : "
                + str(last["time"])
            )

        except Exception as error:
            st.error(f"Erreur de données : {error}")

        st.divider()


live_dashboard()

st.caption(
    "TIBOT AUTOMATIC • Données publiques Kraken. "
    "Indicateurs éducatifs, pas des recommandations financières."
)
