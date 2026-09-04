# The Build Journey

## The Journey Story 

---> give it a try it's intresting

So before I even picked this problem, I actually had a completely different idea in mind. 

I was thinking of building an edge / local AI voice payment agent. The whole concept was to create a conversational payment assistant with multilingual speech for people who struggle with conventional digital payment apps—especially older people, people who need accessibility options, or anyone who feels way more comfortable using their local language instead of clicking around confusing screens. The AI would listen to voice instructions, confirm the transaction, and guide the user through the payment step-by-step. 

I was particularly interested in running the AI locally on-device (Edge AI). Running it on device would keep sensitive personal conversations and payment details from being sent over to servers unnecessarily, and it would also cut down latency. 

So that was my plan. But then I saw that Razorpay was already heavily invested in voice-first and conversational commerce through their partnership with Sarvam, and they were already actively announcing it. Once I saw that, I thought of stepping back from it. There was really no point building something Razorpay was already doing and announcing. 

So I stepped back to find a fresh problem.

ANd now , 
I didn't want to build just another generic finance app or an accounting dashboard that spits out balance sheets. That's boring, and honestly, merchants already have tools like Tally or QuickBooks for that.

I wanted to solve an actual friction point inside payment gateways. I kept thinking about how people actually interact with gateway dashboards like Razorpay. If you've ever run an online business or talked to a merchant (business where there is no dedicated tech finance managing person), you know the feeling: you log in, and you can see charts, total volumes, and success rate percentages like "82.4%". 

On paper, 82% sounds okay. But behind the scenes, that missing 17.6% is thousands or even lakhs of rupees just vanishing into the void. When a transaction fails with strings like `GATEWAY_ERROR` or `PAYMENT_TIMED_OUT`, what is a merchant actually supposed to do with that? Do they call the customer? Do they retry? Is the bank down? Or did the customer just abandon the cart?

No dashboard answers the real questions merchants actually care about:
- How much money am I actually losing right now?
- How much of that lost money can I realistically get back?
- What exact button do I press or action do I take first to recover it?

To make sure this wasn't just my own random hypothesis, I spent time researching where merchants actually vent: Reddit (threads on r/developersIndia, r/ecommerce, r/smallbusiness), Quora, and used ai power (perplexity to research abt the same across twitter and other places)

I could see the stories now:
```
   1. “How much revenue are you losing to failed Razorpay payments without knowing it?” – IndianStartups (Mar 24, 2026)
      https://www.reddit.com/r/indianstartups/comments/1s2ro4n/how_much_revenue_are_you_losing_to_failed/
      Directly about invisible losses from failed payments and retry behavior.
      
   2. “How do you actually track revenue lost from payment failures or webhook issues?” – r/SaaS (Jan 30, 2026)
      https://www.reddit.com/r/SaaS/comments/1qrc3tb/how_do_you_actually_track_revenue_lost_from/
      Focuses on lost revenue from failures, retries, and reconciliation gaps rather than just “missing payments.” 
      
    3. Rackz – “Failed payments don’t announce themselves. They just quietly eat 5–10% of your MRR” – @rackzai (profile thread, 2025–2026)
        https://x.com/rackzai
        Describes failed payments as silent revenue loss and highlights detection of failures, renewal risks, and checkout issues
        
   4. “Anyone else annoyed that Razorpay’s dashboard doesn’t show you what you actually keep?” – r/Razorpay (Apr 4, 2026)
        https://www.reddit.com/r/Razorpay/comments/1scahpv/anyone_else_annoyed_that_razorpays_dashboard/
      Merchants frustrated that fees, GST, failed payments, and refunds make the “real” amount unclear.
```

That was the "aha!" moment for me. Razorpay already records the exact failure reasons, error steps, and transaction metadata. The raw data exists. But it sits in isolated rows. It doesn't guide the merchant on what to do.

Once I decided on this problem statement, I also did a thorough research on how Razorpay currently handles merchants. I looked into the webhooks part, the redirection of payment gateway vs the in-app checkout screen, the portals, and all those things. I wanted to understand how Razorpay actually works in these parts because I didn't want to build a separate SaaS application. I wanted to build an integratable extension for current Razorpay's platform.

I wanted to build an active enhancement layer directly on top of Razorpay. Not a dashboard that just shows you more graphs, but a co-pilot that scans the leaks, quantifies them in actual rupees (₹), and hands you a ready-to-execute "Recovery Play." 
I started late , had very less time but started thinking I'll pull off howmuch ever i can and add rest to the "future scope" haha.. (not bad right?)

### Where AI fits in (and why I refused to build an AI gimmick)

I want to be very clear about this: I didn't want to use AI just to make the project look fancy or jump on the trend. 

In financial software, trust is everything. If an AI hallucinates a number, invents an extra zero, or makes up a reason why money was lost, you destroy the merchant's trust instantly. 

So I drew a hard line in the architecture:
The AI is strictly prohibited from doing math, calculating revenue at risk, or ranking opportunities. All of that is handled deterministically by classical Python logic, pandas, rolling z-score anomaly detection, and time-series models. That's the rock-solid ground truth. (Even though I know "AI" is the buzzword of the season, I'm not going to be that guy who just slaps an LLM on top of everything and calls it a day).

The AI's job is purely to bridge the intelligence gap. It acts as the strategist and translator. It takes pre-computed evidence, failure clusters, and financial facts, and explains them in plain, crisp English so the merchant doesn't need to be a payment engineer to make the right decision. It crafts the story behind the leak and lets the merchant ask questions before executing an action.

### The Phases I planned to tackle

To pull this off properly within the buildathon, I mapped out 7 focused phases:
- Phase 1: Foundation & Data Models (building the database schema, the 2D classification engine, and realistic scenario generator)
- Phase 2: Core Analytics & Detection (deterministic classifier, anomaly detection with rolling z-scores, and yield scoring)
- Phase 3: Forecasting & Play Ranking (Holt-Winters projections and ranking plays by expected ₹ recovery)
- Phase 4: AI Copilot & Action Gateway (grounded LLM tool-calling and idempotent execution gateway)
- Phase 5: Frontend Scaffold & API Client (setting up Vite React and connecting clean API calls)
- Phase 6: Dashboard & Visuals (a try to mimic razorpay's UI and the core metric funnel)
- Phase 7: Hero Components & Final Assembly (the Play Cards and interactive Copilot drawer)

Here is the honest log of how each phase went, the bugs I ran into, and how I debugged and built this step-by-step.

---

## Phase-wise Build, Test & Debugging Log

### Phase 1: Foundation & Data Models

Before touching any AI, I needed solid ground. I set up datamodels , sqlite db , a seeder for synthetic data which is not so random but is designed for different failure scenarios with one clear goal: build a realistic data foundation where we actually know the exact right answers beforehand.

Three things I focused on:
- **Two-dimensional classification:** Normal gateways just slap a "Failed" label on a transaction. But that doesn't tell you if money can be saved. Did the customer close the tab (terminal loss, nothing you can do), or did the bank gateway time out (recoverable via retry)? I split this into transaction state vs. recovery status in `RevenueClassification`. This distinction is the backbone of the whole project.
- **No magic numbers:** In fintech, if your system throws around random percentages without explaining where they came from, merchants won't trust it. So I created an `Assumption` table where every single rate is transparent, backed by real sources (like NPCI benchmarks), and editable.
- **Seed data with real ground truth:** Instead of spitting out random garbage data, I designed 5 deliberate scenarios (like HDFC UPI timeouts during peak hours, card declines, and expiring dispute windows). Because I set the scenario rules, I know the expected outcomes. That gave me a real benchmark to evaluate against later.

**How I tested it:**
I seeded the database and checked the record counts. Then I ran a quick "Spike Test" by changing the failure rate from 80% to 10% (simulating a normal healthy day), and re-seeded. The expected number dropped instantly, proving the scenario logic was truly dynamic. Once confirmed, I flipped it back to 80% to keep the benchmark failure cluster ready.

---

### Phase 2: Core Analytics & Detection Engines

Once the raw data was in place, I had to build the engine that actually sorts through it and finds where money is leaking. 

This phase was all about keeping things deterministic and statistically sound:
- **Zero-AI classification:** I wrote an 11-rule deterministic engine in `classification.py`. If a dispute is still open and within the response window, it's eligible. If the timer expired, it's not. If a settlement is past T+2 days, it's delayed. No machine learning guessing games here—fintech numbers need to be 100% auditable.
- **Finding real spikes with Z-scores:** Instead of dumb static alerts like "alert if failures > 10%" (which would constantly trigger false alarms on credit cards while missing silent netbanking outages), I used rolling z-score anomaly detection in `evidence.py`. It groups by bank and payment method, compares the segment against the baseline average, and flags true statistical anomalies where $|z| > 1.5$ or $2.0$.
- **Debugging card declines:** While testing, I caught an interesting edge case: high-value card declines were slipping through as "user abandoned" (non-recoverable). In reality, when cards get declined for risk/gateway reasons, routing through another gateway or 3DS step can salvage them. I fixed that by adding `card_declined` and `card_declined_risk` into the retryable/routable error bucket so they could be surfaced for recovery.
- **Yield scoring:** In `scoring.py`, I linked the anomalies to the assumptions table using our two-step formula: `At Risk -> Eligible (fraction) -> Expected Recovery (effectiveness)`.

**How I tested it:**
I ran the pipeline step-by-step from the terminal. 
First, the classification sorted all 175 payments, filtering Rs. 3.81L at risk down to Rs. 2.98L legitimately eligible for recovery. 
Then the anomaly detector picked up the exact 4 clusters I seeded (HDFC UPI timeouts hit a high $z \approx 1.93$, alongside card declines and settlement delays). 
Finally, the scoring engine priced them out—showing that retrying the UPI cluster alone has an expected recovery of over ₹31,000. Clean, deterministic math all the way through.

see the outputs here - [test o/p image](./ss/phase2tests.png)

---

### Phase 3: Forecasting & Play Ranking

Now that I had the leaks detected and scored, I hit the next big product question: **If a merchant has multiple leaks happening at once, what do they actually do first?**

Most analytics tools fail here. They either dump a list of 20 alerts or just sort by the biggest raw rupee amount. But sorting purely by money is flawed:
- A ₹1,20,000 card decline issue might take weeks of manual risk-rule tuning and only has a 35% win rate.
- Meanwhile, a ₹31,000 UPI timeout cluster has 100% statistical confidence and can be fixed right now with low operational effort.

So I spent this phase building the intelligence that turns raw anomalies into ranked, prioritized "Recovery Plays":
- **Balanced ranking formula:** In `ranking.py`, I weighted each opportunity across three dimensions: 
  $$\text{Score} = 0.5 \times \text{normalized ₹ impact} + 0.3 \times \text{confidence} + 0.2 \times \text{feasibility}$$
  This pushed the high-confidence, low-effort UPI smart retries straight to **#1**, while keeping the harder card declines and disputes lower down where they belong.
- **Holt-Winters time-series projections:** In `forecasting.py`, I used classical exponential smoothing via `statsmodels` to project historical weekly losses 4 weeks into the future. It generates two curves:
  1. *Baseline*: "If you do nothing, you continue bleeding ₹X/week."
  2. *Scenario*: "If you execute this play, the loss curve bends downward by ₹Y."
- **The Batch Evaluation Harness:** To prove this wasn't just working by lucky accident, I wrote `batch_eval.py`—a complete test harness that runs the whole loop end-to-end against the Phase 1 ground truth.

**How I tested it:**
I ran `python batch_eval.py` in the terminal to evaluate the whole pipeline. 
The harness classified the 175 payments, isolated the 4 clusters, generated the 4 ranked plays, and simulated execution.
The result: an **87.8% identification precision** (capturing ₹1,73,900 of the ₹1,98,000 ground truth), predicting ₹93,094 in recovery, and pulling back ₹76,792 in actual recovered funds with an average forecast error of only ~₹4,000. 

see the outputs here - [batch eval report](./ss/batcheval1.png) and [batch eval report](./ss/batcheval2.png)

---

### Phase 4: AI Copilot & Action Gateway

This was the phase where the AI was finally introduced. But remembering the core architectural rule: **The AI is autonomous in analysis, but strictly forbidden from being autonomous with money.**

In fintech, you don't let an LLM do financial math, and you definitely don't let it trigger bank actions unmonitored. So Phase 4 was built around two disciplined components:
- **The Grounded AI Copilot (`copilot.py` & `llm_service.py`):** 
  Instead of asking an LLM "how much can I recover?", all the numbers ($\text{₹}$ amounts, Z-scores, Holt-Winters projections) are pre-computed deterministically by the Python services first. They get injected into the prompt as immutable facts. The LLM's only job is synthesis: translating technical gateway errors into plain business English, explaining *why* a play is recommended, and answering free-form merchant questions without hallucinations.
- **The Gated Action Gateway (`action.py`):**
  An advisor that just talks is just a dashboard with a chat widget. What makes this a co-pilot is the execution button. But before any action can fire, it has to pass through strict safety guardrails:
  1. *Idempotency*: Generates a deterministic SHA-256 key (`play_id:action:segment`). If a network blip or double-click happens, the database UNIQUE constraint stops it dead. No accidental double retries.
  2. *Pre-approved whitelist*: Only vetted action types (`retry`, `route_change`, `capture_payment`, etc.) are executable.
  3. *Stopping rules*: A hard cap of 2 attempts per play, and an immediate kill-switch if diagnosis confidence drops below the 0.3 floor.
  4. *Audit logging*: Every execution writes an immutable before/after snapshot and verified recovery amount to `AuditLog`.

**How I tested it:**
I tested the safety loop directly from the terminal. 
First, I ran the pipeline to generate fresh plays. I checked eligibility on the top UPI retry play—all checks passed. 
Then I executed it: the gateway verified the outcome, logged the recovery of ₹31,038, and updated the state. 
Immediately after, I tried executing it a second time. The idempotency guard caught it instantly and blocked the action (`Play already executed`). 
Finally, I asked the Copilot a free-form question; it parsed the pre-computed play facts and returned a clear, direct recommendation without fabricating a single number.

see the outputs here - [phase 4 test output](./ss/phase4_tests.png)

---



