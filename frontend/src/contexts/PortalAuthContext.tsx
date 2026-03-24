import React, { createContext, useContext, useState, useCallback } from "react";
import { apiClient } from "@/api/client";

interface PortalAuthContextType {
  isAuthenticated: boolean;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const PortalAuthContext = createContext<PortalAuthContextType | null>(null);

// Separate in-memory token for portal users — never touches admin token
let _portalToken: string | null = null;
export function getPortalToken() {
  return _portalToken;
}

export function PortalAuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [token, setToken] = useState<string | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiClient.post<{ access_token: string }>("/auth/token", {
      email,
      password,
    });
    _portalToken = res.data.access_token;
    setToken(_portalToken);
    // Set a timer to logout just before the token expires
    const payload = JSON.parse(atob(_portalToken.split(".")[1])) as {
      exp: number;
    };
    const expiresInMs = payload.exp * 1000 - Date.now() - 30_000; // 30s buffer
    setTimeout(() => logout(), expiresInMs);
  }, []);

  const logout = useCallback(() => {
    _portalToken = null;
    setToken(null);
  }, []);

  return (
    <PortalAuthContext.Provider
      value={{ isAuthenticated: !!token, token, login, logout }}
    >
      {children}
    </PortalAuthContext.Provider>
  );
}

export function usePortalAuth() {
  const ctx = useContext(PortalAuthContext);
  if (!ctx)
    throw new Error("usePortalAuth must be used inside PortalAuthProvider");
  return ctx;
}
