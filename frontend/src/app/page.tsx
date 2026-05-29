"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import {
  TrendingUp,
  AlertTriangle,
  HelpCircle,
  Clock,
  Trash2,
  Moon,
  Sun,
  LayoutGrid,
  Scale,
  RefreshCw,
  Search,
  ExternalLink,
  ChevronDown,
  CheckCircle2,
  XCircle,
  FileSpreadsheet,
  BookOpen,
  DollarSign
} from "lucide-react";
import {
  saveAnalysisAction,
  loadHistoryAction,
  deleteAnalysisAction
} from "./actions";

interface HeadlineMetric {
  actual: string;
  estimate: string;
  yoy_growth: string;
  beat_miss: string;
  citation_span: string;
  confidence: number;
  confidence_reasoning: string;
}

interface SegmentPerformance {
  name: string;
  revenue: string;
  growth: string;
  citation_span: string;
}

interface GuidanceMetric {
  metric: string;
  period: string;
  range_low: string;
  range_high: string;
  range_mid: string;
  citation_span: string;
}

interface SentimentTakeaway {
  text: string;
  citation_span: string;
  confidence: number;
  confidence_reasoning: string;
}

interface FinancialRisk {
  category: string;
  text: string;
  citation_span: string;
  confidence: number;
  confidence_reasoning: string;
}

interface AnalystQuestion {
  text: string;
  premise: string;
  tension: string;
  confidence: number;
  confidence_reasoning: string;
}

interface AnalystReport {
  ticker: string;
  company_name: string;
  period: string;
  headline?: {
    revenue: HeadlineMetric;
    eps: HeadlineMetric;
    operating_margin: HeadlineMetric;
    net_income: HeadlineMetric;
    ticker: string;
    company_name: string;
    period: string;
    release_date: string;
  };
  segments?: SegmentPerformance[];
  guidance?: GuidanceMetric[];
  bull_takeaways?: SentimentTakeaway[];
  bear_takeaways?: SentimentTakeaway[];
  risks?: FinancialRisk[];
  questions?: AnalystQuestion[];
  evaluation?: {
    score: number;
    report_md: string;
    results: Array<{
      name: string;
      weight: string;
      score: number;
      max_score: number;
      reasoning: string;
      details: any;
    }>;
  };
}

export default function Home() {
  // Theme management
  const [darkMode, setDarkMode] = useState(true);

  // Mode Selection: "single" | "compare"
  const [mode, setMode] = useState<"single" | "compare">("single");

  // Input states
  const [url1, setUrl1] = useState("");
  const [url2, setUrl2] = useState("");

  // Loading states & stages
  const [loading, setLoading] = useState(false);
  const [progressLeft, setProgressLeft] = useState<string[]>([]);
  const [progressRight, setProgressRight] = useState<string[]>([]);

  // Stream data states
  const [reportLeft, setReportLeft] = useState<AnalystReport | null>(null);
  const [reportRight, setReportRight] = useState<AnalystReport | null>(null);

  // Active details modal for grounding checklists
  const [selectedChecklist, setSelectedChecklist] = useState<{
    title: string;
    confidence: number;
    reasoning: string;
    citation: string;
  } | null>(null);

  // Past reports history state
  const [history, setHistory] = useState<any[]>([]);
  const [dbStatus, setDbStatus] = useState<"online" | "offline">("online");
  const [savingStatus, setSavingStatus] = useState<string | null>(null);

  // Load history on mount
  useEffect(() => {
    fetchHistory();
  }, []);

  // Sync theme changes
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  const fetchHistory = async () => {
    const res = await loadHistoryAction();
    if (res.success && res.list) {
      setHistory(res.list);
      setDbStatus("online");
    } else {
      setDbStatus("offline");
    }
  };

  const handleDeleteHistory = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const res = await deleteAnalysisAction(id);
    if (res.success) {
      fetchHistory();
    }
  };

  const handleSelectHistory = (item: any) => {
    // Clear out active streaming frames
    setUrl1(item.url);
    setUrl2("");
    setMode("single");
    
    // Parse the stored JSON
    const report: AnalystReport = item.reportJson;
    setReportLeft(report);
    setReportRight(null);
  };

  // Triggers streaming pipeline
  const runAnalysis = async () => {
    if (!url1.trim()) return;

    setLoading(true);
    setReportLeft(null);
    setReportRight(null);
    setProgressLeft([]);
    setProgressRight([]);
    setSavingStatus(null);

    const controller = new AbortController();

    try {
      // Connect directly to FastAPI Server via POST SSE using fetch-event-source
      await fetchEventSource("http://localhost:8000/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url1,
          url2: mode === "compare" ? url2 : undefined
        }),
        signal: controller.signal,
        async onopen(response) {
          if (response.ok) return;
          throw new Error(`API stream error: ${response.status}`);
        },
        onmessage(msg) {
          try {
            const data = JSON.parse(msg.data);
            const side = data.side; // "left" or "right"

            if (data.event === "progress") {
              if (side === "left") {
                setProgressLeft((prev) => [...prev, data.message]);
              } else {
                setProgressRight((prev) => [...prev, data.message]);
              }
            } else if (data.event === "headline") {
              if (side === "left") {
                setReportLeft((prev) => ({ ...prev, ticker: data.data.ticker, company_name: data.data.company_name, period: data.data.period, headline: data.data }));
              } else {
                setReportRight((prev) => ({ ...prev, ticker: data.data.ticker, company_name: data.data.company_name, period: data.data.period, headline: data.data }));
              }
            } else if (data.event === "segments") {
              if (side === "left") {
                setReportLeft((prev) => ({ ...prev, segments: data.data } as AnalystReport));
              } else {
                setReportRight((prev) => ({ ...prev, segments: data.data } as AnalystReport));
              }
            } else if (data.event === "guidance") {
              if (side === "left") {
                setReportLeft((prev) => ({ ...prev, guidance: data.data } as AnalystReport));
              } else {
                setReportRight((prev) => ({ ...prev, guidance: data.data } as AnalystReport));
              }
            } else if (data.event === "takeaways") {
              if (side === "left") {
                setReportLeft((prev) => ({ ...prev, bull_takeaways: data.bull, bear_takeaways: data.bear } as AnalystReport));
              } else {
                setReportRight((prev) => ({ ...prev, bull_takeaways: data.bull, bear_takeaways: data.bear } as AnalystReport));
              }
            } else if (data.event === "risks") {
              if (side === "left") {
                setReportLeft((prev) => ({ ...prev, risks: data.data } as AnalystReport));
              } else {
                setReportRight((prev) => ({ ...prev, risks: data.data } as AnalystReport));
              }
            } else if (data.event === "questions") {
              if (side === "left") {
                setReportLeft((prev) => ({ ...prev, questions: data.data } as AnalystReport));
              } else {
                setReportRight((prev) => ({ ...prev, questions: data.data } as AnalystReport));
              }
            } else if (data.event === "evaluation") {
              if (side === "left") {
                setReportLeft((prev) => ({ ...prev, evaluation: data } as AnalystReport));
              } else {
                setReportRight((prev) => ({ ...prev, evaluation: data } as AnalystReport));
              }
            } else if (data.event === "done") {
              // Final report completed
              if (side === "left") {
                const finalSummary = data.summary;
                setReportLeft((prev) => ({ ...prev, ...finalSummary }));
                
                // Persist single analyses to Neon via Next.js Server Action
                if (mode === "single") {
                  saveReportToDatabase(finalSummary, url1);
                }
              } else {
                const finalSummary = data.summary;
                setReportRight((prev) => ({ ...prev, ...finalSummary }));
              }
              // STRICT GUARDRAIL: Clean stop on done to prevent auto-reconnect loops
              controller.abort();
              setLoading(false);
            } else if (data.event === "error") {
              if (side === "left") {
                setProgressLeft((prev) => [...prev, `❌ Error: ${data.message}`]);
              } else {
                setProgressRight((prev) => [...prev, `❌ Error: ${data.message}`]);
              }
              // STRICT GUARDRAIL: Clean stop on pipeline crash to prevent loops
              controller.abort();
              setLoading(false);
            }
          } catch (e) {
            console.error("Error parsing message chunk:", e);
          }
        },
        onclose() {
          // STRICT GUARDRAIL: Clean close releases loading states and aborts stream connection
          controller.abort();
          setLoading(false);
        },
        onerror(err) {
          console.error("SSE stream connection errored:", err);
          // STRICT GUARDRAIL: Stop reconnect retry loops instantly upon network or API error
          controller.abort();
          setLoading(false);
          throw err; // Stop fetchEventSource default retry loops
        }
      });
    } catch (error) {
      console.error("Failed executing analysis run:", error);
      setLoading(false);
    }
  };

  // Decoupled DB Server Action call
  const saveReportToDatabase = async (summary: any, url: string) => {
    setSavingStatus("Saving to Neon database...");
    
    // Extract grounding checklist elements for SQL log insertion
    const logs: any[] = [];
    const h = summary.headline;
    
    const headlineItems = [
      { name: "Revenue", obj: h.revenue },
      { name: "EPS", obj: h.eps },
      { name: "Operating Margin", obj: h.operating_margin },
      { name: "Net Income", obj: h.net_income }
    ];
    
    headlineItems.forEach((item) => {
      logs.push({
        metricName: `Headline: ${item.name}`,
        extractedValue: item.obj.actual,
        sourceTable: item.obj.citation_span.includes("|") ? "Parsed Operations Table" : "Text Citation",
        sourceRow: item.obj.citation_span.substring(0, 100),
        isVerified: item.obj.confidence >= 0.70
      });
    });

    const res = await saveAnalysisAction({
      ticker: summary.ticker,
      companyName: summary.company_name,
      period: summary.period,
      url: url,
      veracityScore: summary.evaluation?.score || 90.0,
      cost: summary.cost_log.usd_cost,
      reportJson: summary,
      logs
    });

    if (res.success) {
      setSavingStatus("✓ Persisted to Neon Postgres successfully.");
      fetchHistory();
    } else {
      // Graceful degradation in action!
      setSavingStatus("⚠️ Database write offline. Report remains interactive local-only.");
      setDbStatus("offline");
    }
  };

  // Helper colors for confidence badges
  const getConfidenceBadge = (score: number) => {
    if (score >= 0.80) {
      return {
        bg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
        label: "Green (>=80%)",
        color: "text-emerald-400"
      };
    } else if (score >= 0.50) {
      return {
        bg: "bg-amber-500/10 text-amber-400 border-amber-500/20",
        label: "Amber (50%-80%)",
        color: "text-amber-400"
      };
    } else {
      return {
        bg: "bg-rose-500/10 text-rose-400 border-rose-500/20",
        label: "Red (<50%)",
        color: "text-rose-400"
      };
    }
  };

  return (
    <div className="min-h-screen transition-colors duration-300 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      
      {/* 1. Header Navigation Bar */}
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md sticky top-0 z-40 w-full">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <TrendingUp className="h-6 w-6 text-indigo-500 animate-pulse" />
            <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-indigo-500 to-emerald-400 bg-clip-text text-transparent">
              e-Analyst
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Institutional Engine
            </span>
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-1.5 text-xs text-slate-500 dark:text-slate-400">
              <span className={`h-2.5 w-2.5 rounded-full ${dbStatus === "online" ? "bg-emerald-500" : "bg-rose-500 animate-ping"}`} />
              <span>Neon DB: {dbStatus === "online" ? "Connected" : "Offline"}</span>
            </div>

            <button
              onClick={() => setDarkMode(!darkMode)}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="Toggle Light/Dark Theme"
            >
              {darkMode ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4 text-indigo-500" />}
            </button>
          </div>
        </div>
      </header>

      {/* 2. Main Portal Content */}
      <div className="max-w-7xl mx-auto px-6 py-8 flex-1 grid grid-cols-1 lg:grid-cols-4 gap-8 w-full">
        
        {/* SIDEBAR: Controls & Past Analyses History */}
        <aside className="lg:col-span-1 flex flex-col space-y-6">
          
          {/* Analysis mode selector card */}
          <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4">
            <h3 className="font-bold text-sm text-slate-400 uppercase tracking-wider">Analysis Mode</h3>
            
            <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-200/50 dark:border-slate-800/50">
              <button
                onClick={() => { setMode("single"); setUrl2(""); }}
                className={`py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  mode === "single"
                    ? "bg-white dark:bg-slate-900 shadow-sm text-indigo-500 dark:text-indigo-400"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                <span>Single URL</span>
              </button>
              <button
                onClick={() => setMode("compare")}
                className={`py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center space-x-1 ${
                  mode === "compare"
                    ? "bg-white dark:bg-slate-900 shadow-sm text-indigo-500 dark:text-indigo-400"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                <Scale className="h-3.5 w-3.5" />
                <span>Compare Mode</span>
              </button>
            </div>

            <div className="flex flex-col space-y-3">
              <div className="relative">
                <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Primary earnings URL (HTML/PDF)"
                  value={url1}
                  onChange={(e) => setUrl1(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 rounded-xl text-xs bg-slate-100 dark:bg-slate-950 border border-slate-200/50 dark:border-slate-800/50 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-500"
                />
              </div>

              {mode === "compare" && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="relative overflow-hidden"
                >
                  <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Compare earnings URL (HTML/PDF)"
                    value={url2}
                    onChange={(e) => setUrl2(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 rounded-xl text-xs bg-slate-100 dark:bg-slate-950 border border-slate-200/50 dark:border-slate-800/50 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-500"
                  />
                </motion.div>
              )}

              <button
                onClick={runAnalysis}
                disabled={loading || !url1}
                className="w-full py-3 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white rounded-xl text-xs font-bold transition-all shadow-md flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    <span>Streaming...</span>
                  </>
                ) : (
                  <span>Run Financial Analysis</span>
                )}
              </button>
            </div>
            
            {savingStatus && (
              <span className="text-[10px] font-medium text-center text-indigo-400 mt-2">
                {savingStatus}
              </span>
            )}
          </div>

          {/* Past Analyses history card */}
          <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4 flex-1 max-h-[400px] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200/50 dark:border-slate-800/50 pb-3">
              <span className="font-bold text-sm text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                <Clock className="h-4 w-4" />
                <span>Recent Analyses</span>
              </span>
              <span className="text-[10px] bg-slate-100 dark:bg-slate-950 px-2 py-0.5 rounded-full font-bold border border-slate-200/50 dark:border-slate-800/50">
                {history.length}
              </span>
            </div>

            <div className="flex flex-col space-y-2">
              {history.length === 0 ? (
                <div className="text-center py-6 text-xs text-slate-500">
                  No historical reports found in database.
                </div>
              ) : (
                history.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => handleSelectHistory(item)}
                    className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 hover:bg-slate-100 dark:hover:bg-slate-900 border border-slate-200/30 dark:border-slate-800/30 transition-all cursor-pointer group flex items-center justify-between"
                  >
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="font-extrabold text-xs text-indigo-400">
                          {item.ticker}
                        </span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                          {item.veracityScore.toFixed(0)}%
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 truncate mt-1">
                        {item.companyName} | {item.period}
                      </span>
                    </div>

                    <button
                      onClick={(e) => handleDeleteHistory(item.id, e)}
                      className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-rose-500/10 text-rose-400 transition-all"
                      title="Delete Report"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

        </aside>

        {/* WORKSPACE: Streaming Reports Display Panel */}
        <main className="lg:col-span-3 flex flex-col space-y-8">
          
          {/* Progress state banner */}
          {(progressLeft.length > 0 || progressRight.length > 0) && loading && (
            <div className="p-5 rounded-2xl border border-indigo-500/20 bg-indigo-500/5 backdrop-blur-sm grid grid-cols-1 md:grid-cols-2 gap-4">
              {progressLeft.length > 0 && (
                <div className="flex flex-col space-y-1.5">
                  <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center space-x-1.5">
                    <span className="h-1.5 w-1.5 bg-indigo-500 rounded-full animate-ping" />
                    <span>Pipeline Left: {url1 ? new URL(url1).hostname : ""}</span>
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400 animate-pulse">
                    {progressLeft[progressLeft.length - 1]}
                  </span>
                </div>
              )}

              {progressRight.length > 0 && mode === "compare" && (
                <div className="flex flex-col space-y-1.5 border-t border-slate-200 dark:border-slate-800 md:border-t-0 md:border-l md:pl-4">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center space-x-1.5">
                    <span className="h-1.5 w-1.5 bg-emerald-500 rounded-full animate-ping" />
                    <span>Pipeline Right: {url2 ? new URL(url2).hostname : ""}</span>
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400 animate-pulse">
                    {progressRight[progressRight.length - 1]}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Side-by-Side column display grid */}
          <div className={`grid grid-cols-1 ${mode === "compare" ? "md:grid-cols-2" : ""} gap-8`}>
            
            {/* COLUMN LEFT */}
            <div className="flex flex-col space-y-8">
              {reportLeft ? (
                <motion.div
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col space-y-8"
                >
                  <ReportCard
                    report={reportLeft}
                    getConfidenceBadge={getConfidenceBadge}
                    setSelectedChecklist={setSelectedChecklist}
                  />
                </motion.div>
              ) : (
                !loading && (
                  <div className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-3xl p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center space-y-3">
                    <BookOpen className="h-8 w-8 text-indigo-400/50" />
                    <span>No financial report generated. Paste a URL and run analysis to begin.</span>
                  </div>
                )
              )}
            </div>

            {/* COLUMN RIGHT */}
            {mode === "compare" && (
              <div className="flex flex-col space-y-8">
                {reportRight ? (
                  <motion.div
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col space-y-8"
                  >
                    <ReportCard
                      report={reportRight}
                      getConfidenceBadge={getConfidenceBadge}
                      setSelectedChecklist={setSelectedChecklist}
                    />
                  </motion.div>
                ) : (
                  !loading && (
                    <div className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-3xl p-12 text-center text-xs text-slate-500 flex flex-col items-center justify-center space-y-3 h-full">
                      <Scale className="h-8 w-8 text-emerald-400/50" />
                      <span>Compare column is active. Paste two URLs to analyze and compare corporate indicators side-by-side.</span>
                    </div>
                  )
                )}
              </div>
            )}

          </div>

        </main>

      </div>

      {/* 3. Programmatic Veracity Grounds Details Dialog */}
      <AnimatePresence>
        {selectedChecklist && (
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 max-w-lg w-full rounded-2xl p-6 shadow-2xl relative flex flex-col space-y-4"
            >
              <div className="flex items-center justify-between border-b border-slate-200/50 dark:border-slate-800/50 pb-3">
                <div className="flex flex-col">
                  <span className="font-extrabold text-sm text-indigo-400">Veracity Check</span>
                  <h3 className="font-bold text-base mt-0.5">{selectedChecklist.title}</h3>
                </div>
                
                <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${getConfidenceBadge(selectedChecklist.confidence).bg}`}>
                  F-GVI: {(selectedChecklist.confidence * 100).toFixed(0)}%
                </span>
              </div>

              <div className="flex flex-col space-y-3">
                <span className="font-bold text-xs text-slate-400 uppercase tracking-wider">Automated Verification Checklist</span>
                
                <div className="flex flex-col space-y-2">
                  {Object.entries(JSON.parse(selectedChecklist.reasoning)).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/20 dark:border-slate-800/20">
                      <span className="text-xs font-semibold capitalize text-slate-600 dark:text-slate-400">
                        {key.replace(/_/g, " ")}
                      </span>
                      {value ? (
                        <div className="flex items-center space-x-1 text-emerald-400 text-xs font-bold">
                          <CheckCircle2 className="h-4 w-4" />
                          <span>PASS</span>
                        </div>
                      ) : (
                        <div className="flex items-center space-x-1 text-rose-400 text-xs font-bold">
                          <XCircle className="h-4 w-4" />
                          <span>FAIL</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {selectedChecklist.citation && selectedChecklist.citation !== "N/A" && (
                <div className="flex flex-col space-y-2 bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200/30 dark:border-slate-800/30">
                  <div className="flex items-center space-x-2 text-[10px] font-extrabold text-indigo-400 uppercase tracking-wider">
                    <FileSpreadsheet className="h-3.5 w-3.5" />
                    <span>Verbatim Cited Text / Table Coordinate Row</span>
                  </div>
                  <pre className="text-xs text-slate-600 dark:text-slate-400 whitespace-pre-wrap font-mono leading-relaxed max-h-[120px] overflow-y-auto">
                    {selectedChecklist.citation}
                  </pre>
                </div>
              )}

              <button
                onClick={() => setSelectedChecklist(null)}
                className="w-full py-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 font-bold rounded-xl text-xs transition-colors"
              >
                Close Grounding Details
              </button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}

// SUB-COMPONENT: Unified report card rendering
function ReportCard({
  report,
  getConfidenceBadge,
  setSelectedChecklist
}: {
  report: AnalystReport;
  getConfidenceBadge: (s: number) => any;
  setSelectedChecklist: (c: any) => void;
}) {
  return (
    <div className="flex flex-col space-y-8">
      
      {/* SECTION: Title / Header statistics */}
      <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="font-extrabold text-xs text-indigo-400">{report.ticker}</span>
            <h2 className="font-black text-xl tracking-tight leading-none mt-1">{report.company_name}</h2>
            <span className="text-xs text-slate-500 font-semibold mt-1">Period: {report.period}</span>
          </div>
          
          {report.evaluation && (
            <div className="flex flex-col items-end">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Veracity score</span>
              <span className="font-black text-2xl text-emerald-400">{report.evaluation.score.toFixed(0)}/100</span>
            </div>
          )}
        </div>
      </div>

      {/* SECTION: Headline metrics */}
      {report.headline && (
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4">
          <h3 className="font-bold text-xs text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
            <DollarSign className="h-4 w-4" />
            <span>Headline Financials</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { name: "Revenue", obj: report.headline.revenue },
              { name: "EPS", obj: report.headline.eps },
              { name: "Operating Margin", obj: report.headline.operating_margin },
              { name: "Net Income", obj: report.headline.net_income }
            ].map((metric) => (
              <div
                key={metric.name}
                className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200/30 dark:border-slate-800/30 flex flex-col justify-between"
              >
                <div className="flex items-start justify-between">
                  <span className="text-xs font-bold text-slate-500">{metric.name}</span>
                  <button
                    onClick={() =>
                      setSelectedChecklist({
                        title: `Headline: ${metric.name}`,
                        confidence: metric.obj.confidence,
                        reasoning: metric.obj.confidence_reasoning,
                        citation: metric.obj.citation_span
                      })
                    }
                    className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border ${getConfidenceBadge(metric.obj.confidence).bg}`}
                  >
                    F-GVI: {(metric.obj.confidence * 100).toFixed(0)}%
                  </button>
                </div>
                <div className="flex items-end justify-between mt-4">
                  <span className="font-black text-lg text-slate-900 dark:text-slate-50">{metric.obj.actual}</span>
                  <div className="flex flex-col items-end">
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${metric.obj.beat_miss === "Beat" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
                      {metric.obj.beat_miss}
                    </span>
                    <span className="text-[10px] text-slate-500 font-bold mt-1">YoY: {metric.obj.yoy_growth}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION: Segment performances */}
      {report.segments && report.segments.length > 0 && (
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4">
          <h3 className="font-bold text-xs text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
            <LayoutGrid className="h-4 w-4" />
            <span>Segment Performance</span>
          </h3>

          <div className="flex flex-col space-y-3">
            {report.segments.map((seg) => (
              <div key={seg.name} className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200/30 dark:border-slate-800/30">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs">{seg.name}</span>
                  <span className="text-xs font-black text-indigo-400">{seg.revenue}</span>
                </div>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-200/20 dark:border-slate-800/20">
                  <span className="text-[10px] text-slate-500 font-bold">YoY Growth</span>
                  <span className="text-[10px] font-extrabold text-emerald-400">{seg.growth}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION: Guidance matrix */}
      {report.guidance && report.guidance.length > 0 && (
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4">
          <h3 className="font-bold text-xs text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
            <FileSpreadsheet className="h-4 w-4" />
            <span>Forward Guidance Matrix</span>
          </h3>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 uppercase tracking-wider font-extrabold">
                  <th className="py-2">Metric</th>
                  <th className="py-2">Period</th>
                  <th className="py-2">Low</th>
                  <th className="py-2">High</th>
                  <th className="py-2 text-right">Mid</th>
                </tr>
              </thead>
              <tbody>
                {report.guidance.map((g, idx) => (
                  <tr key={idx} className="border-b border-slate-200/30 dark:border-slate-800/30 text-slate-600 dark:text-slate-300 font-semibold">
                    <td className="py-2">{g.metric}</td>
                    <td className="py-2">{g.period}</td>
                    <td className="py-2">{g.range_low}</td>
                    <td className="py-2">{g.range_high}</td>
                    <td className="py-2 text-right text-indigo-400 font-bold">{g.range_mid}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SECTION: Bull vs Bear Takeaways */}
      {((report.bull_takeaways && report.bull_takeaways.length > 0) || (report.bear_takeaways && report.bear_takeaways.length > 0)) && (
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-6">
          
          {report.bull_takeaways && (
            <div className="flex flex-col space-y-4">
              <h3 className="font-bold text-xs text-emerald-400 uppercase tracking-wider flex items-center space-x-1.5">
                <TrendingUp className="h-4 w-4" />
                <span>Bull Takes</span>
              </h3>
              <div className="flex flex-col space-y-3">
                {report.bull_takeaways.map((b, idx) => (
                  <div key={idx} className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200/20 dark:border-slate-800/20 flex items-start justify-between">
                    <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300 pr-3">{b.text}</p>
                    <button
                      onClick={() =>
                        setSelectedChecklist({
                          title: `Bull Take ${idx + 1}`,
                          confidence: b.confidence,
                          reasoning: b.confidence_reasoning,
                          citation: b.citation_span
                        })
                      }
                      className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded border flex-shrink-0 ${getConfidenceBadge(b.confidence).bg}`}
                    >
                      F-GVI: {(b.confidence * 100).toFixed(0)}%
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.bear_takeaways && (
            <div className="flex flex-col space-y-4 pt-4 border-t border-slate-200/50 dark:border-slate-800/50">
              <h3 className="font-bold text-xs text-rose-400 uppercase tracking-wider flex items-center space-x-1.5">
                <AlertTriangle className="h-4 w-4 animate-bounce" />
                <span>Bear Takes</span>
              </h3>
              <div className="flex flex-col space-y-3">
                {report.bear_takeaways.map((b, idx) => (
                  <div key={idx} className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200/20 dark:border-slate-800/20 flex items-start justify-between">
                    <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300 pr-3">{b.text}</p>
                    <button
                      onClick={() =>
                        setSelectedChecklist({
                          title: `Bear Take ${idx + 1}`,
                          confidence: b.confidence,
                          reasoning: b.confidence_reasoning,
                          citation: b.citation_span
                        })
                      }
                      className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded border flex-shrink-0 ${getConfidenceBadge(b.confidence).bg}`}
                    >
                      F-GVI: {(b.confidence * 100).toFixed(0)}%
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      )}

      {/* SECTION: Risks log */}
      {report.risks && report.risks.length > 0 && (
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4">
          <h3 className="font-bold text-xs text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
            <AlertTriangle className="h-4 w-4 text-rose-500" />
            <span>Categorized Risks</span>
          </h3>

          <div className="flex flex-col space-y-3">
            {report.risks.map((risk, idx) => (
              <div key={idx} className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200/30 dark:border-slate-800/30">
                <div className="flex items-center justify-between border-b border-slate-200/20 dark:border-slate-800/20 pb-2 mb-2">
                  <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-rose-500/10 text-rose-400">
                    {risk.category}
                  </span>
                  
                  <button
                    onClick={() =>
                      setSelectedChecklist({
                        title: `${risk.category} Risk`,
                        confidence: risk.confidence,
                        reasoning: risk.confidence_reasoning,
                        citation: risk.citation_span
                      })
                    }
                    className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded border ${getConfidenceBadge(risk.confidence).bg}`}
                  >
                    F-GVI: {(risk.confidence * 100).toFixed(0)}%
                  </button>
                </div>
                <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  {risk.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION: Probing call questions */}
      {report.questions && report.questions.length > 0 && (
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col space-y-4">
          <h3 className="font-bold text-xs text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
            <HelpCircle className="h-4 w-4 text-indigo-400" />
            <span>Earnings Call Playbook</span>
          </h3>

          <div className="flex flex-col space-y-4">
            {report.questions.map((q, idx) => (
              <div key={idx} className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200/30 dark:border-slate-800/30 flex flex-col space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-extrabold text-indigo-400 uppercase tracking-wider">Playbook Q{idx + 1}</span>
                  <button
                    onClick={() =>
                      setSelectedChecklist({
                        title: `Question ${idx + 1}`,
                        confidence: q.confidence,
                        reasoning: q.confidence_reasoning,
                        citation: q.premise
                      })
                    }
                    className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded border ${getConfidenceBadge(q.confidence).bg}`}
                  >
                    F-GVI: {(q.confidence * 100).toFixed(0)}%
                  </button>
                </div>

                <p className="text-xs text-slate-500 font-semibold italic">
                  Premise: "{q.premise}"
                </p>
                <p className="text-xs font-bold text-slate-800 dark:text-slate-100 bg-slate-100/50 dark:bg-slate-900/50 p-3 rounded-xl">
                  {q.text}
                </p>
                <p className="text-[10px] text-indigo-400 font-semibold">
                  Tension: {q.tension}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
