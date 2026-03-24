# 🖥️ AI Laptop Optimizer v4

**AI Laptop Optimizer v4** is a full-featured Python application that monitors your laptop performance, predicts future resource usage, and provides actionable AI-driven recommendations for cleanup and optimization. This project combines system monitoring, predictive analytics, and AI insights into a single dashboard using **Streamlit**.

---

## 🔹 Features

- **Real-time System Monitoring**  
  - CPU, Memory, Disk usage with live metrics
  - Desktop notifications for high resource usage

- **AI-Driven Recommendations**  
  - Suggestions for system optimization using OpenAI API
  - Cleanup steps, apps to uninstall, and temp files to delete

- **Idle & Heavy Background App Detection**  
  - Identifies apps unused for 7+ days
  - Detects heavy background apps consuming resources

- **Laptop Health Score**  
  - Score out of 100 based on CPU, memory, disk usage, idle apps, and heavy apps

- **Historical Trends & Predictive Analytics**  
  - Visualize resource usage over time
  - Predict next 7 intervals for CPU, Memory, and Disk usage

- **Automatic Temporary File Cleanup**  
  - One-click deletion of temp files

- **URL Safety Check (AI-based)**  
  - Evaluate whether a website is risky before visiting

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **Libraries**
  - `psutil` - system resource monitoring
  - `streamlit` - interactive dashboard
  - `plotly` - metrics visualization
  - `pandas` - data handling
  - `shutil` & `os` - file operations
  - `sklearn` - predictive analytics
  - `win10toast` - desktop notifications
  - `openai` - AI recommendations
- **OpenAI GPT-4o-mini** for AI-based suggestions

---

## ⚡ Installation

1. Clone this repository:

```bash
git clone https://github.com/BhavanaVuttunoori/AI-Laptop-Optimizer.git
cd AI-Laptop-Optimizer
````

2. Install required libraries:

```bash
pip install -r requirements.txt
```

3. Set your OpenAI API key (Windows example):

```powershell
setx OPENAI_API_KEY "your_openai_api_key_here"
```

4. Run the app:

```bash
streamlit run app.py
```

---

## 📊 Usage

1. Open the app in your browser (Streamlit will auto-launch).
2. Monitor **CPU, Memory, and Disk** usage in real-time.
3. View **Idle apps** and **Background heavy apps**.
4. Check **Laptop Health Score**.
5. Get **AI Recommendations** for cleanup and optimization.
6. Click **Clean Temporary Files** to free up space.
7. View **Historical Metrics** and **Predicted Trends**.
8. Optional: Enter a URL to check if it is safe.

---

## 🔒 AI Integration

* Uses **OpenAI GPT-4o-mini** model to provide personalized suggestions.
* Generates:

  * Cleanup steps
  * Apps to uninstall
  * Temp files to delete
  * Optimization recommendations

---

## 🖼️ Screenshots

*(Add screenshots of your Streamlit dashboard here if possible)*

---

## 💡 Future Enhancements

* Real-time virus/malware detection for risky URLs
* Deep Windows EXE analysis using AI
* Automated app uninstallation for unused programs
* Custom notifications and optimization suggestions

---

## 📄 License

This project is **open-source** and free to use.

---

**Created by Bhavana Vuttunoori**

