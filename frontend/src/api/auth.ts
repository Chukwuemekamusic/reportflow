import { apiClient, setStoredToken } from "./client";

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>("/auth/token", {
    email,
    password,
  });
  setStoredToken(response.data.access_token);
  return response.data;
}
