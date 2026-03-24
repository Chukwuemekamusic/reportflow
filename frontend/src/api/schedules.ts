import { apiClient } from "./client";

export interface Schedule {
  id: string;
  report_type: string;
  cron_expr: string;
  is_active: boolean;
  next_run_at: string;
  last_run_at: string | null;
  created_at: string;
}

export const schedulesApi = {
  list: (params?: object) =>
    apiClient
      .get<{ schedules: Schedule[]; total: number }>("/schedules", { params })
      .then((r) => r.data),
  deactivate: (id: string) =>
    apiClient.delete(`/schedules/${id}`).then((r) => r.data),
};
