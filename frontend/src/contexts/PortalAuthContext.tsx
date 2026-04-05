import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
} from "react";
import { apiClient } from "@/api/client";
import { getUserFromToken, decodeJWT } from "@/utils/jwt";

export interface PortalUser {
  id: string;
  tenantId: string;
  role: "member" | "admin";
}

interface PortalAuthContextType {
  isAuthenticated: boolean;
  token: string | null;
  user: PortalUser | null;
  isAdmin: boolean; // Computed: user?.role === "admin"
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
  const [user, setUser] = useState<PortalUser | null>(null);
  const expireTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const logout = useCallback(() => {
    if (expireTimeoutRef.current) {
      clearTimeout(expireTimeoutRef.current);
      expireTimeoutRef.current = null;
    }
    _portalToken = null;
    setToken(null);
    setUser(null);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await apiClient.post<{ access_token: string }>("/auth/token", {
        email,
        password,
      });
      const accessToken = res.data.access_token;

      // Decode JWT to get user info
      const userInfo = getUserFromToken(accessToken);

      if (!userInfo) {
        throw new Error("Invalid token received from server");
      }

      // Portal accepts both "member" and "admin" roles (tenant-scoped)
      // System admins should use the admin login instead
      if (userInfo.role === "system_admin") {
        throw new Error(
          "System administrators should use the Admin login at /admin/login"
        );
      }

      if (expireTimeoutRef.current) {
        clearTimeout(expireTimeoutRef.current);
        expireTimeoutRef.current = null;
      }

      _portalToken = accessToken;
      setToken(accessToken);
      setUser(userInfo as PortalUser);

      // Set a timer to logout just before the token expires
      const payload = decodeJWT(accessToken);
      if (payload?.exp) {
        const expiresInMs = payload.exp * 1000 - Date.now() - 30_000; // 30s buffer
        if (expiresInMs > 0) {
          expireTimeoutRef.current = setTimeout(() => {
            expireTimeoutRef.current = null;
            logout();
          }, expiresInMs);
        }
      }
    },
    [logout],
  );

  useEffect(() => {
    return () => {
      if (expireTimeoutRef.current) {
        clearTimeout(expireTimeoutRef.current);
      }
    };
  }, []);

  const isAdmin = user?.role === "admin";

  return (
    <PortalAuthContext.Provider
      value={{ isAuthenticated: !!token, token, user, isAdmin, login, logout }}
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
