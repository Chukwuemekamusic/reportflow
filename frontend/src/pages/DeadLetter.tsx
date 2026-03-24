import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type DLQEntry } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDistanceToNow } from "date-fns";
import { useState } from "react";
import { ChevronDown, ChevronRight, RotateCcw, Trash2 } from "lucide-react";

function DLQRow({
  entry,
  onRetry,
  onPurge,
  retrying,
  purging,
}: {
  entry: DLQEntry;
  onRetry: () => void;
  onPurge: () => void;
  retrying: boolean;
  purging: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr className="border-b border-border hover:bg-muted/50 transition-colors">
        <td
          className="px-4 py-3 cursor-pointer"
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
          {entry.job_id.slice(0, 8)}…
        </td>
        <td className="px-4 py-3 text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(entry.last_error_at), {
            addSuffix: true,
          })}
        </td>
        <td className="px-4 py-3 text-xs text-foreground">{entry.retry_count} retries</td>
        <td className="px-4 py-3">
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={onRetry}
              disabled={retrying || purging}
            >
              <RotateCcw className="h-3 w-3 mr-1" />
              {retrying ? "Retrying…" : "Retry"}
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={onPurge}
              disabled={retrying || purging}
            >
              <Trash2 className="h-3 w-3 mr-1" />
              {purging ? "Purging…" : "Purge"}
            </Button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-muted/30">
          <td colSpan={5} className="px-4 py-3">
            <p className="text-xs font-semibold text-foreground mb-1">
              Error trace
            </p>
            <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono max-h-48 overflow-auto bg-background/50 p-3 rounded-lg border border-border">
              {entry.error_trace}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

export function DeadLetter() {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<"retry" | "purge" | null>(
    null,
  );

  const { data, isLoading } = useQuery({
    queryKey: ["dlq"],
    queryFn: adminApi.getDLQ,
  });

  const retryMutation = useMutation({
    mutationFn: adminApi.retryDLQ,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq"] });
    },
    onSettled: () => {
      setActiveId(null);
      setActiveAction(null);
    },
  });

  const purgeMutation = useMutation({
    mutationFn: adminApi.purgeDLQ,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq"] });
    },
    onSettled: () => {
      setActiveId(null);
      setActiveAction(null);
    },
  });

  function handleRetry(id: string) {
    setActiveId(id);
    setActiveAction("retry");
    retryMutation.mutate(id);
  }

  function handlePurge(id: string) {
    setActiveId(id);
    setActiveAction("purge");
    purgeMutation.mutate(id);
  }

  return (
    <div className="space-y-6 lg:space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dead Letter Queue</h1>
        <Badge variant="outline">{data?.total ?? 0} unresolved</Badge>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : data?.total === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-lg">Dead letter queue is empty</p>
          <p className="text-sm mt-1">
            All jobs have completed or been resolved
          </p>
        </div>
      ) : (
        <div className="border border-border rounded-xl overflow-hidden bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b border-border">
              <tr>
                <th className="w-8 px-4 py-3" />
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  Job ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  Failed
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  Retries
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((entry) => (
                <DLQRow
                  key={entry.id}
                  entry={entry}
                  onRetry={() => handleRetry(entry.id)}
                  onPurge={() => handlePurge(entry.id)}
                  retrying={activeId === entry.id && activeAction === "retry"}
                  purging={activeId === entry.id && activeAction === "purge"}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
