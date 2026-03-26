import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Route guard for system admin pages.
 * Only allows users with role='system_admin' to access protected routes.
 * Redirects to /admin/login if not authenticated or not a system admin.
 */
export function SystemAdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth();

  // Not authenticated - redirect to admin login
  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace />;
  }

  // Authenticated but not system_admin - redirect to admin login with error
  if (user?.role !== "system_admin") {
    return <Navigate to="/admin/login" replace />;
  }

  // User is authenticated and is system_admin
  return <>{children}</>;
}
