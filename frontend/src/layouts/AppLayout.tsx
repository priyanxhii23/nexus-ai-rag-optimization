import { AnimatePresence, motion } from 'framer-motion'
import { ChevronsLeft, ChevronsRight, FlaskConical, Menu, Moon, Sun, X, Zap } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { StatusDot } from '../components/ui'
import { useTheme } from '../contexts/ThemeContext'
import { usePolling } from '../hooks/usePolling'
import { NAV } from '../navigation'
import { api } from '../services/api'

function readCollapsed() {
  try { return localStorage.getItem('nexus-sidebar') === 'collapsed' } catch { return false }
}

function SidebarContent({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  return (
    <>
      <div className="flex h-14 items-center gap-2.5 px-4">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-accent to-cyan text-white shadow-sm">
          <Zap size={16} strokeWidth={2.5} />
        </div>
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -4 }} className="whitespace-nowrap">
              <p className="text-sm font-semibold leading-none tracking-tight">NEXUS AI</p>
              <p className="mt-1 text-[11px] text-faint">RAG optimisation platform</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <nav className="scrollbar-thin flex-1 space-y-0.5 overflow-y-auto px-3 py-3" aria-label="Main">
        {NAV.map(item => (
          <NavLink key={item.path} to={item.path} end onClick={onNavigate} title={collapsed ? item.label : undefined}
            className={({ isActive }) => `focus-ring group relative flex h-9 items-center gap-3 rounded-lg px-2.5 text-[13px] transition-colors ${
              isActive ? 'text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg'}`}>
            {({ isActive }) => (
              <>
                {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-lg bg-accent-soft ring-1 ring-inset ring-accent/15"
                  transition={{ type: 'spring', stiffness: 500, damping: 40 }} />}
                <item.icon size={17} className={`relative shrink-0 transition-colors ${isActive ? 'text-accent' : ''}`} />
                {!collapsed && <span className="relative whitespace-nowrap font-medium">{item.label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </>
  )
}

export function AppLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { theme, toggle } = useTheme()
  const { pathname } = useLocation()
  const health = usePolling(api.health, 10000)
  const current = NAV.find(n => n.path === pathname)

  useEffect(() => { try { localStorage.setItem('nexus-sidebar', collapsed ? 'collapsed' : 'expanded') } catch { /* ignore */ } }, [collapsed])
  useEffect(() => { document.title = current ? `${current.label} · NEXUS AI` : 'NEXUS AI' }, [current])

  const backendStatus = health.error ? 'offline' : health.data?.status === 'ok' ? 'ok' : health.data ? 'degraded' : 'pending'
  const backendLabel = health.error ? 'Backend offline' : health.data ? `API v${health.data.version}` : 'Connecting…'

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* ---------- Desktop sidebar ---------- */}
      <motion.aside animate={{ width: collapsed ? 68 : 236 }} transition={{ type: 'spring', stiffness: 400, damping: 40 }}
        className="glass hidden shrink-0 flex-col border-r border-line lg:flex">
        <SidebarContent collapsed={collapsed} />
        <button onClick={() => setCollapsed(c => !c)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="focus-ring m-3 flex h-9 items-center gap-3 rounded-lg px-2.5 text-[13px] text-muted hover:bg-surface-2 hover:text-fg">
          {collapsed ? <ChevronsRight size={17} /> : <><ChevronsLeft size={17} /><span>Collapse</span></>}
        </button>
      </motion.aside>

      {/* ---------- Mobile drawer ---------- */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
            <motion.aside initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }} transition={{ type: 'spring', stiffness: 400, damping: 40 }}
              className="relative flex h-full w-64 flex-col border-r border-line bg-surface">
              <button onClick={() => setMobileOpen(false)} aria-label="Close menu" className="absolute right-3 top-3.5 rounded-md p-1.5 text-muted hover:bg-surface-2"><X size={16} /></button>
              <SidebarContent collapsed={false} onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---------- Main column ---------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-line px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <button onClick={() => setMobileOpen(true)} aria-label="Open menu" className="focus-ring -ml-1 rounded-md p-1.5 text-muted hover:bg-surface-2 lg:hidden"><Menu size={18} /></button>
            <p className="truncate text-sm font-medium">{current?.label ?? 'Not found'}</p>
          </div>
          <div className="flex items-center gap-2">
            {health.data?.mock_mode && (
              <span title="No LLM API key configured (or LLM_MOCK_MODE=true). Answers come from a labelled mock provider."
                className="hidden items-center gap-1.5 rounded-lg border border-warn/30 bg-warn/10 px-2.5 py-1.5 text-xs font-medium text-warn sm:flex">
                <FlaskConical size={13} /> Test mode
              </span>
            )}
            <div className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-xs text-muted" role="status" aria-live="polite">
              <StatusDot status={backendStatus} />
              <span className="hidden sm:inline">{backendLabel}</span>
            </div>
            <button onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              className="focus-ring grid h-8 w-8 place-items-center rounded-lg border border-line text-muted hover:bg-surface-2 hover:text-fg">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span key={theme} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }}>
                  {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
                </motion.span>
              </AnimatePresence>
            </button>
          </div>
        </header>
        <main className="scrollbar-thin flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
