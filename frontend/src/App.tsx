import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { PortalAuthProvider } from "@/contexts/PortalAuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Shell } from "@/components/Shell";
import { PortalShell } from "@/components/portal/PortalShell";
import { PortalProtectedRoute } from "@/components/portal/PortalProtectedRoute";
import { Register } from "@/pages/portal/Register";
import { PortalLogin } from "@/pages/portal/PortalLogin";
import { PortalDashboard } from "@/pages/portal/PortalDashboard";
import { JobHistory } from "@/pages/portal/JobHistory";
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
              </Route>

              {/* admin routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/test" element={<StyleTest />} />
              <Route
                element={
                  <ProtectedRoute>
                    <Shell />
                  </ProtectedRoute>
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
    </ThemeProvider>
  );
}

export default App;
