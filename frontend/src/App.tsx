import { useState } from "react";
import {
  LayoutDashboard, Play, FolderOpen, Train, Zap,
  Settings, FileBarChart, BookOpen
} from "lucide-react";
import "./index.css";

import Dashboard  from "./pages/Dashboard";
import Simulation from "./pages/Simulation";
import Projects   from "./pages/Projects";
import Materials  from "./pages/Materials";

type PageId = "dashboard" | "simulation" | "projects" | "materials" | "substations" | "reports" | "settings";

const NAV = [
  {
    section: "Vue d\u0027ensemble",
    items: [
      { id: "dashboard"   as PageId, icon: LayoutDashboard, label: "Tableau de bord" },
    ]
  },
  {
    section: "Simulation",
    items: [
      { id: "simulation"  as PageId, icon: Play,            label: "Lancer une simulation", badge: "v2" },
      { id: "projects"    as PageId, icon: FolderOpen,      label: "Projets" },
    ]
  },
  {
    section: "Base de données",
    items: [
      { id: "materials"   as PageId, icon: Train,           label: "Matériel roulant" },
      { id: "substations" as PageId, icon: Zap,             label: "Sous-stations" },
    ]
  },
  {
    section: "Rapports & config",
    items: [
      { id: "reports"     as PageId, icon: FileBarChart,    label: "Rapports" },
      { id: "settings"    as PageId, icon: Settings,        label: "Paramètres" },
    ]
  },
];

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="fade-in-up">
      <div className="page-header"><h1>{title}</h1></div>
      <div className="card" style={{ textAlign: "center", padding: 60, color: "var(--clr-muted)" }}>
        <BookOpen size={48} style={{ margin: "0 auto 16px", opacity: 0.3 }} />
        <p>Cette section est en cours de développement.</p>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<PageId>("dashboard");
  const [projetSimule, setProjetSimule] = useState<string | undefined>();

  const simulerProjet = (id: string) => {
    setProjetSimule(id);
    setPage("simulation");
  };

  const renderPage = () => {
    switch (page) {
      case "dashboard":   return <Dashboard />;
      case "simulation":  return <Simulation key={projetSimule} projectId={projetSimule} />;
      case "projects":    return <Projects onSimuler={simulerProjet} />;
      case "materials":   return <Materials />;
      default:            return <PlaceholderPage title={page.charAt(0).toUpperCase() + page.slice(1)} />;
    }
  };

  return (
    <div className="app-shell">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-logo">
          <Zap size={22} style={{ color: "#3b82f6" }} />
          <span>Sim<span className="gradient">Traction</span></span>
          <span style={{ fontSize: "0.65rem", fontWeight: 400, color: "var(--clr-muted)" }}>Pro</span>
        </div>
        <span className="topbar-badge">v2.0</span>
        <div className="topbar-spacer" />
        <div className="topbar-user">
          <span>Brahim Ait Lakhyar</span>
          <div className="avatar">B</div>
        </div>
      </header>

      {/* ── Sidebar ── */}
      <nav className="sidebar">
        {NAV.map(section => (
          <div key={section.section} className="sidebar-section">
            <div className="sidebar-section-label">{section.section}</div>
            {section.items.map(item => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`nav-item ${page === item.id ? "active" : ""}`}
                  onClick={() => setPage(item.id)}
                >
                  <Icon className="nav-icon" />
                  {item.label}
                  {item.badge && <span className="nav-badge">{item.badge}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* ── Main ── */}
      <main className="main-content">
        {renderPage()}
      </main>
    </div>
  );
}
