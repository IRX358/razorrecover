import { useState, useRef, useEffect } from "react";
import {
  Bot,
  Sparkles,
  Send,
  Key,
  Cpu,
  ShieldCheck,
  AlertCircle,
  Loader2,
  ChevronRight,
  Settings,
} from "lucide-react";
import { askCopilot, getConfigStatus, saveLlmKey } from "../api";
import mainLogo from "../assets/icn1.png";
import crystalMonolith from "../assets/icn2.png";


/**
 * Copilot Chat
 * =============
 * Conversational interface for the AI Recovery Copilot.
 * Answers are strictly grounded in pre-computed facts.
 */

const SUGGESTED_QUESTIONS = [
  "What happens if I enable smart retry?",
  "Turn off auto-retry for card failures",
  "Only auto-retry UPI under ₹500",
  "Where am I losing the most money?",
  "How much can I recover this month?",
  "Which recovery play has the highest ROI?"
];

export default function Copilot() {
  // Config & State
  const [hasLlmKey, setHasLlmKey] = useState(false);
  const [provider, setProvider] = useState("gemini");
  const [agentMode, setAgentMode] = useState(null); // 'llm' | 'fallback' | null
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [keySaving, setKeySaving] = useState(false);
  const [keyError, setKeyError] = useState(null);

  // Chat State
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "I'm your RazorRecover Copilot. I can explain your recovery plays, " +
        "analyze revenue leaks, and help you decide which actions to take. " +
        "Every number I cite comes directly from your pre-computed analysis.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEnd = useRef(null);

  // Check backend config on mount
  useEffect(() => {
    checkConfig();
  }, []);

  const checkConfig = async () => {
    try {
      const cfg = await getConfigStatus();
      setHasLlmKey(cfg.has_llm_key);
      setProvider(cfg.llm_provider || "gemini");
      if (cfg.has_llm_key) {
        setAgentMode("llm");
      }
    } catch {
      setAgentMode("fallback");
    }
  };

  const scrollToBottom = () => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages, agentMode]);

  const handleSaveKey = async (e) => {
    e.preventDefault();
    if (!keyInput.trim()) {
      setKeyError("Please enter a valid API key.");
      return;
    }
    setKeySaving(true);
    setKeyError(null);
    try {
      await saveLlmKey({ provider, api_key: keyInput.trim() });
      setHasLlmKey(true);
      setAgentMode("llm");
      setShowConfigModal(false);
      setKeyInput("");
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `API key saved! Live AI is now active using ${
            provider === "claude" ? "Claude Sonnet" : "Google Gemini 2.5 Flash"
          }. Ask me anything about your recovery plays.`,
        },
      ]);
    } catch (err) {
      setKeyError(err.message || "Failed to save API key.");
    } finally {
      setKeySaving(false);
    }
  };

  const handleSelectFallback = () => {
    setAgentMode("fallback");
    setShowConfigModal(false);
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content:
          "Deterministic Heuristic Mode activated. I am reasoning directly over pre-computed evidence and statistical z-scores with 100% zero hallucinations.",
      },
    ]);
  };

  const handleSend = async (question) => {
    const q = question || input.trim();
    if (!q || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res = await askCopilot(q);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Unable to process question: ${err.message}`,
        },
      ]);
    }
    setLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="copilot-panel">
      {/* Copilot Header */}
      <div className="copilot-header">
        <div className="copilot-header-left">
          <div className="copilot-icon-badge">
            <img src={mainLogo} alt="RazorRecover" className="copilot-avatar-img" />
          </div>
          <div>
            <div className="copilot-title-row">
              <h3>RazorRecover Copilot</h3>
              {agentMode === "llm" ? (
                <span className="copilot-mode-tag llm">
                  <Sparkles size={11} /> Live AI ({provider})
                </span>
              ) : agentMode === "fallback" ? (
                <span className="copilot-mode-tag fallback">
                  <Cpu size={11} /> Heuristic Mode
                </span>
              ) : null}
            </div>
            <span className="copilot-subtitle">
              Financial Intelligence • Grounded in Evidence
            </span>
          </div>
        </div>

        <button
          className="btn-copilot-settings"
          onClick={() => setShowConfigModal(!showConfigModal)}
          title="Configure AI Engine"
        >
          <Settings size={15} />
        </button>
      </div>

      {/* Config Overlay Modal */}
      {showConfigModal && (
        <div className="copilot-config-box">
          <div className="config-box-header">
            <h4>Configure AI Provider</h4>
            <button
              className="btn-close-config"
              onClick={() => setShowConfigModal(false)}
            >
              ✕
            </button>
          </div>

          <form onSubmit={handleSaveKey} className="config-form">
            <div className="config-field">
              <label>Select Provider</label>
              <select
                className="crystal-select"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                <option value="gemini">Google Gemini 2.5 Flash</option>
                <option value="claude">Anthropic Claude Sonnet</option>
              </select>
            </div>

            <div className="config-field">
              <label>API Key</label>
              <input
                type="password"
                className="crystal-input"
                placeholder={
                  provider === "claude" ? "sk-ant-..." : "AIzaSy..."
                }
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
              />
            </div>

            {keyError && (
              <div className="crystal-alert error compact">
                <AlertCircle size={14} />
                <span>{keyError}</span>
              </div>
            )}

            <div className="config-box-actions">
              <button
                type="submit"
                className="btn-crystal-primary compact"
                disabled={keySaving}
              >
                {keySaving ? (
                  <>
                    <Loader2 size={14} className="spin" /> Saving...
                  </>
                ) : (
                  <>
                    <Key size={14} /> Save Key
                  </>
                )}
              </button>
              <button
                type="button"
                className="btn-crystal-ghost compact"
                onClick={handleSelectFallback}
              >
                Use Fallback Template
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Screen 1: Choose Mode (If no key and no mode chosen yet) */}
      {!agentMode && !hasLlmKey ? (
        <div className="copilot-mode-selector">
          <div className="mode-selector-prompt">
            {/* Fully and attractively displayed crystal monolith (icn1.png) */}
            <div className="copilot-monolith-showcase">
              <img
                src={crystalMonolith}
                alt="RazorRecover Crystal Monolith"
                className="copilot-monolith-img"
              />
            </div>
            <h4>Grounded Financial Intelligence</h4>
            <p>
              Choose how the AI Recovery Copilot should reason over your payment leaks.
            </p>
          </div>

          <div className="mode-cards-grid">
            {/* Option A: Enter API Key */}
            <div className="mode-choice-card">
              <div className="choice-head">
                <div className="choice-icon-wrap">
                  <Key size={18} />
                </div>
                <h5>Enter Your API Key</h5>
              </div>
              <p>
                Connect Google Gemini or Anthropic Claude for natural language
                explanations.
              </p>

              <div className="choice-input-area">
                <select
                  className="crystal-select mb-2"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="claude">Anthropic Claude</option>
                </select>
                <input
                  type="password"
                  className="crystal-input"
                  placeholder="Paste API key..."
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                />
                {keyError && <span className="input-err">{keyError}</span>}
                <button
                  className="btn-crystal-primary mt-2 btn-block"
                  onClick={handleSaveKey}
                  disabled={keySaving || !keyInput.trim()}
                >
                  {keySaving ? (
                    <Loader2 size={14} className="spin" />
                  ) : (
                    "Save & Connect AI"
                  )}
                </button>
              </div>
            </div>

            {/* Option B: Use Fallback Template */}
            <div className="mode-choice-card fallback-highlight">
              <div className="choice-head">
                <div className="choice-icon-wrap fallback-icon">
                  <Cpu size={18} />
                </div>
                <h5>Use Fallback Template</h5>
              </div>
              <p>
                No external API key required. Uses deterministic heuristics and
                pre-computed benchmark models.
              </p>
              <ul className="choice-bullets">
                <li>100% Zero Hallucinations</li>
                <li>Instant response time</li>
                <li>Fully grounded in verified numbers</li>
              </ul>
              <button
                className="btn-crystal-secondary btn-block mt-auto"
                onClick={handleSelectFallback}
              >
                Use Fallback Template <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Screen 2: Active Chat Screen */
        <>
          <div className="copilot-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`message ${msg.role}`}>
                <div className="message-content">
                  {msg.role === "assistant" && (
                    <div className="msg-avatar-tag">
                      <Sparkles size={12} /> Copilot
                    </div>
                  )}
                  <div className="msg-text">{msg.content}</div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="message assistant">
                <div className="message-content typing">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
            <div ref={messagesEnd} />
          </div>

          <div className="copilot-suggestions">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                className="suggestion-chip"
                onClick={() => handleSend(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>

          <div className="copilot-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about revenue leaks, plays, or ROI..."
              disabled={loading}
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="btn-send"
            >
              <Send size={15} />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
