import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8')

# Test 1: Simulate a webhook event
print("=" * 60)
print("TEST 1: Reactive Agent — Simulate Webhook")
print("=" * 60)
r = requests.post("http://localhost:8000/api/agent/simulate")
d = r.json()
sp = d["simulated_payment"]
ad = d["agent_decision"]
print(f"Payment: {sp['id']} | Rs.{sp['amount']} | {sp['method']} | {sp['bank']} | {sp['error']}")
print(f"Decision: Tier {ad['tier']} | {ad['decision']}")
print(f"Reason: {ad['reason']}")
print()

# Run 3 more simulations
for i in range(3):
    r2 = requests.post("http://localhost:8000/api/agent/simulate")
    d2 = r2.json()
    sp2 = d2["simulated_payment"]
    ad2 = d2["agent_decision"]
    print(f"Sim {i+2}: Rs.{sp2['amount']:.0f} {sp2['method']}/{sp2['bank']} -> Tier {ad2['tier']} {ad2['decision']}")

# Test 2: Agent activity feed
print()
print("=" * 60)
print("TEST 2: Agent Activity Feed")
print("=" * 60)
r = requests.get("http://localhost:8000/api/agent/activity")
activity = r.json()
print(f"Total decisions logged: {len(activity)}")
for a in activity[:5]:
    print(f"  [{a['timestamp'][:19]}] Tier {a['tier']} | {a['decision']} | {a['reason'][:70]}...")

# Test 3: Policy control via Copilot chat
print()
print("=" * 60)
print("TEST 3: Conversational Policy Control")
print("=" * 60)

# Disable card retries
r = requests.post("http://localhost:8000/api/copilot/ask", json={"question": "turn off auto-retry for card failures"})
d = r.json()
print(f"Command: 'turn off auto-retry for card failures'")
print(f"Response: {d['answer']}")
if "policy_update" in d:
    print(f"Policy: {d['policy_update']['policy_key']} -> enabled={d['policy_update']['enabled']}")

# Set amount cap on UPI retries
print()
r = requests.post("http://localhost:8000/api/copilot/ask", json={"question": "only auto-retry UPI failures under 500"})
d = r.json()
print(f"Command: 'only auto-retry UPI failures under 500'")
print(f"Response: {d['answer']}")
if "policy_update" in d:
    print(f"Policy: {d['policy_update']['policy_key']} -> max_amount={d['policy_update']['max_amount']}")

# Re-enable card retries
print()
r = requests.post("http://localhost:8000/api/copilot/ask", json={"question": "enable auto-retry for card decline"})
d = r.json()
print(f"Command: 'enable auto-retry for card decline'")
print(f"Response: {d['answer']}")
if "policy_update" in d:
    print(f"Policy: {d['policy_update']['policy_key']} -> enabled={d['policy_update']['enabled']}")

# Normal copilot question (should NOT trigger policy control)
print()
r = requests.post("http://localhost:8000/api/copilot/ask", json={"question": "where am I losing the most money?"})
d = r.json()
has_policy = "policy_update" in d
print(f"Normal question: 'where am I losing the most money?'")
print(f"Policy triggered: {has_policy} (should be False)")
print(f"Answer: {d['answer'][:120]}...")

# Test 4: Feedback Agent
print()
print("=" * 60)
print("TEST 4: Feedback Agent (execute plays first)")
print("=" * 60)

# Get plays and execute the first 4
r = requests.get("http://localhost:8000/api/plays")
plays = r.json()
print(f"Available plays: {len(plays)}")

executed = 0
for p in plays[:4]:
    er = requests.post(f"http://localhost:8000/api/plays/{p['id']}/execute")
    if er.status_code == 200:
        ed = er.json()
        print(f"  Executed: {p['segment_key']} -> {ed['status']} | recovered Rs.{ed['actual_recovered']}")
        if "feedback" in ed:
            fb = ed["feedback"]
            print(f"    Feedback: {fb['calibrations']} calibration(s) — {fb['message']}")
        executed += 1
    else:
        print(f"  Skipped: {p['segment_key']} -> {er.json().get('detail', 'error')}")

# Manual feedback run
print()
r = requests.post("http://localhost:8000/api/feedback/run")
fb = r.json()
print(f"Manual feedback run: {fb['message']}")
if fb.get("details"):
    for cal in fb["details"]:
        print(f"  Calibrated: {cal['cause_type']} | {cal['old_rate']} -> {cal['new_rate']} (drift={cal['drift']}, n={cal['sample_size']})")

# Check policies now
print()
print("=" * 60)
print("TEST 5: Final Policy State")
print("=" * 60)
r = requests.get("http://localhost:8000/api/agent/policies")
for p in r.json():
    cap = f" (max Rs.{p['max_amount']})" if p['max_amount'] else ""
    print(f"  {p['policy_key']}: {'ON' if p['enabled'] else 'OFF'}{cap} [by: {p['updated_by']}]")

print()
print("ALL TESTS COMPLETE")
