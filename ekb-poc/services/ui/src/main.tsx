import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { SessionProvider, useSession } from "./session";
import { Shell } from "./components/Shell";
import { Spinner } from "./components/ui";
import SignIn from "./pages/SignIn";
import Ask from "./pages/Ask";
import Library from "./pages/Library";
import Upload from "./pages/Upload";
import Tasks from "./pages/Tasks";
import Audit from "./pages/Audit";
import "./styles.css";

function landing(roles: string[]) {
  if (roles.includes("REQUESTOR")) return "/upload";
  if (["STEWARD", "OWNER", "CUSTODIAN"].some((r) => roles.includes(r))) return "/tasks";
  return "/ask";
}

function App() {
  const { user, loading } = useSession();
  if (loading)
    return (
      <div className="flex h-dvh items-center justify-center text-muted">
        <Spinner />
      </div>
    );
  if (!user) return <SignIn />;
  return (
    <Shell>
      <Routes>
        <Route path="/ask" element={<Ask />} />
        <Route path="/library" element={<Library />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="*" element={<Navigate to={landing(user.roles)} replace />} />
      </Routes>
    </Shell>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <App />
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
