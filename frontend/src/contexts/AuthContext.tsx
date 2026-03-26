import React, { createContext, useContext, useState, useCallback } from "react";
import { login as apiLogin } from "../api/auth";
import { clearStoredToken, getStoredToken } from "../api/client";
import { getUserFromToken } from "../utils/jwt";

export interface User {
  id: string;
  tenantId: string;
  role: "member" | "admin" | "system_admin";
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    // Call backend login
    const response = await apiLogin(email, password);

    // Decode JWT to get user info
    const userInfo = getUserFromToken(response.access_token);

    if (!userInfo) {
      throw new Error("Invalid token received from server");
    }

    // IMPORTANT: Only allow system_admin role for admin UI
    if (userInfo.role !== "system_admin") {
      clearStoredToken();
      throw new Error(
        "Access denied. System administrator role required. " +
        "Tenant admins and users should use the Portal login."
      );
    }

    setUser(userInfo);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  // Check for existing token on mount
  React.useEffect(() => {
    const token = getStoredToken();
    if (token) {
      const userInfo = getUserFromToken(token);
      if (userInfo && userInfo.role === "system_admin") {
        setUser(userInfo);
        setIsAuthenticated(true);
      } else {
        // Token invalid or not system admin - clear it
        clearStoredToken();
      }
    }
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
