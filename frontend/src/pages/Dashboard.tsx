import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type QueueStatus } from "@/api/admin";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LineChart, Line, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useEffect, useState } from "react";
import { Trash2, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

// Rolling buffer — keeps last 60 data points for sparkline
function useQueueHistory(current: QueueStatus | undefined) {
  const [history, setHistory] = useState<{ t: string; total: number }[]>([]);
  useEffect(() => {
    if (!current) return;
    const point = {
      t: new Date().toLocaleTimeString(),
      total: current.total_pending,
    };
    queueMicrotask(() => {
      setHistory((prev) => [...prev.slice(-59), point]);
    });
  }, [current]);
  return history;
}

function StatCard({
  title,
  value,
  sub,
}: {
  title: string;
  value: number;
  sub?: string;
}) {
  return (
    <Card size="sm" className="min-w-0">
      <CardHeader className="pb-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold text-foreground lg:text-4xl">
          {value}
        </p>
        {sub && <p className="text-xs text-muted-foreground mt-2">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["queue"],
    queryFn: adminApi.getQueue,
    refetchInterval: 5_000, // poll every 5 seconds
  });

  const history = useQueueHistory(data);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Cleanup jobs state
  const [olderThanDays, setOlderThanDays] = useState("30");
  const [statusFilter, setStatusFilter] = useState("completed");
  const [previewResult, setPreviewResult] = useState<{
    would_delete: number;
    cutoff_date: string;
  } | null>(null);

  // Preview mutation (dry run)
  const previewMutation = useMutation({
    mutationFn: () =>
      adminApi.cleanupJobs({
        older_than_days: parseInt(olderThanDays),
        status_filter: statusFilter,
        dry_run: true,
      }),
    onSuccess: (data) => {
      setPreviewResult({
        would_delete: data.would_delete ?? 0,
        cutoff_date: data.cutoff_date,
      });
      toast({
        title: "Preview Complete",
        description: `${data.would_delete ?? 0} job(s) would be deleted`,
      });
    },
    onError: () => {
      toast({
        title: "Preview Failed",
        description: "Failed to preview cleanup",
        variant: "destructive",
      });
    },
  });

  // Cleanup mutation (actual deletion)
  const cleanupMutation = useMutation({
    mutationFn: () =>
      adminApi.cleanupJobs({
        older_than_days: parseInt(olderThanDays),
        status_filter: statusFilter,
        dry_run: false,
      }),
    onSuccess: (data) => {
      toast({
        title: "Cleanup Complete",
        description: `Successfully deleted ${data.deleted ?? 0} job(s)`,
      });
      setPreviewResult(null);
      queryClient.invalidateQueries({ queryKey: ["adminJobs"] });
    },
    onError: () => {
      toast({
        title: "Cleanup Failed",
        description: "Failed to delete jobs",
        variant: "destructive",
      });
    },
  });

  if (isLoading) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-6 lg:space-y-8">
      <h1 className="text-3xl font-bold">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 xl:gap-6">
        <StatCard title="Total Pending" value={data?.total_pending ?? 0} />
        <StatCard
          title="High Queue"
          value={data?.queues.high ?? 0}
          sub="priority 1"
        />
        <StatCard
          title="Default Queue"
          value={data?.queues.default ?? 0}
          sub="priority 5"
        />
        <StatCard
          title="Low Queue"
          value={data?.queues.low ?? 0}
          sub="priority 9"
        />
      </div>

      {/* Sparkline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Queue Depth — last {history.length} readings (5s interval)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={history}>
              <XAxis dataKey="t" hide />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="total"
                stroke="#3b82f6"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Job Cleanup Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trash2 className="h-5 w-5" />
            Job Cleanup
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Delete old completed/failed jobs to free up database space
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="olderThanDays">Delete jobs older than</Label>
                <div className="flex gap-2">
                  <Input
                    id="olderThanDays"
                    type="number"
                    min="1"
                    max="365"
                    value={olderThanDays}
                    onChange={(e) => setOlderThanDays(e.target.value)}
                    placeholder="30"
                  />
                  <span className="flex items-center text-sm text-muted-foreground">
                    days
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="statusFilter">Job status</Label>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger id="statusFilter">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="completed">Completed only</SelectItem>
                    <SelectItem value="failed">Failed only</SelectItem>
                    <SelectItem value="cancelled">Cancelled only</SelectItem>
                    <SelectItem value="all">
                      All terminal states (completed/failed/cancelled)
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {previewResult && (
              <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 dark:border-yellow-900 dark:bg-yellow-950">
                <div className="flex gap-2">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-yellow-900 dark:text-yellow-100">
                      Preview: {previewResult.would_delete} job(s) will be
                      deleted
                    </p>
                    <p className="text-xs text-yellow-700 dark:text-yellow-300">
                      Jobs created before{" "}
                      {new Date(previewResult.cutoff_date).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => previewMutation.mutate()}
                disabled={
                  previewMutation.isPending || cleanupMutation.isPending
                }
              >
                {previewMutation.isPending ? "Loading..." : "Preview"}
              </Button>
              <Button
                variant="destructive"
                onClick={() => cleanupMutation.mutate()}
                disabled={
                  !previewResult ||
                  previewResult.would_delete === 0 ||
                  cleanupMutation.isPending
                }
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {cleanupMutation.isPending
                  ? "Deleting..."
                  : `Delete ${previewResult?.would_delete ?? 0} Jobs`}
              </Button>
            </div>

            <p className="text-xs text-muted-foreground">
              💡 Tip: Preview first to see what will be deleted. Only terminal
              state jobs (completed/failed/cancelled) can be deleted. Active
              jobs (queued/running) are never affected.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
