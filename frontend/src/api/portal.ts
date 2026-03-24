import { apiClient } from "./client";

export interface RegisterRequest {
  email: string;
  password: string;
  tenant_name: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
}

export interface ReportJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  report_type: string;
  priority: number;
  progress: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  links: {
    self: string;
    stream: string;
    download: string | null;
  };
}

export interface SubmitReportRequest {
  report_type: "sales_summary" | "csv_export" | "pdf_report";
  priority: number;
  filters: {
    region?: "EMEA" | "AMER" | "APAC";
    status?: "active" | "cancelled" | "all";
    date_from?: string;
    date_to?: string;
  };
}

export const portalApi = {
  register: (body: RegisterRequest) =>
    apiClient
      .post<RegisterResponse>("/auth/register", body)
      .then((r) => r.data),

  submitReport: (token: string, body: SubmitReportRequest) =>
    apiClient
      .post<ReportJob>("/reports", body, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.data),

  listReports: (token: string, params?: object) =>
    apiClient
      .get<{ items: ReportJob[]; total: number }>("/reports", {
        headers: { Authorization: `Bearer ${token}` },
        params,
      })
      .then((r) => r.data),

  getReport: (token: string, jobId: string) =>
    apiClient
      .get<ReportJob>(`/reports/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.data),
};
