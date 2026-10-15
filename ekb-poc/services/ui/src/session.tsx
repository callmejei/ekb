import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, storedUser, storeUser, type Stats, type User } from "./api";

interface Session {
  user: User | null;
  loading: boolean;
  signIn: (username: string) => Promise<void>;
  signOut: () => void;
  stats: Stats | null;
  refreshStats: () => void;
  theme: "dark" | "light";
  toggleTheme: () => void;
}

const Ctx = createContext<Session | null>(null);

function readTheme(): "dark" | "light" {
  try {
    return localStorage.getItem("ekb-theme") === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Stats | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">(readTheme);

  useEffect(() => {
    document.documentElement.className = `theme-${theme}`;
    try {
      localStorage.setItem("ekb-theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  useEffect(() => {
    if (!storedUser()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => storeUser(null))
      .finally(() => setLoading(false));
  }, []);

  const refreshStats = useCallback(() => {
    if (!storedUser()) return;
    api.stats().then(setStats).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshStats();
    const id = window.setInterval(refreshStats, 8000);
    return () => window.clearInterval(id);
  }, [user, refreshStats]);

  const signIn = useCallback(async (username: string) => {
    storeUser(username);
    setUser(await api.me());
  }, []);

  const signOut = useCallback(() => {
    storeUser(null);
    setUser(null);
    setStats(null);
  }, []);

  return (
    <Ctx.Provider
      value={{
        user,
        loading,
        signIn,
        signOut,
        stats,
        refreshStats,
        theme,
        toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSession(): Session {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}

export const ROLE_LABEL: Record<string, string> = {
  REQUESTOR: "Requestor",
  STEWARD: "Data Steward",
  OWNER: "Data Owner",
  CUSTODIAN: "Data Custodian",
  VIEWER: "Branch Viewer",
  ADMIN: "Administrator",
};
