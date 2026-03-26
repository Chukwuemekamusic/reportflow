import { Link, useLocation, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  LayoutDashboard,
  Briefcase,
  AlertTriangle,
  CalendarClock,
  Building2,
  LogOut,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/dlq", label: "DLQ", icon: AlertTriangle },
  { to: "/schedules", label: "Schedules", icon: CalendarClock },
  { to: "/tenants", label: "Tenants", icon: Building2 },
];

export function Shell() {
  const { pathname } = useLocation();
  const { logout, user } = useAuth();

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
              <span className="ml-2 text-xs text-sidebar-foreground/60">Admin</span>
            </div>
            <Badge variant="outline" className="text-xs">
              System
            </Badge>
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
