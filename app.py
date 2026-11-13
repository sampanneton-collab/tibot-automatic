
import streamlit as st
import numpy as np
import pandas as pd

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
    color: #39ff88 !important;
}
[data-testid="stMetric"] {
    background: #111c17;
    border: 1px solid #245b3c;
    padding: 15px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.title("🟢 TIBOT AUTOMATIC")
st.caption("MULTI-MARKET ANALYSIS TERMINAL")

markets = [
    "NOVA (Simulation)",
    "Bitcoin (Simulation)",
    "Ethereum (Simulation)",
    "Actions (Simulation)",
    "Forex (Simulation)"
]

selected = st.sidebar.multiselect(
    "MARCHÉS À ANALYSER",
    markets,
    default=markets
)

horizons = st.sidebar.multiselect(
    "HORIZONS D'ANALYSE",
    ["Court terme", "Moyen terme", "Long terme"],
    default=["Court terme", "Moyen terme", "Long terme"]
)

st.sidebar.info(
    "MODE SIMULATION — Aucune transaction réelle."
)

def generate_data():
    changes = np.random.normal(0.0005, 0.012, 300)
    prices = 100 * np.cumprod(1 + changes)
    return pd.Series(prices)

if "market_data" not in st.session_state:
    st.session_state.market_data = {}

def refresh_data():
    st.session_state.market_data = {
        market: generate_data()
        for market in markets
    }

if not st.session_state.market_data:
    refresh_data()

if st.button("🔄 ACTUALISER LES ANALYSES"):
    refresh_data()

def analyze(prices, period):
    fast = prices.rolling(period).mean()
    slow = prices.rolling(period * 3).mean()

    delta = prices.diff()
    gains = delta.clip(lower=0).rolling(14).mean()
    losses = -delta.clip(upper=0).rolling(14).mean()

    rs = gains / losses.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    ema12 = prices.ewm(span=12).mean()
    ema26 = prices.ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()

    current_rsi = rsi.iloc[-1]
    current_macd = macd.iloc[-1]
    current_signal = signal_line.iloc[-1]

    if pd.isna(current_rsi):
        return "DONNÉES INSUFFISANTES", current_rsi, current_macd

    if current_rsi < 30 and current_macd > current_signal:
        signal = "ACHAT SIMULÉ"
    elif current_rsi > 70 and current_macd < current_signal:
        signal = "SORTIE SIMULÉE"
    else:
        signal = "ATTENDRE"

    return signal, current_rsi, current_macd

periods = {
    "Court terme": 5,
    "Moyen terme": 15,
    "Long terme": 30
}

st.subheader("📊 TABLEAU DE BORD")

if not selected:
    st.warning("Sélectionne au moins un marché.")
    st.stop()

for market in selected:
    prices = st.session_state.market_data[market]

    st.divider()
    st.subheader(f"📈 {market.upper()}")

    col1, col2, col3 = st.columns(3)

    col1.metric("PRIX SIMULÉ", f"{prices.iloc[-1]:.2f}")
    col2.metric("POINTS ANALYSÉS", len(prices))
    col3.metric(
        "VARIATION",
        f"{((prices.iloc[-1] / prices.iloc[0]) - 1) * 100:.2f}%"
    )

    st.line_chart(prices)

    st.markdown("### ANALYSE MULTI-HORIZONS")

    for horizon in horizons:
        signal, rsi, macd = analyze(
            prices,
            periods[horizon]
        )

        st.markdown(f"**{horizon.upper()}**")

        if pd.isna(rsi):
            st.warning(signal)
        else:
            a, b, c = st.columns(3)
            a.metric("RSI", f"{rsi:.2f}")
            b.metric("MACD", f"{macd:.4f}")
            c.write(f"Signal : **{signal}**")

            if signal == "ACHAT SIMULÉ":
                st.success("Signal pédagogique : conditions à étudier.")
            elif signal == "SORTIE SIMULÉE":
                st.warning("Signal pédagogique : conditions de sortie à étudier.")
            else:
                st.info("Aucun signal suffisamment clair.")

st.divider()

st.subheader("⚙️ ÉTAT DU ROBOT")

st.success("Moteur d'analyse en fonctionnement")
st.write(f"Marchés sélectionnés : {len(selected)}")
st.write("Indicateurs : RSI, MACD, moyennes mobiles.")
st.write("Données : entièrement fictives.")

st.caption(
    "TIBOT est un outil éducatif en simulation. "
    "Les signaux ne constituent pas des recommandations financières."
)
