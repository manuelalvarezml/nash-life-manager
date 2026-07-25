import { useState } from 'react';
import { Home } from './components/tabs/Home';
import { Historial } from './components/tabs/Historial';
import { PerfilConocimiento } from './components/tabs/PerfilConocimiento';
import { SobreMi } from './components/tabs/SobreMi';
import { Metas } from './components/tabs/Metas';
import { Cuerpo } from './components/tabs/Cuerpo';
import { Dinero } from './components/tabs/Dinero';
import { Dev } from './components/tabs/Dev';

const TABS = [
  { id: 'home', label: 'Inicio', implemented: true },
  { id: 'historial', label: 'Historial', implemented: true },
  { id: 'perfil', label: 'Lo que Nash sabe', implemented: true },
  { id: 'sobremi', label: 'Sobre Mi', implemented: true },
  { id: 'work', label: 'Trabajo', implemented: false },
  { id: 'body', label: 'Cuerpo', implemented: true },
  { id: 'mind', label: 'Mente', implemented: false },
  { id: 'money', label: 'Dinero', implemented: true },
  { id: 'goals', label: 'Metas', implemented: true },
  { id: 'progress', label: 'Progreso', implemented: false },
  { id: 'dev', label: 'Dev', implemented: true },
] as const;

type TabId = (typeof TABS)[number]['id'];

function PlaceholderTab({ name }: { name: string }) {
  return (
    <div className="flex items-center justify-center h-64 text-[var(--nash-text-muted)]">
      <p className="text-lg">{name} - proximamente</p>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('home');
  const [threadId] = useState(() => crypto.randomUUID());

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top navigation bar - always visible */}
      <nav className="sticky top-0 z-10 bg-[var(--nash-surface)] border-b border-[var(--nash-border)] shadow-sm">
        <div className="max-w-6xl mx-auto flex overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-5 py-4 text-base font-medium whitespace-nowrap transition-colors cursor-pointer
                ${activeTab === tab.id
                  ? 'text-[var(--nash-accent)] border-b-3 border-[var(--nash-accent)]'
                  : tab.implemented
                    ? 'text-[var(--nash-text-muted)] hover:text-[var(--nash-text)] hover:bg-[var(--nash-surface-2)]'
                    : 'text-[var(--nash-text-muted)]/60 bg-[var(--nash-surface-disabled)]/30'
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="flex-1">
        {activeTab === 'home' && <Home threadId={threadId} />}
        {activeTab === 'historial' && <Historial />}
        {activeTab === 'perfil' && <PerfilConocimiento />}
        {activeTab === 'sobremi' && <SobreMi />}
        {activeTab === 'work' && <PlaceholderTab name="Trabajo" />}
        {activeTab === 'body' && <Cuerpo />}
        {activeTab === 'mind' && <PlaceholderTab name="Mente" />}
        {activeTab === 'money' && <Dinero />}
        {activeTab === 'goals' && <Metas />}
        {activeTab === 'progress' && <PlaceholderTab name="Progreso" />}
        {activeTab === 'dev' && <Dev />}
      </main>
    </div>
  );
}
