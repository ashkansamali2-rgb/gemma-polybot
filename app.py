import streamlit as st
import subprocess
import re
import pandas as pd
import numpy as np
import psutil
import time
from engine import PolyEngine
from paper_trader import PaperWallet

# --- PAGE CONFIG ---
st.set_page_config(page_title="PolyBot Interface", page_icon="📟", layout="wide")

# --- INITIALIZE WALLET ---
wallet = PaperWallet()

# --- BEIGE & ORANGE THEME CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    :root { 
        --warm-beige: #F4F1EA; 
        --burnt-orange: #D95D39; 
        --dark-gray: #2D2D2D;
        --soft-white: #FFFFFF;
    }
    .stApp { 
        background-color: var(--warm-beige); 
        color: var(--dark-gray); 
        font-family: 'Inter', sans-serif; 
    }
    [data-testid="stMetric"] { 
        background: var(--soft-white); 
        border: none;
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        color: var(--dark-gray);
    }
    [data-testid="stMetric"] label { color: var(--dark-gray) !important; }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--burnt-orange) !important; }
    
    .stProgress > div > div > div > div { background-color: var(--burnt-orange); }
    
    .stButton>button { 
        width: 100%; 
        border: 1px solid var(--burnt-orange); 
        background: var(--soft-white); 
        color: var(--burnt-orange); 
        font-weight: bold;
    }
    .stButton>button:hover { 
        background: var(--burnt-orange); 
        color: white; 
        box-shadow: 0 4px 12px rgba(217, 93, 57, 0.3); 
    }
    .paper-banner { 
        background-color: #FFD700; 
        color: black; 
        padding: 10px; 
        text-align: center; 
        font-weight: bold; 
        border-radius: 5px; 
        margin-bottom: 20px; 
    }
    .market-card {
        border: 1px solid #E0DCD0;
        padding: 20px;
        border-radius: 10px;
        background: var(--soft-white);
        margin-bottom: 20px;
        transition: transform 0.2s;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .market-card:hover {
        transform: scale(1.01);
        box-shadow: 0 8px 16px rgba(0,0,0,0.08);
    }
    .countdown {
        color: #D95D39;
        font-weight: bold;
        font-size: 1.1em;
    }
    .buy-signal {
        background: var(--burnt-orange);
        color: white;
        padding: 8px 12px;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
    }
    h1, h2, h3 { color: var(--dark-gray) !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="paper-banner">⚠️ PAPER TRADING MODE ACTIVE - SIMULATED €5 WALLET</div>', unsafe_allow_html=True)

# --- CONSTANTS ---
FEE_2026 = 0.02 # 2% Platform Fee for 2026

# --- ANALYTICS SUITE ---
def get_neural_load():
    """Returns the Mac's RAM usage percentage."""
    return psutil.virtual_memory().percent

def calculate_net_profit(market_category, amount, price):
    """
    Calculates net profit after fees.
    """
    fee_rate = FEE_2026 # Defaulting to 2026 fee
    if market_category == 'Geopolitics':
        fee_rate = 0.0
    elif market_category in ['Politics/Tech', 'Politics', 'Tech']:
        fee_rate = 0.01
    
    fee = amount * fee_rate
    gross_profit = (amount / price) - amount if price > 0 else 0
    net_profit = gross_profit - fee
    return net_profit

def project_alpha_equity(start_bal=5.00, end_bal=8.00, days=30, trades_per_day=2):
    """Plots the Alpha Test growth: €5 to €8 over 30 days."""
    total_trades = days * trades_per_day
    growth_per_trade = (end_bal / start_bal) ** (1 / total_trades)
    
    equity_curve = []
    current_bal = start_bal
    for t in range(total_trades + 1):
        equity_curve.append(current_bal)
        current_bal *= growth_per_trade
    return equity_curve

def get_momentum_markets():
    """Returns mock data for 'Short-Term Momentum' scanning."""
    # Simulating data that would come from an API
    return [
        {
            "title": "Will SpaceX reach Mars by 2026?",
            "expiry_hours": 52,
            "volume_24h": 125000,
            "predicted_profit_pct": 0.15,
            "category": "Tech"
        },
        {
            "title": "BTC to hit $100k by end of week?",
            "expiry_hours": 12, # Filtered: < 48h
            "volume_24h": 500000,
            "predicted_profit_pct": 0.08,
            "category": "Other"
        },
        {
            "title": "US Fed rate cut in June?",
            "expiry_hours": 70,
            "volume_24h": 80000, # Filtered: < €100k
            "predicted_profit_pct": 0.20,
            "category": "Other"
        },
        {
            "title": "NVIDIA Stock > $1200 by Friday?",
            "expiry_hours": 65,
            "volume_24h": 250000,
            "predicted_profit_pct": 0.12,
            "category": "Politics/Tech"
        },
        {
            "title": "Solana ETF Approval Announcement?",
            "expiry_hours": 49,
            "volume_24h": 300000,
            "predicted_profit_pct": 0.01, # Filtered: Profit < Fee
            "category": "Tech"
        }
    ]

# --- ENGINE ---
@st.cache_resource
def get_engine():
    try:
        return PolyEngine(adapter_path="./poly_adapters")
    except Exception as e:
        st.error(f"ENGINE_OFFLINE: {e}")
        return None

# --- UI LOGIC ---
st.title("📟 PolyBot Interface // ANALYTICS_DASH")

# Sidebar for Status and Settings
with st.sidebar:
    st.header("⚙️ SYSTEM_CONFIG")
    alpha_score = st.slider("MODEL_ALPHA_SCORE (%)", 0.0, 10.0, 2.5) / 100
    st.divider()
    st.metric("NEURAL_LOAD", f"{get_neural_load()}%")
    if st.button("SYSTEM_REBOOT"):
        st.rerun()

# Top Row Metrics
m1, m2, m3, m4 = st.columns(4)
current_bal = wallet.get_balance()
m1.metric("BALANCE", f"€{current_bal:.2f}", f"{current_bal - 5.00:+.2f}")
m2.metric("ALPHA_SCORE", f"{alpha_score:.1%}", "OPTIMIZED")
m3.metric("FEE_ESTIMATE", "PAPER_VARIES", "SIMULATED")
m4.metric("WIN_RATE", "62%", "+4%")

st.divider()

col_main, col_side = st.columns([1.5, 1])

with col_main:
    st.subheader("📊 MOMENTUM_SCANNER (48-72H)")
    markets = get_momentum_markets()
    
    for m in markets:
        # 1. Filter by Expiry: 48-72 hours
        if not (48 <= m["expiry_hours"] <= 72):
            continue
            
        # 3. Volume Check: > €100,000
        if m["volume_24h"] <= 100000:
            continue
            
        # 2. Fee-Adjusted Edge: Subtract 2026 fee from predicted profit
        # Using 1% as a general paper trading average for scanner visibility
        adjusted_edge = m["predicted_profit_pct"] - 0.01
        
        with st.container():
            st.markdown(f"""
            <div class="market-card">
                <h3>{m['title']}</h3>
                <p>Volume (24h): €{m['volume_24h']:,}</p>
                <p>Predicted Profit: {m['predicted_profit_pct']:.1%}</p>
                <p><b>Adjusted Edge: {adjusted_edge:.1%}</b></p>
                <p class="countdown">⏳ TIME TO SETTLE: {m['expiry_hours']}h 00m</p>
            </div>
            """, unsafe_allow_html=True)
            
            if adjusted_edge > 0:
                st.markdown('<div class="buy-signal">⚡ BUY SIGNAL DETECTED</div>', unsafe_allow_html=True)
                if st.button(f"EXECUTE_TRADE: {m['title'][:20]}...", key=m['title']):
                    success, msg = wallet.buy_shares(m['title'], "YES", 0.50, 1.00, m['category'])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("HOLD: Edge below fee threshold.")
            st.write("") # Spacing

with col_side:
    st.subheader("🧠 BRAIN_INTERFACE")
    input_text = st.text_input("MANUAL_SIGNAL_INPUT", placeholder="Paste market title...")
    market_cat = st.selectbox("MARKET_CATEGORY", ["Geopolitics", "Sports", "Crypto", "Other"])
    
    if st.button("INITIATE_THINKING"):
        if input_text:
            thinking_feed = st.empty()
            full_response = ""
            
            engine = get_engine()
            if engine:
                with st.spinner("SYNCING..."):
                    for token in engine.stream_analyze({"title": input_text, "odds": "50%"}):
                        full_response += token
                        thinking_feed.markdown(f"**LIVE_THINKING_FEED**\n```markdown\n{full_response}█\n```")
                        time.sleep(0.01)
                
                # Final calculation display
                net_p = calculate_net_profit(market_cat, 5.0, 0.5)
                st.success(f"ANALYSIS_COMPLETE | EST_NET_PROFIT: €{net_p:.2f}")
                
                if st.button("EXECUTE_PAPER_TRADE"):
                    success, msg = wallet.buy_shares(input_text, "YES", 0.50, 1.00, market_cat)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.error("NO_SIGNAL_DETECTED")

    st.divider()
    st.subheader("📈 ALPHA_TEST_EQUITY")
    proj_data = project_alpha_equity(start_bal=5.00, end_bal=8.00, days=30, trades_per_day=2)
    df_proj = pd.DataFrame({"TRADE": np.arange(len(proj_data)), "EQUITY (€)": proj_data}).set_index("TRADE")
    st.line_chart(df_proj, color="#D95D39")

st.divider()
st.markdown("`PolyBot Interface v1.5 // ACTIVE_SESSION`")
