# RazorRecover

> **Autonomous Revenue Recovery & Payment Intelligence Engine**  
> *Built for the Razorpay Buildathon*

**RazorRecover** is an autonomous revenue recovery layer that sits natively between merchants and Razorpay's payment infrastructure. It intercepts live transaction failures, isolates recoverable bank glitches from permanent customer drop-offs, calculates exact rupee recovery potential, and triggers bounded, automated actions to recapture lost revenue before customers walk away.

---

## Essential Documentation

Before diving into setup, explore the complete engineering blueprints and development story:

- **[System Architecture Blueprint](./docs%20n%20ss/architecture.md)** — Deep dive into our 1:1 Razorpay schema parity, 2D classification engine, mathematical scoring formulas, and 3-tier safety guardrails.
- **[The Build Journey](./docs%20n%20ss/buildjourney.md)** — The complete engineering chronicle: from initial napkin sketches and research to building the deterministic core and evolving the autonomous agentic layers.

---

## The Problem & The Solution

### The Problem in Traditional Dashboards
Standard payment gateways comfort merchants with numbers like **"82.4% Success Rate"**. But that missing 17.6% silently bleeds lakhs of rupees every single month:
- Dashboards dump unhelpful technical errors like `GATEWAY_ERROR` or `BAD_REQUEST`.
- Merchants can't tell if a customer gave up or if an HDFC UPI server choked for 60 seconds.
- By the time operations teams review monthly spreadsheets, authorized payments have expired, dispute deadlines have passed, and customers are gone.

### The RazorRecover Solution
RazorRecover converts passive failure logs into active recovered rupees:
1. **2D Classification**: Decouples payment status from recoverability—filtering out permanent user typos (`INVALID_VPA`) and isolating transient leaks (`UPI_TIMEOUT`, uncaptured authorizations).
2. **Statistical Anomaly Radar**: Uses rolling Z-score clustering ($Z \ge 2.0\sigma$) to spot abnormal failure spikes on specific bank and method routes.
3. **Ranked Recovery Plays**: Sequences actionable opportunities by expected ₹ impact rather than abstract percentages.
4. **Autonomous Execution**: Fires smart retries, routing changes, and captures within seconds—governed by strict cryptographic idempotency and circuit breakers.

![RazorRecover End-to-End Pipeline Architecture](./docs%20n%20ss/ss/pipeline_architecture_diagram.jpg)

---

## The 3 Agentic Superpowers

1. **Autonomous Reactive Recovery Agent**  
   Monitors incoming webhooks in real time. Across a **3-tier safety matrix**, small, high-confidence payments (under ₹5,000) are automatically retried in under 5 seconds. To prevent spamming customers during widespread bank outages, a built-in **Circuit Breaker** automatically halts retries if a segment's failure rate crosses 90% in 10 minutes.
   
2. **Conversational Policy Control**  
   Merchants shouldn't have to navigate confusing settings menus to adjust automation. By simply typing into the chat—*"Turn off auto-retry for card failures"* or *"Turn off reactive agent"*—deterministic pattern matching updates bounded policy records in the database, flipping the navbar toggle **ON/OFF in real time**. The LLM never decides the rules; it only sets the dials.

3. **Gated Dual-Mode AI Copilot (Zero-Hallucination)**  
   Powered by **Google Gemini 3.6 Flash** (with Anthropic Claude fallback). In fintech, an LLM must never calculate financial math. All revenue figures, confidence percentages, and anomaly sigmas are pre-computed in Python. The LLM is strictly fenced in to weave clear business explanations around verified facts. If external APIs experience high-demand spikes, the system automatically retries with backoff or falls back to rule-based heuristics.

4. **Closed-Loop Feedback Agent (Self-Calibration)**  
   Static recovery assumptions drift over time. Every time an action is executed, the engine compares predicted recovery against what the bank actually settled. If drift exceeds 10%, a 60/40 weighted blend auto-calibrates baseline assumptions. The platform gets smarter with every transaction it processes.

---

## Quick Start & Setup Guide

RazorRecover is built as a lightweight, high-performance full-stack application:
- **Backend**: Python 3.10+, FastAPI, SQLAlchemy ORM, Pandas, SciPy
- **Frontend**: React 19, Vite, Lucide-React, Glassmorphic Design System

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/RazorRecover.git
cd RazorRecover
```

### 2. Backend Setup
```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv venv

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
# source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
pip install google-genai

# Start the FastAPI dev server (port 8000)
uvicorn main:app --reload
```
The backend will be live at `http://127.0.0.1:8000` (API docs available at `http://127.0.0.1:8000/docs`).

### 3. Frontend Setup
```bash
# Open a new terminal in the frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server (port 5173)
npm run dev
```
Open your browser and navigate to **`http://localhost:5173`**.

---

## Configuration & API Keys

You have two flexible options for configuring API keys:

### Option A: Direct In-App Configuration (Recommended & Zero-Setup)
You don't need to manually create `.env` files before running the project!
1. **Razorpay Credentials**: Click on the **"1. Connect Razorpay Account"** card on the dashboard landing screen to paste your `Key ID`, `Key Secret`, and optional `Webhook Secret`.
2. **AI Engine Keys**: Click the **Settings icon (⚙️)** in the top right of the Copilot chat drawer to select your preferred provider (**Google Gemini 3.6 Flash** or **Anthropic Claude**) and enter your API key. Keys are dynamically saved and active immediately.

### Option B: Backend `.env` File (Persistent)
Alternatively, you can create a `.env` file inside the `backend/` directory:
```env
# Server
HOST=127.0.0.1
PORT=8000

# Razorpay Credentials
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

# AI & LLM Providers (Gemini 3.6 Flash is default)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

---

## Testing with Sample & Custom Data

You can immediately test the entire autonomous pipeline without connecting a live payment gateway:
1. **Clean Start**: Click **"Reset Data"** in the top navbar to return to the fresh ingestion state.
2. **Drag-and-Drop Dataset**: Drag `docs n ss/test_data/custom_transactions.csv` directly into the ingestion dropzone.
3. **Execute Plays**: Click **"Execute Play"** on any ranked card and watch the **"Actually Recovered"** funnel metric update live with bank-verified funds.
4. **Chat Governance**: Type *"turn off reactive agent"* in the Copilot chat and watch the master toggle flip to **OFF** in real time.

---

<div align="center">
  <sub>Built with curiosity — Irfan IR</sub>
</div>
