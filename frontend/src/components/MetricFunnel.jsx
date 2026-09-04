import { ArrowRight, AlertTriangle, CheckCircle2, TrendingUp, Sparkles } from "lucide-react";

/**
 * MetricFunnel
 * =============
 * The four-tier revenue recovery hierarchy:
 *   Revenue at Risk → Recoverable → Expected Recovery → Actually Recovered
 * Sleek crystal cuts, high-authority Razorpay dark blue, crystal glass blue, and white.
 */

export default function MetricFunnel({ summary, playsSummary }) {
  const atRisk = summary?.revenue_at_risk || 0;
  const recoverable = playsSummary?.total_recoverable || 0;
  const expected = playsSummary?.total_expected_recovery || 0;
  const actualRecovered = 0; // Updated dynamically after action execution

  const metrics = [
    {
      id: "risk",
      label: "Revenue at Risk",
      value: atRisk,
      icon: <AlertTriangle size={15} className="metric-icon risk-icon" />,
      colorClass: "stat-risk",
      description: "Total leaking across all states",
    },
    {
      id: "recoverable",
      label: "Recoverable Pool",
      value: recoverable,
      icon: <Sparkles size={15} className="metric-icon rec-icon" />,
      colorClass: "stat-recoverable",
      description: "Actionable failure volume",
    },
    {
      id: "expected",
      label: "Expected Recovery",
      value: expected,
      icon: <TrendingUp size={15} className="metric-icon exp-icon" />,
      colorClass: "stat-expected",
      description: "Model-discounted projection",
    },
    {
      id: "recovered",
      label: "Actually Recovered",
      value: actualRecovered,
      icon: <CheckCircle2 size={15} className="metric-icon act-icon" />,
      colorClass: "stat-recovered",
      description: "Verified bank confirmation",
    },
  ];

  return (
    <div className="metric-funnel">
      {metrics.map((m, i) => (
        <div key={m.id} className={`funnel-card ${m.colorClass}`}>
          {i > 0 && (
            <div className="funnel-connector">
              <ArrowRight size={13} />
            </div>
          )}
          <div className="funnel-header">
            <span className="funnel-label">{m.label}</span>
            {m.icon}
          </div>
          <div className="funnel-value">
            {formatRupees(m.value)}
          </div>
          <div className="funnel-desc">{m.description}</div>
        </div>
      ))}
    </div>
  );
}

export function formatRupees(amount) {
  if (amount == null || isNaN(amount)) return "₹0";
  if (amount >= 10000000) {
    return `₹${(amount / 10000000).toFixed(2)} Cr`;
  }
  if (amount >= 100000) {
    return `₹${(amount / 100000).toFixed(2)} L`;
  }
  if (amount >= 1000) {
    return `₹${(amount / 1000).toFixed(1)}k`;
  }
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}
