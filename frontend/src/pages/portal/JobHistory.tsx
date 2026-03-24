import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePortalAuth } from "@/contexts/PortalAuthContext";
import { portalApi, type ReportJob } from "@/api/portal";
import { Button } from "@/components/ui/button";
import { Download, RefreshCw } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const STATUS_STYLES: Record<string, string> = {
  queued: "bg-slate-100 text-slate-600",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-slate-100 text-slate-400",
};

const TYPE_LABELS: Record<string, string> = {
  sales_summary: "Sales Summary",
  csv_export: "CSV Export",
  pdf_report: "PDF Report",
};

export function JobHistory() {
  const { token } = usePortalAuth();
  const [page, setPage] = useState(0);
  const limit = 15;

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["portal-jobs", page, token],
    queryFn: () =>
      portalApi.listReports(token!, { limit, offset: page * limit }),
    enabled: !!token,
  });

  const handleDownload = async (downloadUrl: string) => {
    try {
      const response = await fetch(downloadUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      // Get the filename from Content-Disposition header or use a default
      const contentDisposition = response.headers.get('Content-Disposition');
      const filename = contentDisposition
        ? contentDisposition.split('filename=')[1]?.replace(/"/g, '')
        : 'report.pdf';

      // Create a blob and trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download error:', error);
      alert('Failed to download report. Please try again.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">My Reports</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {data?.total ?? 0} total jobs
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
          className="gap-1.5"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        // Skeleton rows
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-14 bg-secondary rounded-lg animate-pulse"
            />
          ))}
        </div>
      ) : !data?.items.length ? (
        <div className="text-center py-16 text-muted-foreground border rounded-lg border-dashed">
          <p className="text-lg font-medium">No reports yet</p>
          <p className="text-sm mt-1">
            Go to New Report to generate your first one
          </p>
        </div>
      ) : (
        <>
          <div className="border rounded-lg overflow-hidden bg-background">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b">
                <tr>
                  {["Type", "Status", "Progress", "Created", "Download"].map(
                    (h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left text-xs font-medium text-muted-foreground"
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {data.items.map((job: ReportJob) => (
                  <tr
                    key={job.job_id}
                    className="border-b last:border-0 hover:bg-secondary/10 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium">
                      {TYPE_LABELS[job.report_type] ?? job.report_type}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[job.status] ?? ""}`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-400">
                          {job.progress}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {formatDistanceToNow(new Date(job.created_at), {
                        addSuffix: true,
                      })}
                    </td>
                    <td className="px-4 py-3">
                      {job.status === "completed" && job.links.download ? (
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-1.5 h-7"
                          onClick={() => handleDownload(job.links.download!)}
                        >
                          <Download className="h-3 w-3" />
                          Download
                        </Button>
                      ) : (
                        <span className="text-xs text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {page * limit + 1}–
              {Math.min((page + 1) * limit, data.total)} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p - 1)}
                disabled={page === 0}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * limit >= data.total}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
