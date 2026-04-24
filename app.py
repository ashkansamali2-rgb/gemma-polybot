import streamlit as st
import pandas as pd
from paper_trader import PaperWallet

# --- PAGE CONFIG ---
st.set_page_config(page_title="PolyBot", page_icon="●", layout="wide", initial_sidebar_state="collapsed")

# --- DATA LOAD ---
wallet = PaperWallet()
wallet_data = wallet.state
balance = wallet_data.get("balance", 0.0)
positions = wallet_data.get("positions", [])
deployed_capital = sum(p.get("amount", 0.0) for p in positions)
open_positions_count = len(positions)

# --- MINIMALIST CSS ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    :root {{
        --bg-color: #FDFBF7;
        --text-color: #2B2B2B;
        --accent-color: #E07A5F;
    }}

    .stApp {{
        background-color: var(--bg-color);
        color: var(--text-color);
        font-family: 'Inter', sans-serif;
    }}

    /* Remove Streamlit Elements */
    #MainMenu, footer, header {{visibility: hidden;}}
    [data-testid="stSidebar"] {{display: none;}}

    /* Typography */
    h1 {{
        font-weight: 300;
        letter-spacing: -1px;
        text-align: center;
        margin-bottom: 3rem;
        margin-top: 2rem;
        color: var(--text-color);
    }}
    
    h2, h3 {{
        font-weight: 400;
        color: var(--text-color);
        margin-bottom: 1.5rem;
    }}

    /* Metrics Styling */
    [data-testid="stMetricValue"] {{
        color: var(--accent-color) !important;
        font-weight: 300 !important;
        font-size: 2.5rem !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: var(--text-color) !important;
        font-size: 0.9rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    [data-testid="stMetric"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }}

    /* Table/List Styling */
    .position-row {{
        padding: 1.5rem 0;
        border-bottom: 1px solid rgba(0,0,0,0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    
    .status-badge {{
        color: var(--accent-color);
        font-weight: 600;
        font-size: 0.8rem;
        letter-spacing: 1px;
    }}

    .section-padding {{
        padding: 4rem 0;
    }}

    /* Divider */
    .stDivider {{
        border-bottom: 1px solid rgba(0,0,0,0.05) !important;
    }}

</style>
""", unsafe_allow_html=True)

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

# --- MAIN CONTENT ---
st.markdown("<h3>ACTIVE_POSITIONS</h3>", unsafe_allow_html=True)

if not positions:
    st.markdown("<p style='opacity: 0.5;'>Awaiting market entry...</p>", unsafe_allow_html=True)
else:
    import time
    now = time.time()
    for pos in positions:
        # Calculate percentage of total deployed capital
        pct = (pos['amount'] / deployed_capital) * 100 if deployed_capital > 0 else 0
        
        # Calculate countdown
        expiry = pos.get("expiry_timestamp")
        countdown_text = ""
        if expiry:
            diff = expiry - now
            if diff > 0:
                hours = int(diff // 3600)
                mins = int((diff % 3600) // 60)
                countdown_text = f"⏳ Resolves in: {hours}h {mins}m"
            else:
                countdown_text = "⏳ Resolving..."
        
        st.markdown(f"""
        <div style="padding: 1rem 0; background: transparent;">
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
                <span style="color: #2B2B2B; font-weight: 400; font-size: 1.1rem; flex-grow: 1;">{pos['market_title']}</span>
                <span style="color: #666666; font-size: 0.85rem; margin-right: 15px;">{countdown_text}</span>
                <span style="color: #2B2B2B; font-weight: 600;">€{pos['amount']:.2f}</span>
            </div>
            <div style="width: 100%; background-color: rgba(0,0,0,0.03); height: 4px; border-radius: 2px;">
                <div style="width: {pct}%; background-color: #E07A5F; height: 4px; border-radius: 2px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- FOOTER ---
st.markdown("<div style='padding-top: 5rem; text-align: center; opacity: 0.4; font-size: 0.7rem; letter-spacing: 2px;'>SYSTEM STATUS: ONLINE // READ-ONLY MODE</div>", unsafe_allow_html=True)
