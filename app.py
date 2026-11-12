
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
st.caption("MULTI-MARKET EDUCATIONAL ANALYSIS TERMINAL")

markets = ["NOVA (Simulation)", "Bitcoin", "Ethereum",
           "Actions", "Forex"]

market = st.sidebar.selectbox("MARCHÉ", markets)

horizon = st.sidebar.multiselect(
    "HORIZONS D'ANALYSE",
    ["Court terme", "Moyen terme", "Long terme"],
    default=["Court terme", "Moyen terme", "Long terme"]
)

st.sidebar.info("Mode éducatif — aucune transaction réelle.")

def generate_data():
    np.random.seed()
    changes = np.random.normal(0.0005, 0.012, 300)
    prices = 100 * np.cumprod(1 + changes)
    return pd.Series(prices)

def analyze(prices, period):
    fast = prices.rolling(period).mean()
    slow = prices.rolling(period * 3).mean()

    delta = prices.diff()
    gains = delta.clip(lower=0).rolling(14).mean()
    losses = -delta.clip(upper=0).rolling(14).mean()
    rs = gains / losses.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    current_rsi = rsi.iloc[-1]
    current_price = prices.iloc[-1]

    if pd.isna(current_rsi):
        return "DONNÉES INSUFFISANTES", current_rsi

    if current_rsi < 30 and current_price > fast.iloc[-1]:
        signal = "ACHAT SIMULÉ"
    elif current_rsi > 70 and current_price < fast.iloc[-1]:
        signal = "SORTIE SIMULÉE"
    else:
        signal = "ATTENDRE"

    return signal, current_rsi

prices = generate_data()

st.subheader(f"ANALYSE : {market}")

col1, col2 = st.columns(2)
col1.metric("Prix fictif", f"{prices.iloc[-1]:.2f} NOVA")
col2.metric("Points analysés", len(prices))

st.line_chart(prices)

st.divider()
st.subheader("ANALYSE MULTI-HORIZONS")

periods = {
    "Court terme": 5,
    "Moyen terme": 15,
    "Long terme": 30
}

for name in horizon:
    signal, rsi = analyze(prices, periods[name])

    st.markdown(f"### {name.upper()}")

    if pd.isna(rsi):
        st.warning(signal)
    else:
        st.write(f"RSI : {rsi:.2f}")
        st.write(f"Évaluation : **{signal}**")

        if signal == "ATTENDRE":
            st.info("Les conditions ne sont pas suffisamment réunies.")
        elif signal == "ACHAT SIMULÉ":
            st.success("Configuration favorable dans cette simulation.")
        else:
            st.warning("Configuration de sortie simulée.")

st.divider()
st.subheader("INFORMATIONS")

st.write("""
- Les données de cette première version sont entièrement fictives.
- Les signaux servent uniquement à apprendre.
- Les résultats ne prédisent pas les performances futures.
- Les marchés réels seront ajoutés dans une prochaine version.
""")
