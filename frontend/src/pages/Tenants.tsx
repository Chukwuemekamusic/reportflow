import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type Tenant } from "@/api/admin";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDistanceToNow } from "date-fns";
import { CheckCircle, XCircle } from "lucide-react";

export function Tenants() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["tenants"],
    queryFn: adminApi.getTenants,
  });

  const toggle = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      adminApi.updateTenant(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenants"] }),
  });

  return (
    <div className="space-y-6 lg:space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Tenants</h1>
        <Badge variant="outline">{data?.total ?? 0} total</Badge>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <div className="border border-border rounded-xl overflow-hidden bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b border-border">
              <tr>
                {["Name", "Slug", "Status", "Jobs", "Created", "Action"].map(
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
              {data?.tenants.map((t: Tenant) => (
                <tr key={t.id} className="border-b border-border hover:bg-muted/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-foreground">{t.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {t.slug}
                  </td>
                  <td className="px-4 py-3">
                    {t.is_active ? (
                      <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                        <CheckCircle className="h-3 w-3" /> Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <XCircle className="h-3 w-3" /> Disabled
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-foreground">{t.total_jobs}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(t.created_at), {
                      addSuffix: true,
                    })}
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant={t.is_active ? "destructive" : "default"}
                      onClick={() =>
                        toggle.mutate({ id: t.id, is_active: !t.is_active })
                      }
                      disabled={toggle.isPending}
                    >
                      {t.is_active ? "Disable" : "Enable"}
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
