import { apiClient } from "./client";

export interface TenantJob {
  job_id: string;
  tenant_id: string;
  user_id: string;
  report_type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  priority: number;
  progress: number;
  created_at: string;
  updated_at?: string;
  error_message?: string;
}

export interface TenantDLQEntry {
  id: string;
  job_id: string;
  tenant_id: string;
  retry_count: number;
  last_error_at?: string;
  error_trace: string;
  resolved: boolean;
  resolved_at?: string;
  created_at?: string;
}

export interface TenantStats {
  tenant_id: string;
  total_jobs: number;
  jobs_by_status: Record<string, number>;
  unresolved_dlq_entries: number;
}

export const tenantAdminApi = {
  /**
   * List all report jobs in the current tenant
   */
  getJobs: (token: string, params?: { status?: string; limit?: number; offset?: number }) =>
    apiClient
      .get<{ jobs: TenantJob[]; total: number; limit: number; offset: number }>("/tenant/jobs", {
        headers: { Authorization: `Bearer ${token}` },
        params,
      })
      .then((r) => r.data),

  /**
   * List DLQ entries in the current tenant
   */
  getDLQ: (token: string, params?: { resolved?: boolean; limit?: number; offset?: number }) =>
    apiClient
      .get<{ items: TenantDLQEntry[]; total: number; limit: number; offset: number }>("/tenant/dlq", {
        headers: { Authorization: `Bearer ${token}` },
        params,
      })
      .then((r) => r.data),

  /**
   * Retry a failed job from the DLQ
   */
  retryDLQ: (token: string, id: string) =>
    apiClient
      .post(`/tenant/dlq/${id}/retry`, null, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.data),

  /**
   * Delete a DLQ entry
   */
  deleteDLQ: (token: string, id: string) =>
    apiClient
      .delete(`/tenant/dlq/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.data),

  /**
   * Get statistics for the current tenant
   */
  getStats: (token: string) =>
    apiClient
      .get<TenantStats>("/tenant/stats", {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.data),
};
