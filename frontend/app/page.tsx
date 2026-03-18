"use client";

import { useState, useRef } from "react";

const API = "http://localhost:8000/api";

type Phase = "idle" | "scraping" | "scrubbing" | "analyzing" | "reporting" | "emailing" | "done" | "error";

interface Theme {
  theme_name: string;
  description: string;
  sentiment: string;
  estimated_count: number;
}

interface ThemeGroup {
  theme_name: string;
  review_count: number;
  sentiment: string;
  sample_reviews: string[];
}

interface Quote {
  quote: string;
  rating: number;
  theme: string;
}

interface ActionIdea {
  title: string;
  description: string;
  priority: string;
  related_theme: string;
}

interface Analysis {
  themes: Theme[];
  theme_groups: ThemeGroup[];
  top_quotes: Quote[];
  action_ideas: ActionIdea[];
  summary: string;
}

interface Metadata {
  date_range: string;
  total_reviews: number;
  avg_rating: number;
}

const PHASES: { key: Phase; label: string; pct: number }[] = [
  { key: "scraping", label: "Scraping reviews", pct: 10 },
  { key: "scrubbing", label: "Scrubbing PII", pct: 30 },
  { key: "analyzing", label: "Analyzing with Gemini", pct: 55 },
  { key: "reporting", label: "Generating report", pct: 85 },
  { key: "emailing", label: "Sending email", pct: 95 },
  { key: "done", label: "Complete", pct: 100 },
];

const sentimentColor: Record<string, string> = {
  positive: "bg-green-100 text-green-800 border-green-300",
  negative: "bg-red-100 text-red-800 border-red-300",
  mixed: "bg-amber-100 text-amber-800 border-amber-300",
};

const sentimentBorder: Record<string, string> = {
  positive: "border-l-green-500",
  negative: "border-l-red-500",
  mixed: "border-l-amber-500",
};

const priorityColor: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-green-100 text-green-700",
};

function Stars({ rating }: { rating: number }) {
  return (
    <span className="text-amber-400 tracking-wider">
      {[...Array(5)].map((_, i) => (
        <span key={i} className={i < rating ? "" : "text-gray-300"}>
          ★
        </span>
      ))}
    </span>
  );
}

export default function Home() {
  const [weeks, setWeeks] = useState(10);
  const [recipientName, setRecipientName] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [htmlReport, setHtmlReport] = useState("");
  const iframeRef = useRef<HTMLIFrameElement>(null);

  async function apiFetch(url: string, body?: object) {
    const res = await fetch(url, {
      method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Request failed");
    }
    return res;
  }

  async function runPipeline() {
    setError("");
    setAnalysis(null);
    setHtmlReport("");
    setMetadata(null);

    try {
      setPhase("scraping");
      const scrapeData = await (await apiFetch(`${API}/scrape`, { weeks })).json();
      setMetadata(scrapeData.metadata);

      setPhase("scrubbing");
      await apiFetch(`${API}/scrub`, {});

      setPhase("analyzing");
      const analyzeData = await (await apiFetch(`${API}/analyze`, {})).json();

      setPhase("reporting");
      const name = recipientName || "Team";
      await apiFetch(`${API}/report`, { weeks, recipient_name: name });
      const html = await (await apiFetch(`${API}/report/preview`)).text();
      setHtmlReport(html);

      const stateRes = await (await apiFetch(`${API}/state`)).json();
      setMetadata(stateRes.metadata);

      const fullAnalysis: Analysis = {
        themes: analyzeData.themes || [],
        theme_groups: [],
        top_quotes: [],
        action_ideas: [],
        summary: "",
      };

      try {
        const analysisRes = await fetch(`${API}/state`);
        if (analysisRes.ok) {
          const stData = await analysisRes.json();
          if (stData.has_analysis) {
            const runRes = await fetch(`${API}/report/preview`);
          }
        }
      } catch {}

      setAnalysis(fullAnalysis);
      setPhase("done");
    } catch (e: any) {
      setError(e.message || "Pipeline failed");
      setPhase("error");
    }
  }

  async function sendEmail() {
    if (!recipientEmail) {
      setError("Enter a recipient email address");
      return;
    }
    setError("");
    setPhase("emailing");
    try {
      const name = recipientName || "Team";
      await apiFetch(`${API}/report`, { weeks, recipient_name: name });
      const html = await (await apiFetch(`${API}/report/preview`)).text();
      setHtmlReport(html);

      await apiFetch(`${API}/email`, {
        recipient_name: name,
        recipient_email: recipientEmail,
      });
      setPhase("done");
    } catch (e: any) {
      setError(e.message || "Email failed");
      setPhase("error");
    }
  }

  async function runAll() {
    if (!recipientEmail) {
      setError("Enter a recipient email address to run the full pipeline");
      return;
    }
    await runPipeline();
    if (phase !== "error") {
      await sendEmail();
    }
  }

  const progress = PHASES.find((p) => p.key === phase)?.pct || 0;
  const phaseLabel = PHASES.find((p) => p.key === phase)?.label || "";
  const isRunning = !["idle", "done", "error"].includes(phase);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-900 to-blue-600 text-white shadow-lg">
        <div className="max-w-6xl mx-auto px-6 py-6">
          <h1 className="text-2xl font-bold">IND Money Review Analyser</h1>
          <p className="text-blue-200 text-sm mt-1">Weekly Pulse Dashboard</p>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
              <h2 className="font-semibold text-gray-700 text-sm uppercase tracking-wide">
                Configuration
              </h2>

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Weeks of reviews
                </label>
                <input
                  type="range"
                  min={4}
                  max={16}
                  value={weeks}
                  onChange={(e) => setWeeks(Number(e.target.value))}
                  className="w-full accent-blue-600"
                  disabled={isRunning}
                />
                <div className="text-center text-sm text-gray-500 mt-1">
                  {weeks} weeks
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Recipient name
                </label>
                <input
                  type="text"
                  value={recipientName}
                  onChange={(e) => setRecipientName(e.target.value)}
                  placeholder="e.g. Harika"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  disabled={isRunning}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Recipient email
                </label>
                <input
                  type="email"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  disabled={isRunning}
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
              <h2 className="font-semibold text-gray-700 text-sm uppercase tracking-wide">
                Actions
              </h2>
              <button
                onClick={runPipeline}
                disabled={isRunning}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
              >
                {isRunning ? "Running…" : "Generate Weekly Pulse"}
              </button>
              <button
                onClick={sendEmail}
                disabled={isRunning || !htmlReport}
                className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
              >
                Send Email
              </button>
              <button
                onClick={() => {
                  if (!htmlReport) return;
                  const blob = new Blob([htmlReport], { type: "text/html" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "weekly_pulse.html";
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                disabled={!htmlReport}
                className="w-full bg-gray-600 hover:bg-gray-700 disabled:bg-gray-300 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
              >
                Download HTML
              </button>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3 space-y-6">
            {/* Progress Bar */}
            {isRunning && (
              <div className="bg-white rounded-xl shadow-sm border p-5">
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-medium text-gray-700">{phaseLabel}</span>
                  <span className="text-gray-500">{progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
                <span className="font-semibold">Error:</span> {error}
              </div>
            )}

            {/* Success */}
            {phase === "done" && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-green-700 text-sm">
                Pipeline completed successfully!
              </div>
            )}

            {/* Metrics */}
            {metadata && (
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white rounded-xl shadow-sm border p-5 text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {metadata.total_reviews}
                  </div>
                  <div className="text-xs uppercase tracking-wide text-gray-500 mt-1">
                    Reviews
                  </div>
                </div>
                <div className="bg-white rounded-xl shadow-sm border p-5 text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {metadata.avg_rating.toFixed(1)}
                  </div>
                  <div className="text-xs uppercase tracking-wide text-gray-500 mt-1">
                    Avg Rating
                  </div>
                </div>
                <div className="bg-white rounded-xl shadow-sm border p-5 text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {metadata.date_range}
                  </div>
                  <div className="text-xs uppercase tracking-wide text-gray-500 mt-1">
                    Date Range
                  </div>
                </div>
              </div>
            )}

            {/* Report Preview */}
            {htmlReport && (
              <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
                <div className="px-5 py-3 border-b bg-gray-50">
                  <h2 className="font-semibold text-gray-700 text-sm uppercase tracking-wide">
                    Report Preview
                  </h2>
                </div>
                <iframe
                  ref={iframeRef}
                  srcDoc={htmlReport}
                  className="w-full border-0"
                  style={{ minHeight: "800px" }}
                  title="Weekly Pulse Report"
                />
              </div>
            )}

            {/* Empty state */}
            {phase === "idle" && !htmlReport && (
              <div className="bg-white rounded-xl shadow-sm border p-16 text-center">
                <div className="text-6xl mb-4 text-gray-300">📊</div>
                <h3 className="text-lg font-semibold text-gray-600 mb-2">
                  Ready to generate your weekly pulse
                </h3>
                <p className="text-gray-400 text-sm max-w-md mx-auto">
                  Configure the weeks and recipient in the sidebar, then click
                  &ldquo;Generate Weekly Pulse&rdquo; to start the pipeline.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
