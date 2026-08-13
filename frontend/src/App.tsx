import { Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ThemeToggle } from "./components/ThemeToggle";
import { cn } from "./lib/utils";
import { About } from "./routes/About";
import { Methodology } from "./routes/Methodology";
import { Results } from "./routes/Results";
import { Setup } from "./routes/Setup";
import { useOptimize } from "./state/useOptimize";
import { useSyncConfigToUrl } from "./state/urlState";

interface NavItem {
  to: string;
  label: string;
  requiresRun?: boolean;
}

const NAV: NavItem[] = [
  { to: "/setup", label: "1. Set up" },
  { to: "/results", label: "2. Results", requiresRun: true },
  { to: "/methodology", label: "How it works" },
  { to: "/about", label: "About" },
];

function Header(): JSX.Element {
  const { hasValidConfig, hasRun } = useOptimize();
  const location = useLocation();
  return (
    <header className="border-b bg-card/70 backdrop-blur sticky top-0 z-30">
      <div className="container flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            Stochastic Inventory Explorer
          </h1>
          <p className="text-xs text-muted-foreground">
            Educational demo, not an inventory management or purchasing system.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <nav className="flex flex-wrap gap-1 text-sm">
            {NAV.map((l) => {
              const disabled = l.requiresRun && !(hasValidConfig && hasRun);
              const active = location.pathname.startsWith(l.to);
              if (disabled) {
                return (
                  <span
                    key={l.to}
                    className="rounded-md px-3 py-1.5 text-muted-foreground/50 cursor-not-allowed"
                    title="Pick a scenario on the Set up page first"
                  >
                    {l.label}
                  </span>
                );
              }
              return (
                <NavLink
                  key={l.to}
                  to={l.to}
                  className={cn(
                    "rounded-md px-3 py-1.5 transition-colors",
                    active
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  {l.label}
                </NavLink>
              );
            })}
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function Footer(): JSX.Element {
  return (
    <footer className="border-t bg-card/40 mt-8">
      <div className="container flex flex-col gap-1 py-4 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <div>
          Stochastic Inventory Reorder / Safety Stock Explorer. Open source, MIT licensed.
        </div>
        <div className="flex items-center gap-3">
          <Link to="/methodology" className="hover:text-foreground">
            How it works
          </Link>
          <Link to="/about" className="hover:text-foreground">
            About
          </Link>
        </div>
      </div>
    </footer>
  );
}

function UrlSync(): null {
  useSyncConfigToUrl();
  return null;
}

export default function App(): JSX.Element {
  return (
    <div className="min-h-screen flex flex-col">
      <UrlSync />
      <Header />
      <main className="flex-1 container py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/setup" replace />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/configure" element={<Navigate to="/setup" replace />} />
          <Route path="/results" element={<Results />} />
          <Route path="/frontier" element={<Navigate to="/results?tab=tradeoff" replace />} />
          <Route path="/simulation" element={<Navigate to="/results?tab=futures" replace />} />
          <Route path="/compare" element={<Navigate to="/results?tab=alternatives" replace />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<Navigate to="/setup" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
