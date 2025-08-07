import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import time, os
from dotenv import load_dotenv  
load_dotenv()

HAPPYROBOT_REST_API_KEY = os.getenv("HAPPYROBOT_REST_API_KEY")
API_URL_ANALYTICS = os.getenv("API_URL_ANALYTICS")

headers = {"x-api-key": HAPPYROBOT_REST_API_KEY}

st.set_page_config(page_title="Negotiation Metrics", layout="wide")
st.title("Live Negotiation Metrics Dashboard")

placeholder = st.empty()
REFRESH_INTERVAL = 2  # Polling interval

def load_data():
    resp = requests.get(f"{API_URL_ANALYTICS}/analytics/events", headers=headers)
    if resp.status_code == 200:
        return pd.DataFrame(resp.json())
    return pd.DataFrame()

df = load_data()

if df.empty:
    st.info("Waiting for data...")
else:
    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Events", len(df))
    col2.metric("Accepted", (df.negotiation_outcome == "accepted").sum())
    col3.metric("Declined", (df.negotiation_outcome == "declined").sum())

    st.subheader("Negotiation Outcome Distribution")
    fig1 = px.pie(df, names="negotiation_outcome", title="Outcome Share")
    st.plotly_chart(fig1, use_container_width=True, key="pie_outcome")

    st.subheader("Sentiment Breakdown")
    fig2 = px.histogram(df, x="sentiment", title="Sentiment Counts")
    st.plotly_chart(fig2, use_container_width=True, key="hist_sentiment")

    st.subheader("Offer vs Final Rate")
    fig3 = px.scatter(df, x="offer_amount", y="final_rate", color="negotiation_outcome",
                      hover_data=["carrier_name", "mc_number"])
    st.plotly_chart(fig3, use_container_width=True, key="scatter_off_vs_final")

    st.subheader("Call Outcome Counts")
    counts = df["call_outcome"].value_counts()
    counts_df = counts.rename_axis("call_outcome").reset_index(name="count")
    fig4 = px.bar(counts_df, x="call_outcome", y="count",
                  labels={"call_outcome": "Call Outcome", "count": "Count"},
                  title="Call Outcome Counts")
    st.plotly_chart(fig4, use_container_width=True, key="bar_call_outcome")

# Scheduling the next refresh
time.sleep(REFRESH_INTERVAL)
st.rerun()