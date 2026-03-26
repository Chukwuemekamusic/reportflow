import { Link, useLocation, Outlet } from "react-router-dom";
import { usePortalAuth } from "@/contexts/PortalAuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  History,
  LogOut,
  Users,
  Briefcase,
  AlertTriangle,
  BarChart3,
  User,
} from "lucide-react";

const BASE_NAV = [
  { to: "/portal/dashboard", label: "New Report", icon: LayoutDashboard },
  { to: "/portal/history", label: "My Reports", icon: History },
];

const ADMIN_NAV = [
  { to: "/portal/team", label: "Team", icon: Users },
  { to: "/portal/jobs", label: "All Jobs", icon: Briefcase },
  { to: "/portal/dlq", label: "DLQ", icon: AlertTriangle },
  { to: "/portal/stats", label: "Stats", icon: BarChart3 },
];

export function PortalShell() {
  const { pathname } = useLocation();
  const { logout, isAdmin, user } = usePortalAuth();

  const NAV = isAdmin ? [...BASE_NAV, ...ADMIN_NAV] : BASE_NAV;

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 bg-sidebar border-r border-sidebar-border flex flex-col">
        <div className="px-5 py-6 border-b border-sidebar-border">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-semibold text-sidebar-foreground">
                ReportFlow
              </span>
              <span className="ml-2 text-xs text-sidebar-foreground/60">Portal</span>
            </div>
            {isAdmin && (
              <Badge variant="outline" className="text-xs">
                Admin
              </Badge>
            )}
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                pathname === to
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-sidebar-border">
          {user && (
            <div className="px-4 pt-4 pb-2">
              <div className="flex items-start gap-2 text-xs">
                <User className="h-4 w-4 text-sidebar-foreground/60 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sidebar-foreground/90 font-medium truncate">
                    {user.id}
                  </div>
                  <div className="text-sidebar-foreground/60">
                    Tenant: {user.tenantId}
                  </div>
                </div>
              </div>
            </div>
          )}
          <div className="p-4">
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-2"
              onClick={logout}
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </Button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8 xl:p-10">
        <div className="mx-auto w-full max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
