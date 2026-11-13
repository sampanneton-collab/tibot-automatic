
import streamlit as st
import pandas as pd
import numpy as np
import urllib.request
import urllib.error
import json

# --------------------------------
# CONFIGURATION
# --------------------------------
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
    background: #101a14;
    border: 1px solid #1d5735;
    padding: 14px;
    border-radius: 10px;
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

# --------------------------------
# NOTIFICATIONS NTFY
# --------------------------------
NTFY_TOPIC = "tibot-alertes-73x92"

def send_ntfy_notification(market, title, explanation):
    message = (
        f"{market}\n"
        f"{title}\n\n"
        f"{explanation}\n\n"
        "Observation éducative de TIBOT AUTOMATIC."
    )

    request = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "TIBOT - Nouvelle alerte",
            "Priority": "default",
            "Tags": "chart_with_upwards_trend"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status == 200
    except Exception as error:
        print(f"Erreur notification ntfy : {error}")
        return False


# --------------------------------
# MEMOIRE DES ALERTES
# --------------------------------
if "tibot_alerts" not in st.session_state:
    st.session_state.tibot_alerts = []

if "tibot_seen" not in st.session_state:
    st.session_state.tibot_seen = set()


# --------------------------------
# DONNEES PUBLIQUES KRAKEN
# --------------------------------
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

    # Retirer la bougie encore en formation
    if len(df) > 1:
        df = df.iloc[:-1].copy()

    return df.reset_index(drop=True)


# --------------------------------
# INDICATEURS
# --------------------------------
def calculate_indicators(df):
    df = df.copy()

    df["SMA20"] = df["close"].rolling(20).mean()
    df["SMA50"] = df["close"].rolling(50).mean()

    change = df["close"].diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)

    avg_gain = gains.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = losses.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = (100 - 100 / (1 + rs)).fillna(50)

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()

    df["MACD"] = ema12 - ema26
    df["SIGNAL"] = df["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    return df


# --------------------------------
# DETECTION DES EVENEMENTS
# --------------------------------
def detect_alerts(market_name, df):
    if len(df) < 60:
        return []

    previous = df.iloc[-2]
    last = df.iloc[-1]

    events = []
    candle_time = str(last["time"])

    # Croisement MACD
    if (
        previous["MACD"] <= previous["SIGNAL"]
        and last["MACD"] > last["SIGNAL"]
    ):
        events.append((
            "MACD",
            "Croisement haussier du MACD",
            "Le MACD vient de passer au-dessus de sa ligne de signal."
        ))

    elif (
        previous["MACD"] >= previous["SIGNAL"]
        and last["MACD"] < last["SIGNAL"]
    ):
        events.append((
            "MACD",
            "Croisement baissier du MACD",
            "Le MACD vient de passer sous sa ligne de signal."
        ))

    # Croisement des moyennes mobiles
    if (
        previous["SMA20"] <= previous["SMA50"]
        and last["SMA20"] > last["SMA50"]
    ):
        events.append((
            "MOYENNES",
            "Croisement haussier des moyennes",
            "La moyenne mobile 20 vient de passer au-dessus de la 50."
        ))

    elif (
        previous["SMA20"] >= previous["SMA50"]
        and last["SMA20"] < last["SMA50"]
    ):
        events.append((
            "MOYENNES",
            "Croisement baissier des moyennes",
            "La moyenne mobile 20 vient de passer sous la 50."
        ))

    # Sortie des zones RSI extrêmes
    if previous["RSI"] > 70 and last["RSI"] <= 70:
        events.append((
            "RSI",
            "RSI sort de la zone de surachat",
            "Le RSI repasse sous 70."
        ))

    elif previous["RSI"] < 30 and last["RSI"] >= 30:
        events.append((
            "RSI",
            "RSI sort de la zone de survente",
            "Le RSI repasse au-dessus de 30."
        ))

    # Enregistrer et envoyer les nouvelles alertes
    for category, title, explanation in events:
        alert_id = (
            market_name,
            category,
            candle_time,
            title
        )

        if alert_id not in st.session_state.tibot_seen:
            st.session_state.tibot_seen.add(alert_id)

            st.session_state.tibot_alerts.insert(0, {
                "market": market_name,
                "title": title,
                "explanation": explanation,
                "time": candle_time
            })

            send_ntfy_notification(
                market_name,
                title,
                explanation
            )

    st.session_state.tibot_alerts = (
        st.session_state.tibot_alerts[:30]
    )

    return events


# --------------------------------
# ANALYSE GENERALE
# --------------------------------
def analyze_market(df):
    last = df.iloc[-1]
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
            "RSI élevé : zone de surachat possible."
        )
    elif last["RSI"] <= 30:
        observations.append(
            "RSI bas : zone de survente possible."
        )
    else:
        observations.append(
            "RSI dans une zone intermédiaire."
        )

    if last["MACD"] > last["SIGNAL"]:
        observations.append(
            "MACD au-dessus de sa ligne de signal."
        )
    else:
        observations.append(
            "MACD sous sa ligne de signal."
        )

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


# --------------------------------
# INTERFACE
# --------------------------------
st.title("📈 TIBOT AUTOMATIC")
st.caption("MARKET ANALYSIS TERMINAL • KRAKEN LIVE DATA")

st.success(
    "Surveillance automatique • Alertes éducatives • "
    "Aucune transaction automatique"
)

col1, col2 = st.columns(2)

with col1:
    selected_markets = st.multiselect(
        "Marchés à surveiller",
        list(MARKETS.keys()),
        default=list(MARKETS.keys())
    )

with col2:
    selected_interval = st.selectbox(
        "Intervalle des bougies",
        list(INTERVALS.keys()),
        index=1
    )


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
                pair,
                INTERVALS[selected_interval]
            )

            df = calculate_indicators(raw)

            if len(df) < 60:
                st.warning(
                    "Pas assez de données pour les indicateurs."
                )
                continue

            detect_alerts(market_name, df)

            last = df.iloc[-1]
            status, observations = analyze_market(df)

            c1, c2, c3 = st.columns(3)

            c1.metric("PRIX ACTUEL", f"${price:,.2f}")
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

    # Centre d'alertes actualisé avec le tableau de bord
    st.divider()
    st.subheader("🔔 CENTRE D'ALERTES")

    if st.session_state.tibot_alerts:
        for alert in st.session_state.tibot_alerts:
            with st.container(border=True):
                st.markdown(
                    f"**{alert['market']} — {alert['title']}**"
                )
                st.write(alert["explanation"])
                st.caption(
                    f"Bougie clôturée : {alert['time']}"
                )
    else:
        st.info(
            "Aucune nouvelle alerte pour le moment. "
            "TIBOT continue de surveiller les marchés."
        )


live_dashboard()

if st.button("EFFACER L'HISTORIQUE DES ALERTES"):
    st.session_state.tibot_alerts = []
    st.session_state.tibot_seen = set()
    st.rerun()

st.caption(
    "TIBOT AUTOMATIC • Données publiques Kraken. "
    "Les indicateurs sont éducatifs et ne prédisent pas les marchés."
)
if st.button("🔔 TESTER NOTIFICATION IPHONE"):
    success = send_ntfy_notification(
        "TIBOT AUTOMATIC",
        "TEST DE NOTIFICATION",
        "Bonne nouvelle ! TIBOT communique avec ton iPhone."
    )

    if success:
        st.success("Notification envoyée à ntfy !")
    else:
        st.error("Échec de l'envoi. Vérifie la connexion.")
