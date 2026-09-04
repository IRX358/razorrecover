import { useState, useEffect } from "react";
import {
  UploadCloud,
  Key,
  Database,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Download,
  Loader2,
  ShieldCheck,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import {
  uploadTransactionsFile,
  saveRazorpayConfig,
  seedSampleData,
  getConfigStatus,
} from "../api";
import mainLogo from "../assets/icn1.png";
import llmLogo from "../assets/icn2.png";


export default function DataSourcePanel({
  onDataLoaded,
  isOpen,
  onToggle,
  currentSource,
}) {
  const [selectedTab, setSelectedTab] = useState("sample"); // 'upload' | 'api' | 'sample'
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // File Upload State
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  // Razorpay API Credentials State
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [apiConnected, setApiConnected] = useState(false);
  const [maskedKey, setMaskedKey] = useState("");

  useEffect(() => {
    getConfigStatus()
      .then((cfg) => {
        if (cfg.has_razorpay_keys) {
          setApiConnected(true);
          setMaskedKey(cfg.razorpay_key_id);
        }
      })
      .catch(() => {});
  }, []);

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg("Please select a CSV or XLSX file first.");
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    setStatusMsg("Uploading transactions and running recovery engine...");

    try {
      const res = await uploadTransactionsFile(file);
      setStatusMsg(`Successfully imported ${res.records_imported} transactions!`);
      if (onDataLoaded) {
        onDataLoaded({
          source: "upload",
          pipeline: res.pipeline,
          fileName: file.name,
        });
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to upload transactions file.");
    } finally {
      setLoading(false);
    }
  };

  const handleConnectApi = async (e) => {
    e.preventDefault();
    if (!keyId.trim() || !keySecret.trim()) {
      setErrorMsg("Key ID and Key Secret are required.");
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    setStatusMsg("Saving Razorpay API credentials...");

    try {
      const res = await saveRazorpayConfig({
        key_id: keyId.trim(),
        key_secret: keySecret.trim(),
        webhook_secret: webhookSecret.trim(),
      });
      setApiConnected(true);
      setMaskedKey(res.key_id);
      setStatusMsg("Razorpay API successfully connected and saved!");
      if (onDataLoaded) {
        onDataLoaded({ source: "api", keyId: res.key_id });
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to save Razorpay API credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSample = async () => {
    setLoading(true);
    setErrorMsg(null);
    setStatusMsg("Loading 175 synthetic payments and executing pipeline...");

    try {
      const res = await seedSampleData();
      setStatusMsg("Sample data loaded successfully! Recovery pipeline executed.");
      if (onDataLoaded) {
        onDataLoaded({ source: "sample", pipeline: res });
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to load sample data.");
    } finally {
      setLoading(false);
    }
  };

  const downloadSampleTemplate = () => {
    const csvContent =
      "payment_id,order_id,amount,status,method,bank,error_reason,error_source\n" +
      "pay_sample_101,order_101,2500,failed,upi,HDFC,upi_timeout,gateway\n" +
      "pay_sample_102,order_102,8000,failed,card,ICICI,card_declined_risk,bank\n" +
      "pay_sample_103,order_103,1200,captured,upi,SBI,,\n" +
      "pay_sample_104,order_104,5000,failed,upi,HDFC,upi_timeout,gateway\n" +
      "pay_sample_105,order_105,3500,captured,card,Axis,,";
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "razorpay_transactions_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Compact collapsed bar when data is active and panel is toggled closed
  if (!isOpen && currentSource) {
    return (
      <div className="data-source-compact-bar">
        <div className="compact-info">
          <img src={llmLogo} alt="Active Source" className="compact-icon-img" />
          <div className="compact-text">
            <span className="compact-label">ACTIVE INGESTION FEED</span>
            <span className="compact-val">{currentSource.toUpperCase()}</span>
          </div>
        </div>
        <button className="btn-switch-source" onClick={onToggle}>
          <Database size={14} />
          <span>Switch Ingestion Source</span>
        </button>
      </div>
    );
  }

  return (
    <div className="data-source-wrapper">
      {/* Header Banner - Clean, without duplicate toggle buttons */}
      <div className="data-source-banner">
        <div className="banner-info">
          <img src={llmLogo} alt="RazorRecover" className="banner-icon-img" />
          <div>
            <div className="banner-title-row">
              <span className="banner-tag">DATA PIPELINE INPUT</span>
              {currentSource && (
                <span className="source-active-pill">
                  Current: {currentSource.toUpperCase()}
                </span>
              )}
            </div>
            <h3 className="banner-heading">Select Ingestion Method</h3>
            <p className="banner-subtext">
              Choose one of three pathways to feed transactions into the recovery engine.
            </p>
          </div>
        </div>

        {currentSource && (
          <button className="btn-crystal-ghost compact" onClick={onToggle}>
            Keep Current Data
          </button>
        )}
      </div>

      <div className="data-source-container">
        {/* 3 Main Choice Cards */}
        <div className="source-tabs-grid">
          {/* Option 1: CSV / XLSX */}
          <div
            className={`source-tab-card ${
              selectedTab === "upload" ? "active" : ""
            }`}
            onClick={() => {
              setSelectedTab("upload");
              setErrorMsg(null);
            }}
          >
            <div className="tab-card-header">
              <div className="tab-icon-box">
                <FileSpreadsheet size={20} className="tab-icon" />
              </div>
              <span className="tab-badge">Option 1</span>
            </div>
            <h4>Upload CSV / XLSX</h4>
            <p>
              Drop transaction batches exported from your Razorpay dashboard.
            </p>
          </div>

          {/* Option 2: Connect Razorpay API */}
          <div
            className={`source-tab-card ${
              selectedTab === "api" ? "active" : ""
            }`}
            onClick={() => {
              setSelectedTab("api");
              setErrorMsg(null);
            }}
          >
            <div className="tab-card-header">
              <div className="tab-icon-box">
                <Key size={20} className="tab-icon" />
              </div>
              <div className="tab-header-right">
                {apiConnected && (
                  <span className="connected-badge">
                    <CheckCircle2 size={12} /> Connected
                  </span>
                )}
                <span className="tab-badge">Option 2</span>
              </div>
            </div>
            <h4>Connect Razorpay API</h4>
            <p>Configure backend API keys & webhook secrets directly in UI.</p>
          </div>

          {/* Option 3: Sample Data */}
          <div
            className={`source-tab-card ${
              selectedTab === "sample" ? "active" : ""
            }`}
            onClick={() => {
              setSelectedTab("sample");
              setErrorMsg(null);
            }}
          >
            <div className="tab-card-header">
              <div className="tab-icon-box">
                <Database size={20} className="tab-icon" />
              </div>
              <span className="tab-badge recommended">Option 3 (Instant)</span>
            </div>
            <h4>Use Sample Data</h4>
            <p>
              175 payments, 5 scenarios with ~₹1.98L recoverable ground truth.
            </p>
          </div>
        </div>

        {/* Tab Content Panes */}
        <div className="source-content-pane">
          {/* TAB 1: FILE UPLOAD */}
          {selectedTab === "upload" && (
            <div className="tab-pane">
              <div className="pane-header">
                <div>
                  <h5>Upload Transaction Export</h5>
                  <p>
                    Supports standard <code>.csv</code> and <code>.xlsx</code> formats.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-text-action"
                  onClick={downloadSampleTemplate}
                >
                  <Download size={14} /> Download Sample Template
                </button>
              </div>

              <div
                className={`dropzone ${dragOver ? "drag-over" : ""} ${
                  file ? "has-file" : ""
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  if (e.dataTransfer.files?.[0]) {
                    setFile(e.dataTransfer.files[0]);
                  }
                }}
              >
                <UploadCloud size={34} className="dropzone-icon" />
                {file ? (
                  <div className="file-preview-info">
                    <span className="file-name">{file.name}</span>
                    <span className="file-size">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                ) : (
                  <div>
                    <p className="dropzone-text">
                      Drag & drop transaction file here, or{" "}
                      <label className="file-browse-link">
                        browse files
                        <input
                          type="file"
                          accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                          style={{ display: "none" }}
                          onChange={(e) => {
                            if (e.target.files?.[0]) setFile(e.target.files[0]);
                          }}
                        />
                      </label>
                    </p>
                    <span className="dropzone-sub">
                      Expected columns: <code>amount</code>, <code>status</code>, <code>method</code>, <code>bank</code>, <code>error_reason</code>
                    </span>
                  </div>
                )}
              </div>

              <div className="pane-actions">
                <button
                  className="btn-crystal-primary"
                  onClick={handleFileUpload}
                  disabled={loading || !file}
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="spin" /> Importing File...
                    </>
                  ) : (
                    <>
                      <UploadCloud size={16} /> Import & Run Analysis
                    </>
                  )}
                </button>
                {file && (
                  <button
                    className="btn-crystal-ghost"
                    onClick={() => setFile(null)}
                    disabled={loading}
                  >
                    Clear File
                  </button>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: CONNECT RAZORPAY API */}
          {selectedTab === "api" && (
            <form className="tab-pane" onSubmit={handleConnectApi}>
              <div className="pane-header">
                <div>
                  <h5>Configure Razorpay Credentials</h5>
                  <p>
                    Directly updates your backend environment variables for automated polling.
                  </p>
                </div>
                {apiConnected && (
                  <span className="key-active-tag">
                    <ShieldCheck size={14} /> Key ID: {maskedKey}
                  </span>
                )}
              </div>

              <div className="form-grid-3">
                <div className="form-group">
                  <label>
                    Key ID <span className="req">*</span>
                  </label>
                  <input
                    type="text"
                    className="crystal-input"
                    placeholder="rzp_test_..."
                    value={keyId}
                    onChange={(e) => setKeyId(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label>
                    Key Secret <span className="req">*</span>
                  </label>
                  <input
                    type="password"
                    className="crystal-input"
                    placeholder="••••••••••••••••"
                    value={keySecret}
                    onChange={(e) => setKeySecret(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label>Webhook Secret (Optional)</label>
                  <input
                    type="password"
                    className="crystal-input"
                    placeholder="Webhook signing secret"
                    value={webhookSecret}
                    onChange={(e) => setWebhookSecret(e.target.value)}
                  />
                </div>
              </div>

              <div className="pane-actions">
                <button
                  type="submit"
                  className="btn-crystal-primary"
                  disabled={loading || !keyId.trim() || !keySecret.trim()}
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="spin" /> Saving Credentials...
                    </>
                  ) : (
                    <>
                      <Key size={16} /> Save & Connect Razorpay
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* TAB 3: SAMPLE DATA */}
          {selectedTab === "sample" && (
            <div className="tab-pane">
              <div className="sample-info-layout">
                <div className="sample-text-block">
                  <div className="sample-title-badge">
                    <Sparkles size={14} />
                    <span>VERIFIED GROUND TRUTH BENCHMARK</span>
                  </div>
                  <h5>Pre-Seeded Financial Anomaly Dataset</h5>
                  <p>
                    Loads 175 payments across 5 distinct failure scenarios with ₹1,98,000 recoverable ground truth:
                  </p>
                  <ul className="sample-features-list">
                    <li>
                      <strong>Scenario A:</strong> Baseline normal traffic (100 payments, ~5% natural failures).
                    </li>
                    <li>
                      <strong>Scenario B:</strong> HDFC UPI timeout cluster during peak hours (30 payments, 80% fail).
                    </li>
                    <li>
                      <strong>Scenario C:</strong> High-value card declines (&gt;₹5k) with bank risk flags.
                    </li>
                    <li>
                      <strong>Scenario D:</strong> 15 chargeback disputes (8 contestable within response window).
                    </li>
                    <li>
                      <strong>Scenario E:</strong> 10 uncaptured authorizations and refund surges.
                    </li>
                  </ul>
                </div>

                {/* Prominently showcasing the new bg2.png crystal asset */}
                <div className="sample-crystal-showcase">
                  <div className="crystal-artwork-card">
                    <img
                      src={llmLogo}
                      alt="Deterministic Benchmark Crystal"
                      className="crystal-gem-img"
                    />
                    <div className="crystal-stat-overlay">
                      <span className="truth-label">RECOVERABLE TARGET</span>
                      <span className="truth-val">₹1,98,000</span>
                      <span className="truth-sub">Across 4 actionable plays</span>
                    </div>
                  </div>

                  <button
                    className="btn-crystal-primary btn-block"
                    onClick={handleLoadSample}
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <Loader2 size={16} className="spin" /> Executing Pipeline...
                      </>
                    ) : (
                      <>
                        <RefreshCw size={16} /> Load & Run Sample Data
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Status Messages */}
          {statusMsg && (
            <div className="crystal-alert success">
              <CheckCircle2 size={16} />
              <span>{statusMsg}</span>
            </div>
          )}
          {errorMsg && (
            <div className="crystal-alert error">
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
