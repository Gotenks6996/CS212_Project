# app.py

import re, subprocess
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd                                          # for DataFrame & CSV export 
import streamlit as st                                       # Streamlit UI 
import validators                                            # URL validation 
import plotly.graph_objects as go                            # Gauge chart 
import plotly.express as px                                  # Time‑series chart 
from streamlit_autorefresh import st_autorefresh             # Auto‑refresh 

# — Page setup (must be first Streamlit call)  
st.set_page_config(page_title="🌐 Live SiteSpeedometer", layout="centered")  
st.title("🌐 Live SiteSpeedometer")

# — Auto‑refresh every 4000 ms (4 s)  
st_autorefresh(interval=2500, limit=None, key="ping_refresh")  

# — URL input  
url = st.text_input("Enter website URL (e.g. https://example.com):")
if not validators.url(url):                                   
    st.info("Please enter a valid URL.")
    st.stop()
host = urlparse(url).hostname                                  

# — Ping & parse function  
def get_ping_stats(host, count=3):
    # Force English locale so regex matches predictably 
    res = subprocess.run(
        ["ping","-c",str(count),host],
        capture_output=True, text=True, timeout=5,
        env={"LC_ALL":"C"}
    )
    out = res.stdout

    # Packet‑loss extraction  
    m_loss = re.search(r"(\d+)% packet loss", out)
    loss = float(m_loss.group(1)) if m_loss else 100.0         

    # RTT extraction with guard  
    m_rtt = re.search(
        r"rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms",
        out
    )
    if m_rtt:
        min_rtt, avg_rtt, max_rtt, _ = map(float, m_rtt.groups())
    else:
        min_rtt = avg_rtt = max_rtt = 0.0                       

    return min_rtt, avg_rtt, max_rtt, loss

# — Initialize history log on first run  
if "history" not in st.session_state:
    st.session_state.history = []                              

# — Fetch metrics every 4 s  
min_rtt, avg_rtt, max_rtt, pkt_loss = get_ping_stats(host, count=3)

# — Compute relative change vs previous cycle  
prev = st.session_state.get("prev_avg", avg_rtt)
rel_change = (prev - avg_rtt)/prev*100 if prev else 0.0
st.session_state.prev_avg = avg_rtt

# — Log this cycle  
st.session_state.history.append({
    "timestamp": datetime.now(),
    "min_rtt": min_rtt,
    "avg_rtt": avg_rtt,
    "max_rtt": max_rtt,
    "packet_loss": pkt_loss,
    "rel_change": rel_change
})

# — Live radial gauge (Plotly Indicator)  
fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number",
    value=avg_rtt,
    gauge={
        "axis": {"range": [0, 300]},
        "steps": [
            {"range": [0, 100], "color": "lightgreen"},
            {"range": [100, 300], "color": "lightcoral"}
        ],
        "threshold": {"line": {"color": "red", "width": 4}, "value": 200}
    },
    title={"text": f"Avg RTT to {host} (ms)"}
))
st.plotly_chart(fig_gauge, use_container_width=True)           

# — Metrics row  
c1, c2, c3, c4 = st.columns(4)                                
c1.metric("Min RTT (ms)", f"{min_rtt:.1f}")                   
c2.metric("Max RTT (ms)", f"{max_rtt:.1f}")                   
c3.metric("Packet Loss (%)", f"{pkt_loss:.1f}%")               
c4.metric("Rel Speed (%)", f"{rel_change:.1f}%", delta=f"{rel_change:.1f}%") 

# — Historic time‑series chart (avg_rtt, packet_loss, rel_change)  
df = pd.DataFrame(st.session_state.history)                    
fig_ts = px.line(
    df, x="timestamp", y=["avg_rtt","packet_loss","rel_change"],
    labels={"value":"ms / %","timestamp":"Time","variable":"Metric"},
    title="History: Latency & Packet Loss Over Time"
)
st.plotly_chart(fig_ts, use_container_width=True)              

# — Downloadable CSV report  
csv_data = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download Report as CSV",
    data=csv_data,
    file_name="latency_report.csv",
    mime="text/csv"
)                                                               
