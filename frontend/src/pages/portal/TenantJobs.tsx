import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePortalAuth } from "@/contexts/PortalAuthContext";
import { tenantAdminApi, type TenantJob } from "@/api/tenantAdmin";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

const STATUS_COLORS: Record<TenantJob["status"], string> = {
  queued: "bg-blue-100 text-blue-800",
  running: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
};

export function TenantJobs() {
  const { token } = usePortalAuth();
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(
    undefined,
  );
  const limit = 25;

  const { data, isLoading, error } = useQuery({
    queryKey: ["tenant-jobs", page, statusFilter],
    queryFn: () =>
      tenantAdminApi.getJobs(token!, {
        limit,
        offset: page * limit,
        status: statusFilter,
      }),
    enabled: !!token,
  });

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">All Tenant Jobs</h1>
        <p className="text-muted-foreground mt-2">
          View all report jobs submitted by users in your tenant
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <Button
          variant={statusFilter === undefined ? "default" : "outline"}
          size="sm"
          onClick={() => setStatusFilter(undefined)}
        >
          All
        </Button>
        {["queued", "running", "completed", "failed", "cancelled"].map(
          (status) => (
            <Button
              key={status}
              variant={statusFilter === status ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setStatusFilter(status);
                setPage(0);
              }}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Button>
          ),
        )}
      </div>

      {/* Jobs Table */}
      {error && (
        <div className="text-destructive">
          Failed to load jobs: {(error as Error).message}
        </div>
      )}

      {isLoading ? (
        <div className="text-muted-foreground">Loading jobs...</div>
      ) : data && data.jobs.length > 0 ? (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job ID</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Report Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead>Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.jobs.map((job) => (
                  <TableRow key={job.job_id}>
                    <TableCell className="font-mono text-xs">
                      {job.job_id.split("-")[0]}...
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {job.user_id.split("-")[0]}...
                    </TableCell>
                    <TableCell>{job.report_type}</TableCell>
                    <TableCell>
                      <Badge
                        className={STATUS_COLORS[job.status]}
                        variant="secondary"
                      >
                        {job.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{job.progress}%</TableCell>
                    <TableCell>{job.priority}</TableCell>
                    <TableCell className="text-xs">
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs max-w-xs truncate">
                      {job.error_message || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Showing {page * limit + 1} to{" "}
              {Math.min((page + 1) * limit, data.total)} of {data.total} jobs
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages - 1}
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          No jobs found
          {statusFilter && ` with status "${statusFilter}"`}
        </div>
      )}
    </div>
  );
}
