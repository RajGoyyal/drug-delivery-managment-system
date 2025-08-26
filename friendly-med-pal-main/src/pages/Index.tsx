import { useState, useMemo, useEffect } from "react";
import { Activity, Users, Pill, FileText, Package, Boxes } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { RefreshButton } from "@/components/RefreshButton";
import Dashboard from "@/components/Dashboard";
import PatientsPanel from "@/components/PatientsPanel";
import DrugsPanel from "@/components/DrugsPanel";
import DeliveriesPanel from "@/components/DeliveriesPanel";
import DeliveryHistory from "@/components/DeliveryHistory";

interface TabDef { id:string; label:string; icon: React.ComponentType<any>; component: JSX.Element; }

// Simple placeholder inventory component until full feature ported
function InventoryPlaceholder(){
  return (
    <div className="border rounded-lg p-6 bg-card/50">
      <h2 className="text-xl font-semibold mb-2">Inventory (Coming Soon)</h2>
      <p className="text-sm text-muted-foreground mb-4">Detailed stock levels, pending quantities, daily averages and transaction history will appear here after migration.</p>
      <ul className="text-sm list-disc pl-5 space-y-1">
        <li>Low stock detection & metrics</li>
        <li>Adjust stock with reason codes</li>
        <li>Pending reservations & days supply</li>
        <li>CSV export & transaction log</li>
      </ul>
    </div>
  );
}

const tabs: TabDef[] = [
  { id: 'dashboard', label: 'Dashboard', icon: Activity, component: <Dashboard/> },
  { id: 'patients', label: 'Patients', icon: Users, component: <PatientsPanel/> },
  { id: 'drugs', label: 'Drugs', icon: Pill, component: <DrugsPanel/> },
  { id: 'deliveries', label: 'Deliveries', icon: Package, component: <DeliveriesPanel/> },
  { id: 'history', label: 'History', icon: FileText, component: <DeliveryHistory/> },
  { id: 'inventory', label: 'Inventory', icon: Boxes, component: <InventoryPlaceholder/> },
  // Future: inventory, analytics, settings...
];

export default function Index(){
  const [active, setActive] = useState<string>('dashboard');

  // Sync tab with URL hash for direct access (e.g., /#patients)
  useEffect(()=>{
    const applyHash = () => {
      const hash = (window.location.hash || '').replace('#','');
      if(hash && tabs.some(t=> t.id===hash)) {
        setActive(hash);
      }
    };
    applyHash();
    window.addEventListener('hashchange', applyHash);
    return ()=> window.removeEventListener('hashchange', applyHash);
  },[]);

  const changeTab = (id:string) => {
    setActive(id);
    if(window.location.hash !== `#${id}`) {
      history.replaceState(null,'',`#${id}`); // avoid scroll jump
    }
  };

  const activeComponent = useMemo(()=> tabs.find(t=> t.id===active)?.component ?? tabs[0].component, [active]);

  return (
    <div className="h-screen flex bg-background text-foreground overflow-hidden relative">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_25%_20%,hsl(var(--primary)/0.08),transparent_60%),radial-gradient(circle_at_80%_70%,hsl(var(--accent)/0.08),transparent_65%)]" />
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col relative z-10">
        <div className="h-16 px-3 flex items-center gap-2 border-b border-border/60 justify-between">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center text-primary-foreground">
              <Activity className="w-5 h-5" />
            </div>
            <span className="font-semibold tracking-tight">MedDelivery</span>
          </div>
          <div className="flex items-center gap-2">
            <RefreshButton />
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2">
          {tabs.map(tab=>{
            const Icon = tab.icon;
            const activeTab = tab.id===active;
            return (
              <button
                key={tab.id}
                onClick={()=> changeTab(tab.id)}
                className={[
                  'w-full group flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  activeTab ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                ].join(' ')}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="p-3 text-[10px] text-muted-foreground border-t border-border/60 flex items-center justify-between">
          <span>v2 • {new Date().getFullYear()}</span>
          <ThemeToggle />
        </div>
      </aside>
      {/* Main content */}
      <main className="flex-1 overflow-y-auto relative z-0">
        <div className="max-w-7xl mx-auto p-6 space-y-6 relative">
          {activeComponent}
        </div>
      </main>
    </div>
  );
}
