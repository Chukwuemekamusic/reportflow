import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { PortalAuthProvider } from "@/contexts/PortalAuthContext";
import { Toaster } from "@/components/ui/toaster";
import { SystemAdminRoute } from "@/components/SystemAdminRoute";
import { RequirePortalAdmin } from "@/components/RequirePortalAdmin";
import { Shell } from "@/components/Shell";
import { PortalShell } from "@/components/portal/PortalShell";
import { PortalProtectedRoute } from "@/components/portal/PortalProtectedRoute";
import { Register } from "@/pages/portal/Register";
import { PortalLogin } from "@/pages/portal/PortalLogin";
import { PortalDashboard } from "@/pages/portal/PortalDashboard";
import { JobHistory } from "@/pages/portal/JobHistory";
import { TeamManagement } from "@/pages/portal/TeamManagement";
import { TenantJobs } from "@/pages/portal/TenantJobs";
import { Login } from "@/pages/Login";
import { Dashboard } from "@/pages/Dashboard";
import { StyleTest } from "@/pages/StyleTest";
import { Jobs } from "@/pages/Jobs";
import { DeadLetter } from "@/pages/DeadLetter";
import { Schedules } from "@/pages/Schedules";
import { Tenants } from "@/pages/Tenants";

import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 5_000 },
  },
});

function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              {/* portal routes  */}
              <Route
                path="/portal/register"
                element={
                  <PortalAuthProvider>
                    <Register />
                  </PortalAuthProvider>
                }
              />
              <Route
                path="/portal/login"
                element={
                  <PortalAuthProvider>
                    <PortalLogin />
                  </PortalAuthProvider>
                }
              />

              <Route
                path="/portal"
                element={
                  <PortalAuthProvider>
                    <PortalProtectedRoute>
                      <PortalShell />
                    </PortalProtectedRoute>
                  </PortalAuthProvider>
                }
              >
                <Route path="dashboard" element={<PortalDashboard />} />
                <Route path="history" element={<JobHistory />} />

                {/* Tenant admin routes - require admin role */}
                <Route
                  path="team"
                  element={
                    <RequirePortalAdmin>
                      <TeamManagement />
                    </RequirePortalAdmin>
                  }
                />
                <Route
                  path="jobs"
                  element={
                    <RequirePortalAdmin>
                      <TenantJobs />
                    </RequirePortalAdmin>
                  }
                />
                <Route
                  path="dlq"
                  element={
                    <RequirePortalAdmin>
                      <div>Tenant DLQ (Coming Soon)</div>
                    </RequirePortalAdmin>
                  }
                />
                <Route
                  path="stats"
                  element={
                    <RequirePortalAdmin>
                      <div>Tenant Stats (Coming Soon)</div>
                    </RequirePortalAdmin>
                  }
                />
              </Route>

              {/* system admin routes */}
              <Route path="/admin/login" element={<Login />} />
              <Route path="/test" element={<StyleTest />} />
              <Route
                element={
                  <SystemAdminRoute>
                    <Shell />
                  </SystemAdminRoute>
                }
              >
                <Route path="/" element={<Dashboard />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="/dlq" element={<DeadLetter />} />
                <Route path="/schedules" element={<Schedules />} />
                <Route path="/tenants" element={<Tenants />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
      <Toaster />
    </ThemeProvider>
  );
}

export default App;
