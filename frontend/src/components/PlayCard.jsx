import { useState } from "react";
import {
  Zap,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ShieldAlert,
  Layers,
  ArrowRight,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import { executePlay } from "../api";
import { formatRupees } from "./MetricFunnel";

/**
 * PlayCard
 * =========
 * The core product object: an actionable, bounded Recovery Play.
 * Engineered for high clarity, precision cuts, and glassmorphism.
 */

const ACTION_LABELS = {
  retry: "Smart Retry Failed Payments",
  route_change: "Re-Route Gateway Traffic",
  contest_with_evidence: "Contest Dispute with Evidence",
  capture_payment: "Capture Authorization",
  escalate_to_razorpay: "Escalate to Razorpay Support",
  investigate_product: "Investigate Product Issue",
};

const LEAK_LABELS = {
  upi_timeout: "UPI Timeout Cluster",
  card_decline: "Card Decline Pattern",
  gateway_error: "Gateway Error Spike",
  settlement_delay: "Settlement Delay Bottleneck",
  dispute: "Contestable Chargeback Dispute",
  uncaptured: "Uncaptured Authorization Leak",
  refund_surge: "Refund Surge Pattern",
};

export default function PlayCard({ play, rank, onExecuted }) {
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleExecute = async () => {
    setExecuting(true);
    try {
      const res = await executePlay(play.id);
      setResult(res);
      if (onExecuted) onExecuted(res);
    } catch (err) {
      setResult({ status: "error", error: err.message });
    }
    setExecuting(false);
    setShowConfirm(false);
  };

  const confidencePercent = Math.round((play.diagnosis_confidence || 0) * 100);
  const isExecutable = play.status === "pending" && !result;

  return (
    <div className={`play-card ${result ? "play-executed" : ""}`}>
      {/* Top Meta Bar */}
      <div className="play-header">
        <div className="play-header-left">
          <span className="play-rank-badge">RANK #{rank}</span>
          <span className="play-leak-badge">
            <ShieldAlert size={12} className="inline-icon" />
            {LEAK_LABELS[play.leak_category] || play.leak_category}
          </span>
        </div>

        <div className="play-confidence-wrap">
          <span className="confidence-dot" />
          <span className="confidence-text">{confidencePercent}% Diagnosis Confidence</span>
        </div>
      </div>

      {/* Segment Name */}
      <h3 className="play-segment">
        {play.segment_key?.replace(/_/g, " × ") || "Unsegmented Cluster"}
      </h3>

      {/* 3-Pillar Financial Metrics */}
      <div className="play-metrics-grid">
        <div className="play-metric-cell risk">
          <span className="cell-label">Revenue at Risk</span>
          <span className="cell-value">{formatRupees(play.affected_amount)}</span>
        </div>
        <div className="play-metric-cell eligible">
          <span className="cell-label">Eligible Pool</span>
          <span className="cell-value">{formatRupees(play.eligible_recovery)}</span>
        </div>
        <div className="play-metric-cell expected">
          <span className="cell-label">Expected Recovery</span>
          <span className="cell-value highlight">{formatRupees(play.expected_recovery)}</span>
        </div>
      </div>

      {/* Reasoning Engine Output */}
      {play.reasoning && (
        <div className="play-reasoning-box">
          <div className="reasoning-header">
            <Layers size={13} />
            <span>Copilot Root-Cause Diagnosis</span>
          </div>
          <p className="reasoning-text">{play.reasoning}</p>
        </div>
      )}

      {/* Action Trigger Bar */}
      <div className="play-action-bar">
        <div className="play-action-info">
          <div className="action-tag">
            <Zap size={14} className="action-zap-icon" />
            <span className="action-name">
              {ACTION_LABELS[play.action_type] || play.action_type}
            </span>
          </div>
          <span className="efficiency-rating">
            Efficiency Score: {Math.round(play.recovery_efficiency_score || 0).toLocaleString("en-IN")}
          </span>
        </div>

        {result ? (
          <div className={`execution-result-pill ${result.status}`}>
            {result.status === "verified" ? (
              <>
                <CheckCircle2 size={15} />
                <span>Verified: {formatRupees(result.actual_recovered)}</span>
              </>
            ) : result.status === "partial" ? (
              <>
                <AlertCircle size={15} />
                <span>Partial Recovery ({result.forecast_accuracy}%)</span>
              </>
            ) : (
              <>
                <XCircle size={15} />
                <span>{result.error || "Action Blocked"}</span>
              </>
            )}
          </div>
        ) : showConfirm ? (
          <div className="inline-confirm-box">
            <span className="confirm-prompt">
              Execute bounded action for {formatRupees(play.expected_recovery)}?
            </span>
            <div className="confirm-btn-group">
              <button
                className="btn-cancel-sm"
                onClick={() => setShowConfirm(false)}
                disabled={executing}
              >
                Cancel
              </button>
              <button
                className="btn-confirm-sm"
                onClick={handleExecute}
                disabled={executing}
              >
                {executing ? (
                  <>
                    <Loader2 size={13} className="spin" /> Executing...
                  </>
                ) : (
                  <>
                    <ShieldCheck size={13} /> Confirm Execution
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <button
            className="btn-play-execute"
            onClick={() => setShowConfirm(true)}
            disabled={!isExecutable}
          >
            <Zap size={14} />
            <span>{isExecutable ? "Execute Recovery Play" : "Executed"}</span>
          </button>
        )}
      </div>
    </div>
  );
}
