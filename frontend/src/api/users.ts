import { apiClient } from "./client";

export interface TeamUser {
  id: string;
  email: string;
  role: "member" | "admin";
  tenant_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateUserRequest {
  email: string;
  password: string;
  role: "member" | "admin";
}

export interface UserListResponse {
  items: TeamUser[];
  total: number;
  limit: number;
  offset: number;
}

export const usersApi = {
  /**
   * List all users in the current tenant (admin-only)
   */
  listUsers: (token: string, params?: { limit?: number; offset?: number }) =>
    apiClient
      .get<UserListResponse>("/users", {
        headers: { Authorization: `Bearer ${token}` },
        params,
      })
      .then((r) => r.data),

  /**
   * Create a new user in the current tenant (admin-only)
   */
  createUser: (token: string, body: CreateUserRequest) =>
    apiClient
      .post<TeamUser>("/users", body, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.data),

  /**
   * Deactivate a user (soft delete) - admin-only
   */
  deactivateUser: (token: string, userId: string) =>
    apiClient
      .delete<TeamUser>(`/users/${userId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.data),
};
