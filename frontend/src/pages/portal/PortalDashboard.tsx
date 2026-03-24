import { useState, useCallback } from "react";
import { usePortalAuth } from "@/contexts/PortalAuthContext";
import { portalApi, type SubmitReportRequest } from "@/api/portal";
import { useWebSocket, type WSEvent } from "@/hooks/useWebSocket";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, Loader2, CheckCircle2, XCircle, Zap } from "lucide-react";

// ── Progress bar component ─────────────────────────────────────────────
function ProgressBar({ value }: { value: number }) {
  return (
    <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
      <div
        className="h-full bg-blue-500 rounded-full transition-all duration-500 ease-out"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

// ── Job status badge ───────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    queued: "bg-slate-100 text-slate-600",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${variants[status] ?? ""}`}
    >
      {status}
    </span>
  );
}

// ── Main component ─────────────────────────────────────────────────────
interface ProgressState {
  jobId: string;
  progress: number;
  stage: string;
  etaSecs: number;
  status: "queued" | "running" | "completed" | "failed";
  downloadUrl: string | null;
  errorMessage: string | null;
}

export function PortalDashboard() {
  const { token } = usePortalAuth();

  // Form state
  const [reportType, setReportType] =
    useState<SubmitReportRequest["report_type"]>("sales_summary");
  const [region, setRegion] = useState("EMEA");
  const [status, setStatus] = useState("active");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  // Progress panel state — null = not yet submitted
  const [progressState, setProgressState] = useState<ProgressState | null>(
    null,
  );

  // Handle incoming WebSocket events
  const handleEvent = useCallback((event: WSEvent) => {
    if (event.event === "progress") {
      setProgressState((prev) =>
        prev
          ? {
              ...prev,
              progress: event.progress,
              stage: event.stage,
              etaSecs: event.eta_secs,
              status: "running",
            }
          : null,
      );
    } else if (event.event === "completed") {
      setProgressState((prev) =>
        prev
          ? {
              ...prev,
              progress: 100,
              stage: "Report ready",
              status: "completed",
              downloadUrl: event.download_url,
            }
          : null,
      );
    } else if (event.event === "failed") {
      setProgressState((prev) =>
        prev
          ? {
              ...prev,
              status: "failed",
              errorMessage: event.error_message,
            }
          : null,
      );
    }
  }, []);

  const { connect, status: wsStatus } = useWebSocket({ onEvent: handleEvent });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSubmitError("");
    setSubmitting(true);

    try {
      const job = await portalApi.submitReport(token, {
        report_type: reportType,
        priority: 5,
        filters: { region: region as any, status: status as any },
      });

      // Initialise progress state immediately — before WS connects
      setProgressState({
        jobId: job.job_id,
        progress: 0,
        stage: "Queuing job…",
        etaSecs: 0,
        status: "queued",
        downloadUrl: null,
        errorMessage: null,
      });

      // Connect to WebSocket stream
      connect(job.job_id, token);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setSubmitError(
        typeof detail === "string" ? detail : "Failed to submit report.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setProgressState(null);
    setSubmitError("");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">
          Generate a Report
        </h1>
        <p className="text-muted-foreground mt-1">
          Submit a report job and watch it run in real time
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Left: Submit form ─────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Report Configuration</CardTitle>
            <CardDescription>
              Choose a type and filters, then submit
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <Label>Report type</Label>
                <Select
                  value={reportType}
                  onValueChange={(v) => setReportType(v as any)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sales_summary">
                      Sales Summary — MRR breakdown + charts (PDF)
                    </SelectItem>
                    <SelectItem value="csv_export">
                      CSV Export — raw subscription data
                    </SelectItem>
                    <SelectItem value="pdf_report">
                      Full PDF Report — multi-section with charts
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Region</Label>
                  <Select value={region} onValueChange={setRegion}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="EMEA">EMEA</SelectItem>
                      <SelectItem value="AMER">AMER</SelectItem>
                      <SelectItem value="APAC">APAC</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>Subscription status</Label>
                  <Select value={status} onValueChange={setStatus}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active only</SelectItem>
                      <SelectItem value="cancelled">Cancelled only</SelectItem>
                      <SelectItem value="all">All</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {submitError && (
                <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md">
                  {submitError}
                </p>
              )}

              <Button
                type="submit"
                className="w-full gap-2"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Submitting…
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4" /> Generate Report
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* ── Right: Live progress panel ────────────────────────── */}
        <Card className={progressState ? "" : "border-dashed"}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Live Progress</CardTitle>
              {progressState && <StatusBadge status={progressState.status} />}
            </div>
            <CardDescription>
              {progressState
                ? `Job ${progressState.jobId.slice(0, 8)}…`
                : "Submit a report to see live progress here"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!progressState ? (
              // Empty state
              <div className="flex flex-col items-center justify-center py-10 text-slate-300">
                <Zap className="h-12 w-12 mb-3" />
                <p className="text-sm">Waiting for a job…</p>
              </div>
            ) : progressState.status === "failed" ? (
              // Failure state
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-destructive">
                  <XCircle className="h-5 w-5" />
                  <span className="font-medium">Job failed</span>
                </div>
                <p className="text-sm text-destructive-foreground bg-destructive-50 px-3 py-2 rounded-md font-mono">
                  {progressState.errorMessage}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleReset}
                  className="w-full"
                >
                  Try again
                </Button>
              </div>
            ) : progressState.status === "completed" ? (
              // Completion state
              <div className="space-y-4">
                <ProgressBar value={100} />
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="font-medium">Report ready!</span>
                </div>
                <div className="flex gap-2">
                  <a
                    href={`/api/v1${progressState.downloadUrl}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1"
                  >
                    <Button className="w-full gap-2">
                      <Download className="h-4 w-4" />
                      Download report
                    </Button>
                  </a>
                  <Button variant="outline" onClick={handleReset}>
                    New report
                  </Button>
                </div>
              </div>
            ) : (
              // Running state — the live panel
              <div className="space-y-4">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-600 font-medium">
                    {progressState.progress}%
                  </span>
                  {progressState.etaSecs > 0 && (
                    <span className="text-slate-400">
                      ~{progressState.etaSecs}s remaining
                    </span>
                  )}
                </div>
                <ProgressBar value={progressState.progress} />
                <p className="text-sm text-slate-500 min-h-[1.25rem]">
                  {progressState.stage}
                </p>

                {/* Animated pulse to show active connection */}
                <div className="flex items-center gap-2 text-xs text-blue-500">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
                  </span>
                  Live — WebSocket connected
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
