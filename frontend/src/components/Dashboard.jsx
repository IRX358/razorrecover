import { useState, useEffect } from "react";
import {
  runPipeline,
  getSummary,
  getPlays,
  generateReasoning,
  clearData,
  getAgentStatus,
  toggleAgentStatus,
} from "../api";
import MetricFunnel from "./MetricFunnel";
import PlayCard from "./PlayCard";
import Copilot from "./Copilot";
import DataSourcePanel from "./DataSourcePanel";
import {
  RefreshCw,
  Search,
  CheckCircle2,
  Loader2,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  ShieldOff,
  RotateCcw,
} from "lucide-react";
import crystalMonolith from "../assets/icn1.png";


export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [plays, setPlays] = useState([]);
  const [playsSummary, setPlaysSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pipelineRun, setPipelineRun] = useState(false);
  const [reasoningLoading, setReasoningLoading] = useState(false);
  const [dataSourceOpen, setDataSourceOpen] = useState(true);
  const [currentSource, setCurrentSource] = useState(null);
  const [agentActive, setAgentActive] = useState(true);
  const [agentToggling, setAgentToggling] = useState(false);

  // Load initial summary & agent status on mount
  useEffect(() => {
    getSummary()
      .then((data) => {
        setSummary(data);
        if (data && data.total_payments > 0) {
          loadPlays();
          setCurrentSource("Sample Database");
          setDataSourceOpen(false); // Compact mode if data is already present
        } else {
          // Empty or fresh DB: show clean start screen with Data Ingestion selector open
          setPipelineRun(false);
          setDataSourceOpen(true);
          setPlays([]);
          setPlaysSummary(null);
          setCurrentSource(null);
        }
      })
      .catch(() => {
        setPipelineRun(false);
        setDataSourceOpen(true);
      });

    refreshAgentStatus();
  }, []);

  const refreshAgentStatus = async () => {
    try {
      const res = await getAgentStatus();
      if (res && typeof res.active === "boolean") {
        setAgentActive(res.active);
      }
    } catch (err) {}
  };

  // Sync state whenever policy changes in copilot chat or background
  useEffect(() => {
    const handlePolicyChange = () => refreshAgentStatus();
    window.addEventListener("agent-policy-updated", handlePolicyChange);
    return () => window.removeEventListener("agent-policy-updated", handlePolicyChange);
  }, []);

  const handleToggleAgent = async () => {
    setAgentToggling(true);
    try {
      const res = await toggleAgentStatus(!agentActive);
      setAgentActive(res.active);
    } catch (err) {
      console.error("Failed to toggle agent:", err);
    } finally {
      setAgentToggling(false);
    }
  };

  const handleResetData = async () => {
    if (window.confirm("Clear all transactions and return to the data ingestion start screen?")) {
      setLoading(true);
      try {
        await clearData();
        setSummary(null);
        setPlays([]);
        setPlaysSummary(null);
        setPipelineRun(false);
        setCurrentSource(null);
        setDataSourceOpen(true); // Open the Data Source selection panel on start screen
      } catch (err) {
        console.error("Failed to clear data:", err);
      } finally {
        setLoading(false);
      }
    }
  };

  const loadPlays = async () => {
    try {
      const playsData = await getPlays();
      setPlays(playsData);
      if (playsData.length > 0) {
        setPlaysSummary({
          total_recoverable: playsData.reduce(
            (sum, p) => sum + (p.eligible_recovery || 0),
            0
          ),
          total_expected_recovery: playsData.reduce(
            (sum, p) => sum + (p.expected_recovery || 0),
            0
          ),
          plays_generated: playsData.length,
        });
        setPipelineRun(true);
      }
    } catch (err) {
      console.error("Error loading plays:", err);
    }
  };

  const handleRunPipeline = async () => {
    setLoading(true);
    try {
      const result = await runPipeline();
      setSummary(result.summary);
      setPlaysSummary(result.play_summary);
      setPipelineRun(true);

      // Load plays
      const playsData = await getPlays();
      setPlays(playsData);

      // Generate LLM reasoning
      setReasoningLoading(true);
      await generateReasoning();
      const updatedPlays = await getPlays();
      setPlays(updatedPlays);
      setReasoningLoading(false);
    } catch (err) {
      console.error("Pipeline error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDataLoaded = async ({ source, pipeline, fileName }) => {
    const sourceLabel = source === "upload" ? `File: ${fileName}` : source === "api" ? "Razorpay API" : "Sample Data";
    setCurrentSource(sourceLabel);
    if (pipeline) {
      setSummary(pipeline.summary);
      setPlaysSummary(pipeline.play_summary);
      setPipelineRun(true);
      await loadPlays();
    } else {
      await handleRunPipeline();
    }
    setDataSourceOpen(false); // Collapse to compact bar once data loads
  };

  const handlePlayExecuted = async () => {
    await loadPlays();
    try {
      const updatedSummary = await getSummary();
      setSummary(updatedSummary);
    } catch (err) {
      console.error("Failed to refresh summary after execution:", err);
    }
  };

  return (
    <div className="dashboard-root">
      {/* Top Navbar: Clean, no duplicate buttons */}
      <header className="navbar">
        <div className="navbar-brand">
          <div className="brand-logo-wrapper">
            <img src={crystalMonolith} alt="RazorRecover Logo" className="brand-logo" />
          </div>
          <div className="brand-text">
            <div className="brand-title-wrap">
              <span className="brand-name">RazorRecover</span>
              <span className="brand-tag">FINTECH AI</span>
            </div>
            <span className="brand-desc">
              Autonomous Revenue Recovery Engine • Made for RazorPay Buildathon
            </span>
          </div>
        </div>

        <div className="navbar-actions">
          {/* Interactive Master Toggle for Autonomous Reactive Agent */}
          <button
            type="button"
            className={`nav-agent-toggle-btn ${agentActive ? "agent-on" : "agent-off"}`}
            onClick={handleToggleAgent}
            disabled={agentToggling}
            title={agentActive ? "Click to Pause Reactive Agent" : "Click to Turn ON Reactive Agent"}
          >
            {agentActive ? (
              <ShieldCheck size={14} className="agent-toggle-icon text-success" />
            ) : (
              <ShieldOff size={14} className="agent-toggle-icon text-muted" />
            )}
            <span className="agent-toggle-text">Reactive Agent:</span>
            <span className={`agent-toggle-status ${agentActive ? "status-on" : "status-off"}`}>
              {agentActive ? "ON" : "OFF"}
            </span>
            <span className={`agent-toggle-switch ${agentActive ? "switched-on" : "switched-off"}`}>
              <span className="agent-toggle-switch-thumb" />
            </span>
          </button>

          {pipelineRun ? (
            <>
              <div className="nav-status-pill">
                <span className="status-live-dot" />
                <span>{currentSource || "Active Pipeline"}</span>
              </div>

              {/* Reset Data Button to return to clean state at any time */}
              <button
                type="button"
                className="btn-nav-reset"
                onClick={handleResetData}
                disabled={loading}
                title="Clear all transactions and return to clean data ingestion"
              >
                <RotateCcw size={13} />
                <span>Reset Data</span>
              </button>

              {/* Single primary button to re-run analysis */}
              <button
                className={`btn-nav-primary ${loading ? "loading" : ""}`}
                onClick={handleRunPipeline}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 size={14} className="spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <RefreshCw size={14} />
                    <span>Re-Run Analysis</span>
                  </>
                )}
              </button>
            </>
          ) : (
            <div className="nav-ready-badge">
              <Sparkles size={13} />
              <span>Ready for Ingestion</span>
            </div>
          )}
        </div>
      </header>

      {/* Main Container */}
      <main className="dashboard-main">
        {/* Onboarding & 3 Data Input Options Panel */}
        <DataSourcePanel
          isOpen={dataSourceOpen}
          onToggle={() => setDataSourceOpen(!dataSourceOpen)}
          onDataLoaded={handleDataLoaded}
          currentSource={currentSource}
        />

        {/* Metric Funnel Section */}
        {summary && pipelineRun && (
          <section className="section-funnel-area">
            <MetricFunnel summary={summary} playsSummary={playsSummary} />

            {/* Precision KPI Counters */}
            <div className="kpi-counters-bar">
              <div className="kpi-cell">
                <span className="kpi-num">
                  {summary.total_payments?.toLocaleString("en-IN") || 0}
                </span>
                <span className="kpi-label">Audited Transactions</span>
              </div>
              <div className="kpi-divider" />
              <div className="kpi-cell">
                <span className="kpi-num">
                  {summary.by_recovery_status?.ELIGIBLE?.toLocaleString("en-IN") || 0}
                </span>
                <span className="kpi-label">Eligible Leak Events</span>
              </div>
              <div className="kpi-divider" />
              <div className="kpi-cell">
                <span className="kpi-num">{plays.length}</span>
                <span className="kpi-label">Actionable Plays</span>
              </div>
              <div className="kpi-divider" />
              <div className="kpi-cell">
                <span className="kpi-num">
                  {summary.by_state?.FAILED || 0}
                </span>
                <span className="kpi-label">Failed State Events</span>
              </div>
            </div>
          </section>
        )}

        {/* 2-Column Split: Plays (Left) + Sticky Copilot (Right) */}
        {pipelineRun ? (
          <div className="split-workspace">
            {/* Left Column: Ranked Recovery Plays Feed */}
            <section className="column-plays">
              <div className="plays-feed-header">
                <div>
                  <h2 className="feed-title">Ranked Recovery Plays</h2>
                  <p className="feed-subtitle">
                    Sequenced by Expected Recoverable Rupee (₹) Impact
                  </p>
                </div>

                {reasoningLoading && (
                  <div className="reasoning-indicator">
                    <Loader2 size={13} className="spin" />
                    <span>Copilot synthesizing reasoning...</span>
                  </div>
                )}
              </div>

              <div className="plays-stack">
                {plays.length > 0 ? (
                  plays.map((play, index) => (
                    <PlayCard
                      key={play.id}
                      play={play}
                      rank={index + 1}
                      onExecuted={handlePlayExecuted}
                    />
                  ))
                ) : (
                  <div className="empty-plays-notice">
                    <CheckCircle2 size={24} className="text-success" />
                    <h4>Zero Recoverable Leaks Detected</h4>
                    <p>All scanned payment batches are performing within normal tolerance.</p>
                  </div>
                )}
              </div>
            </section>

            {/* Right Column: Sticky Copilot Window */}
            <aside className="column-copilot-sticky">
              <Copilot onPolicyChange={refreshAgentStatus} />
            </aside>
          </div>
        ) : (
          /* Initial State before data is loaded - Fully Showcases crystalMonolith (icn1.png) Artwork */
          !loading && (
            <div className="hero-showcase-panel">
              <div className="hero-showcase-content">
                <div className="hero-tag-wrap">
                  <Search size={14} />
                  <span>AUTONOMOUS RECOVERY PLATFORM</span>
                </div>

                <h2 className="hero-showcase-title">
                  Stop Leaving Money on the Payment Gateway
                </h2>
                <p className="hero-showcase-lead">
                  Standard dashboards report failure rates like <em>82.4%</em>.
                  RazorRecover digs deeper: classifying recoverable drops, spot-checking
                  bank timeouts, and delivering bounded recovery actions with quantified ₹ returns.
                </p>

                <div className="hero-action-hint">
                  <span className="hint-arrow"><ArrowRight size={15} /></span>
                  <span>Select an Ingestion Method above (Drop CSV, Connect API, or click Sample Data) to launch the engine.</span>
                </div>

                {/* 4 Architecture Pillars */}
                <div className="hero-architecture-grid">
                  <div className="hero-arch-card">
                    <span className="arch-num">01</span>
                    <h6>Two-Dimensional Classifier</h6>
                    <p>Distinguishes terminal fails from recoverable errors</p>
                  </div>
                  <div className="hero-arch-card">
                    <span className="arch-num">02</span>
                    <h6>Z-Score Anomaly Radar</h6>
                    <p>Identifies bank-specific UPI timeout clusters</p>
                  </div>
                  <div className="hero-arch-card">
                    <span className="arch-num">03</span>
                    <h6>Deterministic Scorer</h6>
                    <p>Calculates expected ₹ return using transparent assumptions</p>
                  </div>
                  <div className="hero-arch-card">
                    <span className="arch-num">04</span>
                    <h6>Bounded Action Copilot</h6>
                    <p>Executes retries and disputes with strict audit logging</p>
                  </div>
                </div>
              </div>

              {/* Fully Displayed, Attractive 3D Crystal Prism Monolith Artwork (icn1.png) */}
              <div className="hero-artwork-stage">
                <div className="artwork-glow-pedestal" />
                <img
                  src={crystalMonolith}
                  alt="RazorRecover Crystal Monolith"
                  className="hero-prism-monolith"
                />
                <div className="artwork-badge">
                  <span className="badge-crystal-dot" />
                  <span>Deterministic Heuristic Engine</span>
                </div>
              </div>
            </div>
          )
        )}
      </main>
    </div>
  );
}
