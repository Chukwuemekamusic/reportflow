import axios from "axios";

export const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredToken();
      // Redirect to portal login if on portal routes, otherwise admin login
      const isPortalRoute = window.location.pathname.startsWith("/portal");
      window.location.href = isPortalRoute ? "/portal/login" : "/admin/login";
    }
    return Promise.reject(error);
  },
);

let _token: string | null = null;

export function setStoredToken(token: string) {
  _token = token;
}

export function getStoredToken(): string | null {
  return _token;
}

export function clearStoredToken() {
  _token = null;
}

/** Best-effort `detail` string from axios-style API errors */
export function getApiErrorDetail(err: unknown): string | undefined {
  if (!err || typeof err !== "object") return undefined;
  const data = (err as { response?: { data?: unknown } }).response?.data;
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return undefined;
}
