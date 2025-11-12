import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import uuid  # for unique chart IDs
import os
import json

# -------------------------
# Firebase initialization
# -------------------------
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')
DATABASE_URL = os.getenv('DATABASE_URL')

if not SERVICE_ACCOUNT_JSON:
    st.error("SERVICE_ACCOUNT_JSON environment variable is not set")
    st.stop()
if not DATABASE_URL:
    st.error("DATABASE_URL environment variable is not set")
    st.stop()

if not firebase_admin._apps:
    service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})

# -------------------------
# Streamlit UI configuration
# -------------------------
st.set_page_config(page_title="Accident Detection Dashboard", layout="wide")
st.title("🚗 Smart Accident Detection Dashboard")

# Sidebar
st.sidebar.header("⚙️ Controls")
refresh_rate = st.sidebar.slider("⏱ Refresh rate (seconds)", 3, 30, 5)
show_raw = st.sidebar.checkbox("Show Raw Firebase Data", value=False)
refresh_button = st.sidebar.button("🔄 Manual Refresh")

# -------------------------
# Firebase fetch function
# -------------------------
def fetch_data():
    ref = db.reference("/AccidentEvents")
    data = ref.get()
    rows = []

    if data and isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, dict):
                rows.append({
                    "ID": key,
                    "Acceleration": val.get("Acceleration", 0),
                    "Status": val.get("Status", "Unknown"),
                    "Severity": val.get("Severity", None),
                    "Timestamp": val.get("Timestamp", 0)
                })

    if rows:
        df = pd.DataFrame(rows)
        # Convert timestamp safely
        df["Time"] = pd.to_datetime(df["Timestamp"], unit='ms', errors='coerce')
        df = df.sort_values("Time", ascending=False)
        return df
    else:
        return pd.DataFrame(columns=["ID", "Acceleration", "Status", "Severity", "Timestamp", "Time"])

# -------------------------
# Main Section
# -------------------------
st.info("Fetching latest data from Firebase...")
df = fetch_data()

if df.empty:
    st.warning("⚠️ No accident data found in Firebase Realtime Database.")
else:
    # Summary Metrics
    total_events = len(df)
    total_accidents = df[df["Severity"] == 1].shape[0]
    total_normal = df[df["Severity"] == 0].shape[0]
    last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Total Events", total_events)
    col2.metric("🚨 Accidents Detected", total_accidents)
    col3.metric("✅ Normal Events", total_normal)
    col4.metric("🕒 Last Updated", last_update_time)

    # Line chart (Acceleration over time)
    fig = px.line(
        df.sort_values("Time"),
        x="Time",
        y="Acceleration",
        color="Status",
        title="📈 Acceleration vs Time",
        markers=True
    )

    # Unique key fix (prevents Streamlit duplicate element crash)
    st.plotly_chart(fig, use_container_width=True, key=f"plot_{uuid.uuid4().hex}")

    # Recent logs table
    st.subheader("🧾 Recent Logs")
    st.dataframe(df[["Time", "Acceleration", "Status", "Severity"]].head(20), use_container_width=True)

    # Download CSV button
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download All Data (CSV)",
        data=csv,
        file_name="accident_data.csv",
        mime="text/csv"
    )

    # Show raw Firebase data if toggled
    if show_raw:
        st.subheader("🪵 Raw Firebase Data")
        st.write(df)

# Manual refresh
if refresh_button:
    st.experimental_rerun()
