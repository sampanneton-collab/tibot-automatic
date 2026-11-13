
import streamlit as st
import pandas as pd
import numpy as np
import urllib.request
import json
from datetime import datetime

# -----------------------------
# CONFIGURATION
# -----------------------------
st.set_page_config(
    page_title="TIBOT AUTOMATIC",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #080d0b;
    color: #e8f5ed;
}
h1, h2, h3 {
    color: #20d878 !important;
}
[data-testid="stMetric"] {
    background-color: #101a14;
    border: 1px solid #1d5735;
    padding: 14px;
    border-radius: 10px;
}
.stButton button {
    background-color: #126b3b;
    color: white;
    border: none;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# DONNEES PUBLIQUES KRAKEN
# -----------------------------
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


@st.cache_data(ttl=60)
def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TIBOT-AUTOMATIC/1.0"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def get_market_data(pair, interval):
    url = (
        "https://api.kraken.com/0/public/OHLC"
        f"?pair={pair}&interval={interval}"
    )

    data = get_json(url)

    if data.get("error"):
        raise ValueError(", ".join(data["error"]))

    result = data["result"]
    result_key = next(key for key in result if key != "last")
    candles = result[result_key]

    df = pd.DataFrame(
        candles,
        columns=[
            "time", "open", "high", "low",
            "close", "vwap", "volume", "count"
        ]
    )

    for column in [
        "open", "high", "low", "close",
        "vwap", "volume"
    ]:
        df[column] = pd.to_numeric(df[column])

    df["time"] = pd.to_datetime(
        pd.to_numeric(df["time"]),
        unit="s",
        utc=True
    ).dt.tz_convert("America/Toronto")

    # La dernière bougie peut être encore en formation.
    # On l'exclut pour calculer les indicateurs sur des bougies terminées.
    if len(df) > 1:
        df = df.iloc[:-1].copy()

    return df.reset_index(drop=True)


# -----------------------------
# INDICATEURS TECHNIQUES
# -----------------------------
def calculate_indicators(df):
    df = df.copy()

    # Moyennes mobiles
    df["SMA20"] = df["close"].rolling(20).mean()
    df["SMA50"] = df["close"].rolling(50).mean()

    # RSI 14
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
    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI"] = df["RSI"].fillna(50)

    # MACD
    ema12 = df["close"].ewm(
        span=12, adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26, adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    df["MACD_HIST"] = (
        df["MACD"] - df["MACD_SIGNAL"]
    )

    return df


# -----------------------------
# ANALYSE EXPLICATIVE
# -----------------------------
def analyze_market(df):
    last = df.iloc[-1]
    previous = df.iloc[-2]

    observations = []

    if last["close"] > last["SMA20"]:
        observations.append(
            "Le cours est au-dessus de la moyenne mobile 20."
        )
    else:
        observations.append(
            "Le cours est sous la moyenne mobile 20."
        )

    if last["SMA20"] > last["SMA50"]:
        observations.append(
            "La moyenne 20 est au-dessus de la moyenne 50."
        )
    else:
        observations.append(
            "La moyenne 20 est sous la moyenne 50."
        )

    if last["RSI"] >= 70:
        observations.append(
            "RSI élevé : le marché peut être en zone de surachat."
        )
    elif last["RSI"] <= 30:
        observations.append(
            "RSI bas : le marché peut être en zone de survente."
        )
    else:
        observations.append(
            "RSI dans une zone intermédiaire."
        )

    if last["MACD"] > last["MACD_SIGNAL"]:
        observations.append(
            "MACD au-dessus de sa ligne de signal."
        )
    else:
        observations.append(
            "MACD sous sa ligne de signal."
        )

    if (
        previous["MACD"] <= previous["MACD_SIGNAL"]
        and last["MACD"] > last["MACD_SIGNAL"]
    ):
        observations.append(
            "Croisement haussier récent du MACD à observer."
        )

    if (
        previous["MACD"] >= previous["MACD_SIGNAL"]
        and last["MACD"] < last["MACD_SIGNAL"]
    ):
        observations.append(
            "Croisement baissier récent du MACD à observer."
        )

    bullish_count = sum([
        last["close"] > last["SMA20"],
        last["SMA20"] > last["SMA50"],
        last["MACD"] > last["MACD_SIGNAL"]
    ])

    if bullish_count == 3 and last["RSI"] < 70:
        status = "PLUSIEURS SIGNAUX HAUSSIERS À ÉTUDIER"
    elif bullish_count == 0:
        status = "PLUSIEURS SIGNAUX BAISSIERS À ÉTUDIER"
    else:
        status = "SIGNAUX MIXTES — ATTENDRE PLUS DE CONFIRMATION"

    return status, observations


# -----------------------------
# INTERFACE TIBOT
# -----------------------------
st.title("📈 TIBOT AUTOMATIC")
st.caption("MARKET ANALYSIS TERMINAL • DONNEES PUBLIQUES")

st.success("Système d'analyse éducative — aucune transaction automatique.")

col1, col2 = st.columns(2)

with col1:
    selected_markets = st.multiselect(
        "Marchés à analyser",
        list(MARKETS.keys()),
        default=list(MARKETS.keys())
    )

with col2:
    selected_interval = st.selectbox(
        "Intervalle des bougies",
        list(INTERVALS.keys()),
        index=1
    )

refresh = st.button(
    "⟳ ACTUALISER LES ANALYSES",
    use_container_width=True
)

if refresh:
    st.cache_data.clear()

st.divider()

st.subheader("TABLEAU DE SURVEILLANCE")

if not selected_markets:
    st.info("Choisis au moins un marché pour commencer.")
else:
    for market_name in selected_markets:
        pair = MARKETS[market_name]

        st.markdown(f"### {market_name}")

        try:
            with st.spinner(f"Récupération des données de {market_name}..."):
                raw_df = get_market_data(
                    pair,
                    INTERVALS[selected_interval]
                )
                df = calculate_indicators(raw_df)

            if len(df) < 60:
                st.warning("Pas assez de données pour tous les indicateurs.")
                continue

            last = df.iloc[-1]
            status, observations = analyze_market(df)

            price_col, rsi_col, macd_col = st.columns(3)

            with price_col:
                st.metric(
                    "Dernière clôture",
                    f"${last['close']:,.2f}"
                )

            with rsi_col:
                st.metric(
                    "RSI (14)",
                    f"{last['RSI']:.1f}"
                )

            with macd_col:
                st.metric(
                    "MACD",
                    f"{last['MACD']:.2f}"
                )

            st.markdown("#### Graphique du marché")

            chart_data = df.set_index("time")[
                ["close", "SMA20", "SMA50"]
            ]

            st.line_chart(
                chart_data,
                height=350
            )

            st.caption(
                "Cours de clôture et moyennes mobiles 20 et 50."
            )

            st.markdown("#### Volume")

            st.bar_chart(
                df.set_index("time")[["volume"]],
                height=160
            )

            st.markdown("#### Lecture de TIBOT")

            st.info(status)

            for observation in observations:
                st.write("• " + observation)

            st.markdown("#### Historique récent")

            history = df[
                ["time", "close", "RSI", "MACD", "volume"]
            ].tail(10).copy()

            history["time"] = history["time"].dt.strftime(
                "%Y-%m-%d %H:%M"
            )

            st.dataframe(
                history,
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                f"Dernière bougie terminée : {last['time']}"
            )

        except Exception as error:
            st.error(
                f"Impossible de récupérer les données : {error}"
            )

        st.divider()

st.caption(
    "TIBOT AUTOMATIC • Données publiques Kraken • "
    "Les indicateurs sont des outils éducatifs, "
    "pas des prédictions ni des recommandations financières."
)
