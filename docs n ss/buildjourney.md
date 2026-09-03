# The Build Journey

## The Journey Story 

---> give it a try it's intresting

When I first started thinking about what to build for this buildathon, I didn't want to build just another generic finance app or an accounting dashboard that spits out balance sheets. That's boring, and honestly, merchants already have tools like Tally or QuickBooks for that.

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