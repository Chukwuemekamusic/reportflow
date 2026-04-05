import { useQuery } from "@tanstack/react-query";
import { adminApi, type QueueStatus } from "@/api/admin";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LineChart, Line, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useEffect, useState } from "react";

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
    </div>
  );
}
