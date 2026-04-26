import streamlit as st
import pandas as pd
import time
from paper_trader import PaperWallet

# --- PAGE CONFIG ---
st.set_page_config(page_title="PolyBot", page_icon="●", layout="wide", initial_sidebar_state="collapsed")

# --- DATA LOAD ---
wallet = PaperWallet()
wallet_data = wallet.state
balance = wallet_data.get("balance", 0.0)
positions = wallet_data.get("positions", [])
settled = wallet_data.get("settled", [])
deployed_capital = sum(p.get("amount", 0.0) for p in positions)
open_positions_count = len(positions)

# --- MINIMALIST CSS ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap');
    
    :root {{
        --bg-color: #FDFBF7;
        --text-color: #2B2B2B;
        --accent-color: #E07A5F;
        --muted-color: #666666;
        --terminal-bg: #F5F2EA;
    }}

    .stApp {{
        background-color: var(--bg-color);
        color: var(--text-color);
        font-family: 'Inter', sans-serif;
    }}

    /* Remove Streamlit Elements */
    #MainMenu, footer, header {{visibility: hidden;}}
    [data-testid="stSidebar"] {{display: none;}}

    /* Layout */
    .main-container {{
        max-width: 900px;
        margin: 0 auto;
        padding: 2rem 1rem;
    }}

    /* Typography */
    h1 {{
        font-weight: 300;
        letter-spacing: -0.5px;
        text-align: center;
        margin-bottom: 4rem;
        margin-top: 2rem;
        color: var(--text-color);
        font-size: 1.8rem;
    }}
    
    h3 {{
        font-weight: 500;
        color: var(--text-color);
        margin-bottom: 2rem;
        font-size: 0.8rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        opacity: 0.8;
    }}

    /* Metrics Styling */
    [data-testid="stMetricValue"] {{
        color: var(--accent-color) !important;
        font-weight: 300 !important;
        font-size: 2rem !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: var(--muted-color) !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    [data-testid="stMetric"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }}

    /* Ledger Styling */
    .ledger-row {{
        padding: 1.2rem 0;
        border-bottom: 1px solid rgba(0,0,0,0.03);
    }}
    
    .ledger-top {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 12px;
    }}

    .market-title {{
        color: var(--text-color);
        font-weight: 400;
        font-size: 0.95rem;
        flex-grow: 1;
    }}

    .data-columns {{
        display: flex;
        gap: 2rem;
        text-align: right;
    }}

    .data-item {{
        display: flex;
        flex-direction: column;
    }}

    .data-label {{
        font-size: 0.6rem;
        color: var(--muted-color);
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 2px;
    }}

    .data-value {{
        font-size: 0.85rem;
        font-weight: 500;
        color: var(--text-color);
    }}

    .weight-bar-bg {{
        width: 100%;
        background-color: rgba(0,0,0,0.03);
        height: 2px;
        border-radius: 1px;
    }}

    .weight-bar-fill {{
        background-color: var(--accent-color);
        height: 2px;
        border-radius: 1px;
    }}

    /* Settled Section */
    .settled-section {{
        margin-top: 5rem;
        margin-bottom: 5rem;
    }}

    .settled-row {{
        display: flex;
        justify-content: space-between;
        padding: 0.8rem 0;
        font-size: 0.85rem;
        border-bottom: 1px solid rgba(0,0,0,0.02);
    }}

    .empty-state {{
        color: #A0A0A0;
        font-style: italic;
        font-size: 0.85rem;
        padding: 1rem 0;
    }}

    /* Terminal Output */
    .terminal-box {{
        background-color: var(--terminal-bg);
        padding: 1.5rem;
        border-radius: 4px;
        margin-top: 4rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        color: #4A4A4A;
        letter-spacing: 0.5px;
    }}

    .terminal-status {{
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    /* Divider */
    .stDivider {{
        border-bottom: 1px solid rgba(0,0,0,0.05) !important;
        margin: 3rem 0 !important;
    }}

</style>
""", unsafe_allow_html=True)

# --- WRAPPER START ---
st.markdown('<div class="main-container">', unsafe_allow_html=True)

# --- HEADER ---
st.markdown("<h1>PolyBot / Autonomous Intelligence</h1>", unsafe_allow_html=True)

# --- TOP METRICS ---
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Current Balance", f"€{balance:.2f}")
with c2:
    st.metric("Deployed Capital", f"€{deployed_capital:.2f}")
with c3:
    st.metric("Open Positions", f"{open_positions_count}")

st.divider()

# --- ACTIVE POSITIONS ---
st.markdown("<h3>ACTIVE_POSITIONS</h3>", unsafe_allow_html=True)

if not positions:
    st.markdown("<p class='empty-state'>Awaiting market entry...</p>", unsafe_allow_html=True)
else:
    now = time.time()
    for pos in positions:
        pct = (pos['amount'] / deployed_capital) * 100 if deployed_capital > 0 else 0
        
        # Countdown calculation
        expiry = pos.get("expiry_timestamp")
        countdown_text = "N/A"
        if expiry:
            diff = expiry - now
            if diff > 0:
                hours = int(diff // 3600)
                mins = int((diff % 3600) // 60)
                countdown_text = f"⏳ {hours}h {mins}m"
            else:
                countdown_text = "⏳ Resolving"
        
        # Price formatting (e.g., 0.62 -> 62¢)
        price_val = pos.get('price', 0)
        entry_text = f"{int(price_val * 100)}¢" if price_val < 1 else f"€{price_val:.2f}"
        
        st.markdown(f"""
        <div class="ledger-row">
            <div class="ledger-top">
                <span class="market-title">{pos['market_title']}</span>
                <div class="data-columns">
                    <div class="data-item">
                        <span class="data-label">SHARES</span>
                        <span class="data-value">{pos.get('shares', 0):.2f}</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">ENTRY</span>
                        <span class="data-value">{entry_text}</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">RESOLVES</span>
                        <span class="data-value">{countdown_text}</span>
                    </div>
                </div>
            </div>
            <div class="weight-bar-bg">
                <div class="weight-bar-fill" style="width: {pct}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- SETTLEMENT ARCHIVE ---
st.markdown('<div class="settled-section">', unsafe_allow_html=True)
st.markdown("<h3>SETTLED_TRADES</h3>", unsafe_allow_html=True)

if not settled:
    st.markdown("<p class='empty-state'>Awaiting first market resolution.</p>", unsafe_allow_html=True)
else:
    for s in settled[-5:]: # Show last 5
        result_color = "#2D6A4F" if s.get('result') == "WON" else "#A4161A"
        st.markdown(f"""
        <div class="settled-row">
            <span style="opacity: 0.8;">{s['market_title']}</span>
            <span style="color: {result_color}; font-weight: 600; font-size: 0.7rem; letter-spacing: 1px;">{s.get('result')}</span>
        </div>
        """, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# --- BOT TELEMETRY ---
# Mocking status based on data
status_text = "HIBERNATING" if open_positions_count == 0 else "SNIPING"
batch_progress = f"{len(settled) % 5}/5" if len(settled) > 0 else "0/5"

st.markdown(f"""
<div class="terminal-box">
    <div class="terminal-status">
        <span>🟢 SYSTEM: {status_text}</span>
        <span style="margin-left: 20px; opacity: 0.5;">|</span>
        <span style="margin-left: 20px;">DAILY BATCH: {batch_progress} COMPLETE</span>
    </div>
    <div style="margin-top: 10px; opacity: 0.4; font-size: 0.65rem;">
        LAST_SCAN: {time.strftime("%H:%M:%S")} // EDGE_THRESHOLD: 15% // ENGINE: QWEN_27B
    </div>
</div>
""", unsafe_allow_html=True)

# --- FOOTER ---
st.markdown("<div style='padding-top: 3rem; text-align: center; opacity: 0.3; font-size: 0.6rem; letter-spacing: 2px;'>NON-CUSTODIAL PAPER TRADING ENGINE // v2.1</div>", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
