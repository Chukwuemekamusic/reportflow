import { Link, useLocation, Outlet } from "react-router-dom";
import { usePortalAuth } from "@/contexts/PortalAuthContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LayoutDashboard, History, LogOut, Zap } from "lucide-react";

const NAV = [
  { to: "/portal/dashboard", label: "New Report", icon: LayoutDashboard },
  { to: "/portal/history", label: "My Reports", icon: History },
];

export function PortalShell() {
  const { pathname } = useLocation();
  const { logout } = usePortalAuth();

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Top nav */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          {/* Brand */}
          <Link
            to="/portal/dashboard"
            className="flex items-center gap-2 font-semibold text-slate-900"
          >
            <Zap className="h-5 w-5 text-blue-600" />
            ReportFlow
          </Link>

          {/* Nav */}
          <nav className="flex items-center gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors",
                  pathname === to
                    ? "bg-slate-100 text-slate-900 font-medium"
                    : "text-slate-500 hover:text-slate-900 hover:bg-slate-50",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            ))}
          </nav>

          {/* Sign out */}
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            className="text-slate-500 gap-1.5"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
