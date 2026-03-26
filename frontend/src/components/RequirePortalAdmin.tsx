import { Navigate } from "react-router-dom";
import { usePortalAuth } from "@/contexts/PortalAuthContext";

/**
 * Route guard for tenant admin pages within the portal.
 * Only allows users with role='admin' (tenant admin) to access protected routes.
 * Redirects to /portal if not authenticated or not a tenant admin.
 */
export function RequirePortalAdmin({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAdmin } = usePortalAuth();

  // Not authenticated - redirect to portal login
  if (!isAuthenticated) {
    return <Navigate to="/portal/login" replace />;
  }

  // Authenticated but not tenant admin - redirect to portal dashboard
  if (!isAdmin) {
    return <Navigate to="/portal" replace />;
  }

  // User is authenticated and is tenant admin
  return <>{children}</>;
}
