# SOUL · Installation & Setup Guide

This guide describes how to set up and run the Vietlott Deterministic Universe pipeline from scratch on a new **Windows** or **Linux** machine.

---

## 💻 Windows Setup (New Machine Guide)

If you are on a fresh Windows installation, follow these step-by-step instructions:

### Step 1: Install Git
1. Download the Git for Windows installer from [git-scm.com](https://git-scm.com/download/win).
2. Run the `.exe` installer. You can accept the default options during setup.
3. Once complete, open **Command Prompt** (cmd) and verify it works:
   ```cmd
   git --version
   ```

### Step 2: Install Python 3
1. Download Python 3.10+ (recommend Python 3.11 or 3.12) from [python.org](https://www.python.org/downloads/windows/).
2. **CRITICAL**: Run the installer and check the box at the bottom that says **"Add python.exe to PATH"**. If you skip this, the startup scripts will fail to find Python.
3. Choose **"Install Now"**.
4. To verify the installation, open a new Command Prompt and run:
   ```cmd
   python --version
   ```

### Step 3: Clone the Repository
Open Command Prompt and navigate to where you want the project folder, then clone:
```cmd
git clone https://github.com/just-haku/vietlott.git
cd vietlott
```

### Step 4: Run the Startup Script
Double-click `start.bat` in the project folder, or run it from the Command Prompt:
```cmd
start.bat
```
This batch file will automatically:
1. Create a local Python Virtual Environment (`.venv`).
2. Download and install all required libraries (`flask`, `requests`, etc.).
3. Extract mathematical features (A–L, M1–M7) from raw lottery draws.
4. Launch the web dashboard server.

---

## 🐧 Linux Setup (New Machine Guide)

Follow these steps for Debian/Ubuntu-based distributions:

### Step 1: Install System Packages
Open terminal and install Python, Git, and Pip:
```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv
```

### Step 2: Clone the Repository
```bash
git clone https://github.com/just-haku/vietlott.git
cd vietlott
```

### Step 3: Run the Startup Script
Make sure the script is executable and launch it:
```bash
chmod +x start.sh
./start.sh
```
This shell script will automatically:
1. Create a Python Virtual Environment (`.venv`).
2. Install dependencies using `uv` (if installed) or standard `pip`.
3. Process `dataset_raw.jsonl` to extract math features.
4. Start the dashboard web server.

---

## ⚙️ Running & Configuring the Pipeline

Once the startup script completes, follow these instructions to use the engine:

### 1. Access the Dashboard
Open your web browser and navigate to:
```
http://localhost:5000
```
*(You will see a premium, dark-mode analytics console with leaderboard charts and AI response feeds.)*

### 2. Set Up API Keys
To use the Auto-Research LLM engine:
1. Scroll down to the **Engine Configuration** panel.
2. Select your provider (e.g., **Google Gemini** or **Groq**).
3. Enter your API Key.
4. Click **Save Configuration**. (This writes to a local, git-ignored `config.json` file).

### 3. Kick Off the Research Loop
- Click the **Start Research** button at the top of the dashboard.
- The AI agent will begin generating, testing, and saving formula sets automatically.
- The **AI Response Feed** will show its live reasoning, and the **Leaderboard** will persist the top 5 brains (scoring the lowest entropy on the test set).
