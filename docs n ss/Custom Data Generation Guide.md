# Custom Data Generation Guide for RazorRecover

To test RazorRecover against your own scenarios or simulate a different merchant's transaction profile, you can generate a custom CSV dataset and upload it via the frontend's **"Drop a CSV or XLSX"** zone.

## Required CSV Format

Your CSV file must contain the following exact columns. (This strictly follows the Razorpay Payment API schema):

| Column Name | Type | Description / Allowed Values |
| :--- | :--- | :--- |
| `payment_id` | String | Unique ID, e.g., `pay_ABCD1234567890` |
| `order_id` | String | Unique ID, e.g., `order_XYZ0987654321` |
| `amount` | Float | Transaction amount in INR (e.g., `1500.00`) |
| `status` | String | `created`, `authorized`, `captured`, `refunded`, `failed` |
| `captured` | Boolean | `True` or `False` (Must be `True` if status is captured) |
| `method` | String | `upi`, `card`, `netbanking`, `wallet` |
| `bank` | String | `HDFC`, `SBI`, `ICICI`, `AXIS`, etc. (Can be empty for cards) |
| `error_source` | String | `gateway`, `customer`, `bank`, `business` (Empty for successes) |
| `error_step` | String | `payment_authorization`, `payment_processing` (Empty for successes) |
| `error_reason` | String | The exact failure reason (see supported list below) |
| `created_at` | ISO Date | e.g., `2026-09-01T10:00:00Z` |

## Supported `error_reason` Values

RazorRecover's deterministic classification engine relies on specific error reasons to map failures to actionable "Leak Categories". If you want the system to find recoverable revenue, you must use these specific reasons:

### 1. Recoverable via Smart Retry (Tier 1 & Tier 2)
- `upi_timeout`: Temporary bank downtime (Highly recoverable).
- `gateway_timeout`: The payment gateway did not respond in time.
- `server_error`: 500 Internal Server Error at the bank.
- `gateway_error`: Generic gateway failure.

### 2. Recoverable via Route Change (Tier 2)
- `card_declined`: Standard bank decline.
- `card_declined_risk`: Gateway flagged as risk (often routable via 3DS).
- `payment_failed`: Generic failure.

### 3. NOT Recoverable (Terminal Loss)
- `user_cancelled`: The customer closed the checkout tab.
- `insufficient_funds`: The customer's account is empty.
- `invalid_vpa`: Typo in the UPI ID.

## Prompt to Generate Test Data with AI

If you want to generate a synthetic dataset using an AI (like ChatGPT, Claude, or Gemini), copy and paste this exact prompt:

```text
Act as a Python data engineer. I need a script to generate a CSV dataset of 500 simulated Razorpay payment transactions. 

The CSV must contain these columns exactly: 
['payment_id', 'order_id', 'amount', 'status', 'captured', 'method', 'bank', 'error_source', 'error_step', 'error_reason', 'created_at']

Rules for the data generation:
1. Generate dates sequentially over the last 7 days.
2. 70% of the transactions should be successful (status: 'captured', captured: True, error fields empty).
3. 30% of the transactions should be failures (status: 'failed', captured: False).
4. For the failures, create a massive statistical anomaly (a "cluster") to test my anomaly detection engine: 
   - 60% of all failures should specifically be method: 'upi', bank: 'HDFC', error_reason: 'upi_timeout', error_source: 'bank'.
   - 20% should be method: 'card', error_reason: 'card_declined_risk', error_source: 'gateway'.
   - 20% should be random noise (user_cancelled, insufficient_funds, etc.).
5. Randomize amounts between 100.00 and 15000.00.

Output the full, executable Python script using the 'csv' and 'random' standard libraries to generate 'custom_transactions.csv'. Do not use external libraries like pandas.
```

## How to Test the Agentic Behaviors

To truly test the **Feedback Agent** and **Reactive Agent**, your data needs to trigger them:

1. **Reactive Agent (Auto-Execute):** Ensure you have failures where `amount` is under ₹5,000 and the error is `upi_timeout` (which yields a high confidence score of 0.90). The Reactive Agent will auto-execute these as Tier 1.
2. **Circuit Breaker:** If you upload a CSV where almost *all* recent payments for a specific bank are failing with `upi_timeout`, the Circuit Breaker will trip (status OPEN) and halt auto-retries for that bank to prevent a rate-limit storm.
3. **Feedback Agent (Assumption Calibration):** The engine expects `upi_timeout` retries to succeed ~60% of the time based on assumptions. After you generate plays and execute them, the feedback loop will compare the actual simulated recovery against the 60% assumption and automatically recalibrate the engine.
