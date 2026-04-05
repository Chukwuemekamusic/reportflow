import { apiClient } from "./client";

export interface QueueStatus {
  queues: { high: number; default: number; low: number };
  total_pending: number;
}

export interface AdminJob {
  job_id: string;
  tenant_id: string;
  report_type: string;
  status: string;
  priority: number;
  created_at: string;
  error_message?: string;
}

export interface DLQEntry {
  id: string;
  job_id: string;
  tenant_id: string;
  retry_count: number;
  error_trace: string;
  last_error_at: string;
  resolved: boolean;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  total_jobs: number;
}

export interface CleanupJobsResponse {
  deleted?: number;
  would_delete?: number;
  cutoff_date: string;
  status_filter: string;
  older_than_days: number;
  dry_run?: boolean;
}

export const adminApi = {
  getQueue: () =>
    apiClient.get<QueueStatus>("/admin/queue").then((r) => r.data),
  getJobs: (params?: object) =>
    apiClient
      .get<{ jobs: AdminJob[]; total: number }>("/admin/jobs", { params })
      .then((r) => r.data),
  getDLQ: () =>
    apiClient
      .get<{ items: DLQEntry[]; total: number }>("/admin/dlq")
      .then((r) => r.data),
  retryDLQ: (id: string) =>
    apiClient.post(`/admin/dlq/${id}/retry`).then((r) => r.data),
  purgeDLQ: (id: string) => apiClient.delete(`/admin/dlq/${id}`),
  getTenants: () =>
    apiClient
      .get<{ tenants: Tenant[]; total: number }>("/admin/tenants")
      .then((r) => r.data),
  updateTenant: (id: string, body: { is_active: boolean }) =>
    apiClient.put(`/admin/tenants/${id}`, body).then((r) => r.data),
  cleanupJobs: (params: {
    older_than_days: number;
    status_filter?: string;
    dry_run?: boolean;
  }) =>
    apiClient
      .delete<CleanupJobsResponse>("/admin/jobs/cleanup", { params })
      .then((r) => r.data),
};
