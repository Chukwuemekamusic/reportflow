import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  effectiveTheme: "light" | "dark";
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Default to dark mode (as per user preference)
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem("reportflow-theme");
    return (stored as Theme) || "dark";
  });

  const [effectiveTheme, setEffectiveTheme] = useState<"light" | "dark">("dark");

  // Update localStorage when theme changes
  useEffect(() => {
    localStorage.setItem("reportflow-theme", theme);
  }, [theme]);

  // Handle system preference and apply dark class to HTML
  useEffect(() => {
    const root = document.documentElement;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const updateTheme = () => {
      let resolvedTheme: "light" | "dark";

      if (theme === "system") {
        resolvedTheme = mediaQuery.matches ? "dark" : "light";
      } else {
        resolvedTheme = theme;
      }

      setEffectiveTheme(resolvedTheme);

      // Apply or remove 'dark' class on HTML element
      if (resolvedTheme === "dark") {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
    };

    // Initial update
    updateTheme();

    // Listen for system preference changes
    mediaQuery.addEventListener("change", updateTheme);

    return () => {
      mediaQuery.removeEventListener("change", updateTheme);
    };
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, effectiveTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
