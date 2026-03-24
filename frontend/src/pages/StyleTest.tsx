import { useTheme } from "@/contexts/ThemeContext";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Moon, Sun, Monitor } from "lucide-react";

export function StyleTest() {
  const { theme, setTheme, effectiveTheme } = useTheme();

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">
              ReportFlow Style Test
            </h1>
            <p className="text-muted-foreground mt-2">
              Testing the new bold & vibrant dark mode design system
            </p>
          </div>

          {/* Theme Toggle */}
          <div className="flex gap-2">
            <Button
              variant={theme === "light" ? "default" : "outline"}
              size="sm"
              onClick={() => setTheme("light")}
              className="gap-2"
            >
              <Sun className="h-4 w-4" />
              Light
            </Button>
            <Button
              variant={theme === "dark" ? "default" : "outline"}
              size="sm"
              onClick={() => setTheme("dark")}
              className="gap-2"
            >
              <Moon className="h-4 w-4" />
              Dark
            </Button>
            <Button
              variant={theme === "system" ? "default" : "outline"}
              size="sm"
              onClick={() => setTheme("system")}
              className="gap-2"
            >
              <Monitor className="h-4 w-4" />
              System
            </Button>
          </div>
        </div>

        {/* Current Theme Display */}
        <Card className="card-elevated">
          <CardHeader>
            <CardTitle>Current Theme</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <p className="text-foreground">
                <strong>Selected:</strong> {theme}
              </p>
              <p className="text-foreground">
                <strong>Effective:</strong> {effectiveTheme}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Typography */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">Typography</h2>
          <Card className="card-elevated">
            <CardContent className="pt-6 space-y-4">
              <h1 className="text-3xl font-bold text-foreground">
                Heading 1 - Bold & Large
              </h1>
              <h2 className="text-2xl font-semibold text-foreground">
                Heading 2 - Semibold
              </h2>
              <h3 className="text-xl font-semibold text-foreground">
                Heading 3 - Smaller Semibold
              </h3>
              <p className="text-foreground">
                Body text with normal weight and good readability across both
                light and dark modes.
              </p>
              <p className="text-muted-foreground">
                Muted text for secondary information, descriptions, and subtle
                content.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* Color Swatches */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">
            Color System
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="card-elevated">
              <CardContent className="pt-6">
                <div className="w-full h-20 bg-primary rounded-lg mb-3"></div>
                <p className="text-sm font-medium text-foreground">Primary</p>
                <p className="text-xs text-muted-foreground">Electric Blue</p>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardContent className="pt-6">
                <div className="w-full h-20 bg-accent rounded-lg mb-3"></div>
                <p className="text-sm font-medium text-foreground">Accent</p>
                <p className="text-xs text-muted-foreground">Bright Cyan</p>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardContent className="pt-6">
                <div className="w-full h-20 bg-secondary rounded-lg mb-3"></div>
                <p className="text-sm font-medium text-foreground">Secondary</p>
                <p className="text-xs text-muted-foreground">Blue-Gray</p>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardContent className="pt-6">
                <div className="w-full h-20 bg-destructive rounded-lg mb-3"></div>
                <p className="text-sm font-medium text-foreground">
                  Destructive
                </p>
                <p className="text-xs text-muted-foreground">Vibrant Red</p>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Chart Colors */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">
            Chart Colors
          </h2>
          <Card className="card-elevated">
            <CardContent className="pt-6">
              <div className="grid grid-cols-5 gap-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="space-y-2">
                    <div
                      className="w-full h-24 rounded-lg"
                      style={{
                        backgroundColor: `var(--color-chart-${i})`,
                      }}
                    ></div>
                    <p className="text-xs text-center text-muted-foreground">
                      Chart {i}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Buttons */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">Buttons</h2>
          <Card className="card-elevated">
            <CardContent className="pt-6 space-y-4">
              <div className="flex flex-wrap gap-3">
                <Button variant="default" className="button-glow">
                  Primary Button
                </Button>
                <Button variant="secondary">Secondary Button</Button>
                <Button variant="outline">Outline Button</Button>
                <Button variant="ghost">Ghost Button</Button>
                <Button variant="destructive">Destructive Button</Button>
                <Button variant="link">Link Button</Button>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button variant="default" size="sm">
                  Small
                </Button>
                <Button variant="default" size="default">
                  Default
                </Button>
                <Button variant="default" size="lg">
                  Large
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Dashboard Stats Preview */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">
            Dashboard Stats (Preview)
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="card-elevated">
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Pending
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-foreground">0</p>
                <p className="text-xs text-muted-foreground mt-1">
                  All Queues
                </p>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  High Queue
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-foreground">0</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Priority 1
                </p>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Default Queue
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-foreground">0</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Priority 5
                </p>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Low Queue
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-foreground">0</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Priority 9
                </p>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Sidebar Colors Preview */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">
            Sidebar Colors (Preview)
          </h2>
          <Card className="card-elevated">
            <CardContent className="pt-6">
              <div className="bg-sidebar border border-sidebar-border rounded-lg p-4 space-y-3">
                <div className="px-2 py-2 border-b border-sidebar-border">
                  <span className="font-semibold text-sidebar-foreground">
                    ReportFlow
                  </span>
                  <span className="ml-2 text-xs text-sidebar-foreground/60">
                    Admin
                  </span>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-sidebar-accent text-sidebar-accent-foreground font-medium text-sm">
                    <div className="h-4 w-4 bg-current rounded"></div>
                    Active Nav Item
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2 rounded-md text-sidebar-foreground/70 text-sm">
                    <div className="h-4 w-4 bg-current rounded"></div>
                    Inactive Nav Item
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2 rounded-md text-sidebar-foreground/70 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
                    <div className="h-4 w-4 bg-current rounded"></div>
                    Hover Me
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Borders & Shadows */}
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold text-foreground">
            Borders & Shadows
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>No Elevation</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">Standard card</p>
              </CardContent>
            </Card>

            <Card className="card-elevated">
              <CardHeader>
                <CardTitle>With Elevation</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Elevated card with shadow + glow
                </p>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Footer */}
        <div className="pt-8 border-t border-border text-center">
          <p className="text-sm text-muted-foreground">
            ReportFlow Style Test Page • No Authentication Required • Refresh
            browser to see changes
          </p>
        </div>
      </div>
    </div>
  );
}
