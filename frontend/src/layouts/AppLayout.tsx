import { AnimatePresence, motion } from 'framer-motion'
import { ChevronsLeft, ChevronsRight, Moon, Sun, Zap } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { StatusDot } from '../components/ui'
import { useTheme } from '../contexts/ThemeContext'
import { usePolling } from '../hooks/usePolling'
import { NAV } from '../navigation'
import { api } from '../services/api'

export function AppLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const { theme, toggle } = useTheme()
  const { pathname } = useLocation()
  const health = usePolling(api.health, 10000)
  const current = NAV.find(n => n.path === pathname)

  const backendStatus = health.error ? 'offline' : health.data?.status === 'ok' ? 'ok' : 'pending'
  const backendLabel = health.error ? 'Backend offline' : health.data ? `API v${health.data.version}` : 'Connecting…'

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ---------- Sidebar ---------- */}
      <motion.aside
        animate={{ width: collapsed ? 68 : 232 }}
        transition={{ type: 'spring', stiffness: 400, damping: 40 }}
        className="flex shrink-0 flex-col border-r border-line bg-surface transition-colors"
      >
        <div className="flex h-14 items-center gap-2.5 px-4">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent text-white dark:text-bg">
            <Zap size={16} strokeWidth={2.5} />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="whitespace-nowrap">
                <p className="text-sm font-semibold leading-none">NEXUS AI</p>
                <p className="mt-1 text-[11px] text-muted">RAG optimisation</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3" aria-label="Main">
          {NAV.map(item => (
            <NavLink key={item.path} to={item.path} end title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `group relative flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm transition-colors ${
                  isActive ? 'text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg'}`}>
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span layoutId="nav-active" className="absolute inset-0 rounded-lg bg-accent-soft"
                      transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
                  )}
                  <item.icon size={17} className={`relative shrink-0 ${isActive ? 'text-accent' : ''}`} />
                  {!collapsed && <span className="relative whitespace-nowrap">{item.label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <button onClick={() => setCollapsed(c => !c)}
          className="m-3 flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm text-muted hover:bg-surface-2 hover:text-fg"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          {collapsed ? <ChevronsRight size={17} /> : <><ChevronsLeft size={17} /><span>Collapse</span></>}
        </button>
      </motion.aside>

      {/* ---------- Main column ---------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-bg/80 px-6 backdrop-blur transition-colors">
          <h1 className="text-sm font-medium">{current?.label ?? 'Not found'}</h1>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-xs text-muted" role="status">
              <StatusDot status={backendStatus} />
              {backendLabel}
            </div>
            <button onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              className="grid h-8 w-8 place-items-center rounded-lg border border-line text-muted hover:bg-surface-2 hover:text-fg">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span key={theme} initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }}
                  exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }}>
                  {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
                </motion.span>
              </AnimatePresence>
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
