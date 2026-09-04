import { useState, useEffect } from "react";
import {
  runPipeline,
  getSummary,
  getPlays,
  generateReasoning,
  seedSampleData,
} from "../api";
import MetricFunnel from "./MetricFunnel";
import PlayCard from "./PlayCard";
import Copilot from "./Copilot";
import DataSourcePanel from "./DataSourcePanel";
import {
  Zap,
  Play,
  RefreshCw,
  Sliders,
  TrendingUp,
  Database,
  Search,
  Sparkles,
  ShieldAlert,
  Loader2,
  Layers,
  ArrowRight,
} from "lucide-react";
import icn1 from "../assets/icn1.jpg";
import bg1 from "../assets/bg1.jpg";
import bg2 from "../assets/bg2.jpg";

/**
 * Dashboard
 * ==========
 * The command center for RazorRecover.
 * Answers the three critical merchant questions:
 *   1. How much revenue is leaking?
 *   2. How much is recoverable?
 *   3. What exact play should I execute first?
 */

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [plays, setPlays] = useState([]);
  const [playsSummary, setPlaysSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pipelineRun, setPipelineRun] = useState(false);
  const [reasoningLoading, setReasoningLoading] = useState(false);
  const [dataSourceOpen, setDataSourceOpen] = useState(true);
  const [currentSource, setCurrentSource] = useState("sample");

  // Load initial summary & plays on mount
  useEffect(() => {
    getSummary()
      .then((data) => {
        setSummary(data);
        if (data.total_payments > 0) {
          loadPlays();
          setDataSourceOpen(false); // Auto-collapse data source once data exists
        }
      })
      .catch(() => {});
  }, []);

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
    setCurrentSource(source === "upload" ? `File: ${fileName}` : source);
    if (pipeline) {
      setSummary(pipeline.summary);
      setPlaysSummary(pipeline.play_summary);
      setPipelineRun(true);
      await loadPlays();
    } else {
      await handleRunPipeline();
    }
    setDataSourceOpen(false); // collapse panel to reveal results
  };

  const handlePlayExecuted = () => {
    loadPlays();
  };

  return (
    <div className="dashboard-root">
      {/* Subtle Crystal Backdrop Elements */}
      <div
        className="crystal-bg-glow crystal-glow-left"
        style={{ backgroundImage: `url(${bg1})` }}
      />
      <div
        className="crystal-bg-glow crystal-glow-right"
        style={{ backgroundImage: `url(${bg2})` }}
      />

      {/* Top Navbar */}
      <header className="navbar">
        <div className="navbar-brand">
          <div className="brand-logo-wrapper">
            <img src={icn1} alt="RazorRecover Logo" className="brand-logo" />
          </div>
          <div className="brand-text">
            <div className="brand-title-wrap">
              <span className="brand-name">RazorRecover</span>
              <span className="brand-tag">FINTECH AI</span>
            </div>
            <span className="brand-desc">
              Autonomous Revenue Recovery Engine • Powered by Razorpay
            </span>
          </div>
        </div>

        <div className="navbar-actions">
          <button
            className="btn-nav-outline"
            onClick={() => setDataSourceOpen(!dataSourceOpen)}
          >
            <Database size={15} />
            <span>Data Ingestion</span>
          </button>

          <button
            className={`btn-nav-primary ${loading ? "loading" : ""}`}
            onClick={handleRunPipeline}
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 size={15} className="spin" />
                <span>Analyzing Leaks...</span>
              </>
            ) : (
              <>
                <Play size={15} />
                <span>
                  {pipelineRun ? "Re-Run Pipeline" : "Run Recovery Pipeline"}
                </span>
              </>
            )}
          </button>
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
        {summary && (
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
              <Copilot />
            </aside>
          </div>
        ) : (
          /* Empty / Initial State before scan */
          !loading && (
            <div className="initial-hero-card">
              <div className="hero-badge">
                <Search size={14} />
                <span>ENGINE READY FOR SCAN</span>
              </div>

              <h2>Identify & Quantify Your Payment Leaks</h2>
              <p className="hero-lead">
                Choose an ingestion option above — upload your gateway transaction export,
                connect live Razorpay API keys, or load the pre-computed benchmark dataset
                to run root-cause anomaly detection.
              </p>

              <div className="hero-cta-row">
                <button
                  className="btn-crystal-primary lg"
                  onClick={handleRunPipeline}
                >
                  <Play size={16} /> Run Discovery Scan
                </button>
                <button
                  className="btn-crystal-ghost lg"
                  onClick={() => setDataSourceOpen(true)}
                >
                  <Database size={16} /> Choose Ingestion Source
                </button>
              </div>

              <div className="hero-architecture-steps">
                <div className="arch-step">
                  <span className="step-num">01</span>
                  <span className="step-title">Two-Dimensional Classifier</span>
                  <span className="step-desc">Distinguishes terminal fails from recoverable errors</span>
                </div>
                <div className="arch-step">
                  <span className="step-num">02</span>
                  <span className="step-title">Z-Score Anomaly Radar</span>
                  <span className="step-desc">Identifies localized cluster drops across banks & methods</span>
                </div>
                <div className="arch-step">
                  <span className="step-num">03</span>
                  <span className="step-title">Deterministic Scorer</span>
                  <span className="step-desc">Calculates expected ₹ return using transparent assumptions</span>
                </div>
                <div className="arch-step">
                  <span className="step-num">04</span>
                  <span className="step-title">Autonomous Recovery Copilot</span>
                  <span className="step-desc">Executes bounded actions with real-time audit logging</span>
                </div>
              </div>
            </div>
          )
        )}
      </main>
    </div>
  );
}
