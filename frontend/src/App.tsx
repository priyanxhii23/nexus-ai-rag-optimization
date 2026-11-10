import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { Suspense, lazy } from 'react'
import { Link, BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { page } from './animations/variants'
import { ThemeProvider, useTheme } from './contexts/ThemeContext'
import { AppLayout } from './layouts/AppLayout'
const Benchmarks = lazy(() => import('./pages/Benchmarks'))
const CachePage = lazy(() => import('./pages/Cache'))
const Compare = lazy(() => import('./pages/Compare'))
const Cost = lazy(() => import('./pages/Cost'))
const Documents = lazy(() => import('./pages/Documents'))
const Monitoring = lazy(() => import('./pages/Monitoring'))
const Overview = lazy(() => import('./pages/Overview'))
const Playground = lazy(() => import('./pages/Playground'))
const RouterPage = lazy(() => import('./pages/Router'))
const Settings = lazy(() => import('./pages/Settings'))

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <motion.div key={location.pathname} variants={page} initial="initial" animate="animate" exit="exit">
        <Suspense fallback={<div className="p-6"><div className="h-6 w-40 animate-pulse rounded-md bg-surface-2" /></div>}>
        <Routes location={location}>
          <Route path="/" element={<Overview />} />
          <Route path="/playground" element={<Playground />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/cache" element={<CachePage />} />
          <Route path="/router" element={<RouterPage />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/cost" element={<Cost />} />
          <Route path="/benchmarks" element={<Benchmarks />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<div className="p-6 text-sm text-muted">Page not found. <Link className="text-accent" to="/">Back to Overview</Link></div>} />
        </Routes>
        </Suspense>
      </motion.div>
    </AnimatePresence>
  )
}

function Shell() {
  const { reduceMotion } = useTheme()
  return (
    // "user" respects the OS setting; the Settings toggle can force it on.
    <MotionConfig reducedMotion={reduceMotion ? 'always' : 'user'}>
      <BrowserRouter>
        <AppLayout>
          <AnimatedRoutes />
        </AppLayout>
      </BrowserRouter>
    </MotionConfig>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <Shell />
    </ThemeProvider>
  )
}
