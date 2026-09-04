/**
 * API Client
 * ===========
 * All backend fetch calls in one place.
 * Every function returns parsed JSON.
 */

const API_BASE = "http://localhost:8000";

export async function runPipeline() {
  const res = await fetch(`${API_BASE}/api/run-pipeline`, { method: "POST" });
  if (!res.ok) throw new Error(`Pipeline failed: ${res.statusText}`);
  return res.json();
}

export async function getSummary() {
  const res = await fetch(`${API_BASE}/api/summary`);
  return res.json();
}

export async function getPlays() {
  const res = await fetch(`${API_BASE}/api/plays`);
  return res.json();
}

export async function getPlayDetail(playId) {
  const res = await fetch(`${API_BASE}/api/plays/${playId}`);
  return res.json();
}

export async function executePlay(playId) {
  const res = await fetch(`${API_BASE}/api/plays/${playId}/execute`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Execution failed");
  }
  return res.json();
}

export async function askCopilot(question) {
  const res = await fetch(`${API_BASE}/api/copilot/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return res.json();
}

export async function generateReasoning() {
  const res = await fetch(`${API_BASE}/api/copilot/generate-reasoning`, {
    method: "POST",
  });
  return res.json();
}

export async function getAssumptions() {
  const res = await fetch(`${API_BASE}/api/assumptions`);
  return res.json();
}

export async function getAuditLog() {
  const res = await fetch(`${API_BASE}/api/audit-log`);
  return res.json();
}

export async function getConfigStatus() {
  const res = await fetch(`${API_BASE}/api/config/status`);
  if (!res.ok) throw new Error("Failed to fetch configuration status");
  return res.json();
}

export async function saveLlmKey({ provider = "gemini", api_key }) {
  const res = await fetch(`${API_BASE}/api/config/llm-key`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, api_key }),
  });
  if (!res.ok) throw new Error("Failed to save LLM key");
  return res.json();
}

export async function saveRazorpayConfig({ key_id, key_secret, webhook_secret }) {
  const res = await fetch(`${API_BASE}/api/config/razorpay`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key_id, key_secret, webhook_secret }),
  });
  if (!res.ok) throw new Error("Failed to save Razorpay credentials");
  return res.json();
}

export async function seedSampleData() {
  const res = await fetch(`${API_BASE}/api/seed`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to seed sample data");
  return res.json();
}

export async function uploadTransactionsFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload-transactions`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload transactions file");
  }
  return res.json();
}

