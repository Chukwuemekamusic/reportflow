import { Navigate } from "react-router-dom";
import { usePortalAuth } from "@/contexts/PortalAuthContext";

export function PortalProtectedRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated } = usePortalAuth();
  if (!isAuthenticated) return <Navigate to="/portal/login" replace />;
  return <>{children}</>;
}
