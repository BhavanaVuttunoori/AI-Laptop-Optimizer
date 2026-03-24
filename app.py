# app.py
import psutil
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import shutil
from datetime import datetime, timedelta
from openai import OpenAI
from sklearn.linear_model import LinearRegression
from win10toast import ToastNotifier
from urllib.parse import urlparse
import requests

# -----------------------------
# OpenAI client
# -----------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# Notifications
# -----------------------------
toaster = ToastNotifier()

# -----------------------------
# Data storage
# -----------------------------
CSV_FILE = "system_log.csv"

def log_data(cpu, memory, disk):
    df = pd.DataFrame([[datetime.now(), cpu, memory, disk]],
                      columns=["Time", "CPU", "Memory", "Disk"])
    if os.path.exists(CSV_FILE):
        df.to_csv(CSV_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(CSV_FILE, index=False)

# -----------------------------
# System stats
# -----------------------------
def get_system_stats():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    log_data(cpu, memory, disk)
    # Notifications
    if cpu > 85:
        toaster.show_toast("High CPU Usage", f"CPU at {cpu}%", duration=5)
    if memory > 85:
        toaster.show_toast("High Memory Usage", f"Memory at {memory}%", duration=5)
    if disk > 95:
        toaster.show_toast("Disk Almost Full", f"Disk at {disk}%", duration=5)
    return cpu, memory, disk

# -----------------------------
# Idle apps (>7 days)
# -----------------------------
def get_idle_apps(days=7):
    idle_apps = []
    threshold = datetime.now() - timedelta(days=days)
    program_dirs = [os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)")]
    for dir_path in program_dirs:
        if dir_path and os.path.exists(dir_path):
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.endswith(".exe"):
                        try:
                            full_path = os.path.join(root, file)
                            last_used = datetime.fromtimestamp(os.path.getatime(full_path))
                            if last_used < threshold:
                                idle_apps.append((file, last_used))
                        except:
                            continue
    return idle_apps

# -----------------------------
# Heavy background apps
# -----------------------------
HEAVY_APPS = ["chrome.exe", "code.exe", "msedge.exe", "teams.exe", "skype.exe"]
def get_heavy_background_apps():
    running = []
    for proc in psutil.process_iter(['name', 'cpu_percent']):
        try:
            if proc.info['name'] in HEAVY_APPS and proc.info['cpu_percent'] < 1:
                running.append(proc.info['name'])
        except:
            continue
    return running

# -----------------------------
# Laptop Health Score
# -----------------------------
def calculate_health(cpu, memory, disk, idle_apps, heavy_apps):
    score = 100
    # Deduct points
    score -= max(cpu-50, 0) * 0.5
    score -= max(memory-50, 0) * 0.5
    score -= max(disk-70, 0) * 0.3
    score -= len(idle_apps) * 0.5
    score -= len(heavy_apps) * 0.5
    return max(int(score), 0)

# -----------------------------
# AI Recommendations
# -----------------------------
def ask_ai(cpu, memory, disk, idle_apps, heavy_apps):
    issues = []
    if cpu>80: issues.append("High CPU")
    if memory>80: issues.append("High Memory")
    if disk>90: issues.append("Disk almost full")
    
    idle_names = [name for name, _ in idle_apps]
    prompt=f"""
    Laptop stats:
    CPU: {cpu}%
    Memory: {memory}%
    Disk: {disk}%
    Idle apps (>7 days): {idle_names}
    Background heavy apps: {heavy_apps}
    Issues detected: {issues}

    Suggest actionable cleanup steps, apps to uninstall, temp files to delete, and optimizations.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Recommendations unavailable: {e}"

# -----------------------------
# Clean temp files
# -----------------------------
def clean_temp_files():
    temp_dir = os.getenv("TEMP")
    try:
        shutil.rmtree(temp_dir)
        return "Temporary files cleaned ✅"
    except Exception as e:
        return f"Failed to clean temp files: {e}"

# -----------------------------
# Predictive trends
# -----------------------------
def predict_usage(df):
    df = df.copy()
    df['TimeInt'] = range(len(df))
    predictions = {}
    for metric in ["CPU","Memory","Disk"]:
        X = df[['TimeInt']]
        y = df[metric]
        model = LinearRegression().fit(X,y)
        future_X = pd.DataFrame({'TimeInt': range(len(df), len(df)+7)})
        predictions[metric] = model.predict(future_X)
    return predictions

# -----------------------------
# Basic URL safety check (fallback)
# -----------------------------
def safe_url_check(url):
    try:
        result = urlparse(url)
        if all([result.scheme, result.netloc]):
            try:
                r = requests.head(url, timeout=5)
                if r.status_code >= 400:
                    return f"⚠️ URL reachable but returned status {r.status_code}"
                else:
                    return "✅ URL reachable, seems safe (basic check)"
            except:
                return "⚠️ URL could not be reached. Be cautious!"
        else:
            return "⚠️ Invalid URL format"
    except:
        return "⚠️ Error parsing URL. Be cautious!"

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("🖥️ AI Laptop Optimizer v5 - Safe URL & AI Fallback")

cpu, memory, disk = get_system_stats()

# Metrics
st.subheader("Current Metrics")
st.metric("CPU Usage", f"{cpu}%")
st.metric("Memory Usage", f"{memory}%")
st.metric("Disk Usage", f"{disk}%")

# Apps
idle_apps = get_idle_apps()
heavy_apps = get_heavy_background_apps()

st.subheader("Idle Apps (>7 days)")
if idle_apps:
    for name, last_used in idle_apps:
        st.write(f"{name} - Last Used: {last_used.strftime('%Y-%m-%d')}")
else:
    st.write("No apps detected")

st.subheader("Background Heavy Apps (low CPU)")
st.write(heavy_apps if heavy_apps else "No heavy idle apps detected")

# Health Score
health = calculate_health(cpu, memory, disk, idle_apps, heavy_apps)
st.subheader("Laptop Health Score")
st.progress(health)
st.write(f"Score: {health}/100")

# AI Recommendations
st.subheader("AI Recommendations")
st.write(ask_ai(cpu, memory, disk, idle_apps, heavy_apps))

# Cleanup button
if st.button("Clean Temporary Files"):
    st.write(clean_temp_files())

# Historical trends
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    st.subheader("Metrics Over Time")
    fig = px.line(df, x="Time", y=["CPU","Memory","Disk"],
                  labels={"value":"Usage (%)","Time":"Time"}, title="System Metrics Over Time")
    st.plotly_chart(fig, use_container_width=True)

    # Predictive trends
    st.subheader("Predicted Metrics (Next 7 Intervals)")
    preds = predict_usage(df)
    pred_df = pd.DataFrame(preds)
    pred_df['Time'] = pd.date_range(start=pd.to_datetime(df['Time'].iloc[-1]), periods=8, freq='H')[1:]
    fig_pred = px.line(pred_df, x="Time", y=["CPU","Memory","Disk"], title="Predicted Metrics")
    st.plotly_chart(fig_pred, use_container_width=True)

# -----------------------------
# URL Safety Check
# -----------------------------
st.subheader("🔗 URL Safety Checker")
url_input = st.text_input("Enter URL to check:")

if url_input:
    try:
        # Attempt AI check first
        prompt = f"Check if the URL is safe: {url_input}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        )
        st.write(response.choices[0].message.content)
    except:
        # Fallback if quota exceeded or error
        st.write(safe_url_check(url_input))