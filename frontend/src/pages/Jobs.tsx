import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi, type AdminJob } from "@/api/admin";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChevronDown, ChevronRight } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const STATUS_COLOURS: Record<string, string> = {
  queued: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  running: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  completed: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  failed: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  cancelled: "bg-muted text-muted-foreground",
};

function JobRow({ job }: { job: AdminJob }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr
        className="border-b border-border hover:bg-muted/50 cursor-pointer transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <td className="px-4 py-3">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
          {job.job_id.slice(0, 8)}…
        </td>
        <td className="px-4 py-3 text-sm text-foreground">{job.report_type}</td>
        <td className="px-4 py-3">
          <span
            className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLOURS[job.status] ?? ""}`}
          >
            {job.status}
          </span>
        </td>
        <td className="px-4 py-3 text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
        </td>
        <td className="px-4 py-3 text-xs text-muted-foreground/60 font-mono truncate max-w-xs">
          {job.tenant_id.slice(0, 8)}…
        </td>
      </tr>
      {expanded && job.error_message && (
        <tr className="bg-destructive/10 dark:bg-destructive/20">
          <td colSpan={6} className="px-4 py-3">
            <p className="text-xs font-semibold text-destructive mb-1">
              Error trace
            </p>
            <pre className="text-xs text-destructive/90 whitespace-pre-wrap font-mono">
              {job.error_message}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

export function Jobs() {
  const [status, setStatus] = useState<string>("all");
  const [page, setPage] = useState(0);
  const limit = 25;

  const params = {
    limit,
    offset: page * limit,
    ...(status !== "all" && { status }),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["jobs", params],
    queryFn: () => adminApi.getJobs(params),
  });

  return (
    <div className="space-y-6 lg:space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Jobs</h1>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <>
          <div className="border border-border rounded-xl overflow-hidden bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b border-border">
                <tr>
                  <th className="w-8 px-4 py-3" />
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                    Job ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                    Created
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                    Tenant
                  </th>
                </tr>
              </thead>
              <tbody>
                {data?.jobs.map((job) => (
                  <JobRow key={job.job_id} job={job} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{data?.total ?? 0} total jobs</span>
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
                disabled={(page + 1) * limit >= (data?.total ?? 0)}
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
