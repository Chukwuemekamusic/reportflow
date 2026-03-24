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
    if (error.response.status === 401) {
      clearStoredToken();
      window.location.href = "/login";
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
