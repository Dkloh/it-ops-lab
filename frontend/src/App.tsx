import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { PageBoundary } from "./components/PageBoundary";
import { OverviewPage } from "./pages/Overview";
import { ServicesPage } from "./pages/Services";
import { LogsPage } from "./pages/Logs";
import { DiagnosticsPage } from "./pages/Diagnostics";
import { NetworkPage } from "./pages/Network";
export default function App() {
  const location = useLocation();
  return (
    <div className="app-shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside>
        <div className="brand">
          <span className="brand-mark">IT</span>
          <div>
            Ops Lab<small>INCIDENT INVESTIGATION</small>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {[
            ["/", "Overview"],
            ["/services", "Services"],
            ["/logs", "Logs"],
            ["/diagnostics", "Diagnostics"],
            ["/network", "Network Checks"],
          ].map(([path, label]) => (
            <NavLink key={path} to={path} end={path === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
        <p className="sidebar-note">
          LOCAL WORKSPACE
          <br />
          Evidence before conclusions.
          <br />
          All timestamps shown in UTC.
        </p>
      </aside>
      <main id="main" tabIndex={-1}>
        <PageBoundary key={location.pathname}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/services" element={<ServicesPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/diagnostics" element={<DiagnosticsPage />} />
            <Route path="/network" element={<NetworkPage />} />
            <Route path="*" element={<h1>Page not found</h1>} />
          </Routes>
        </PageBoundary>
        <footer>
          IT Ops Lab · Local investigation workspace · No automatic network
          checks
        </footer>
      </main>
    </div>
  );
}
