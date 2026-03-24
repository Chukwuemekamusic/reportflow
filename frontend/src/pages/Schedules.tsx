import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { schedulesApi, type Schedule } from "@/api/schedules";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { format, formatDistanceToNow } from "date-fns";
import { PauseCircle } from "lucide-react";

export function Schedules() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["schedules"],
    queryFn: () => schedulesApi.list({ include_inactive: false }),
    refetchInterval: 30_000, // refresh every 30s — next_run_at changes over time
  });

  const deactivate = useMutation({
    mutationFn: schedulesApi.deactivate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["schedules"] }),
  });

  return (
    <div className="space-y-6 lg:space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Schedules</h1>
        <Badge variant="outline">{data?.total ?? 0} active</Badge>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <div className="border border-border rounded-xl overflow-hidden bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b border-border">
              <tr>
                {["Report Type", "Cron", "Next Run", "Last Run", "Action"].map(
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
              {data?.schedules.map((s: Schedule) => (
                <tr key={s.id} className="border-b border-border hover:bg-muted/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-foreground">{s.report_type}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {s.cron_expr}
                  </td>
                  <td className="px-4 py-3 text-xs text-foreground">
                    <span title={format(new Date(s.next_run_at), "PPpp")}>
                      {formatDistanceToNow(new Date(s.next_run_at), {
                        addSuffix: true,
                      })}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {s.last_run_at
                      ? formatDistanceToNow(new Date(s.last_run_at), {
                          addSuffix: true,
                        })
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => deactivate.mutate(s.id)}
                      disabled={deactivate.isPending}
                    >
                      <PauseCircle className="h-3 w-3 mr-1" />
                      Deactivate
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
