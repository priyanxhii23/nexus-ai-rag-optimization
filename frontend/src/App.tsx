import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { page } from './animations/variants'
import { ThemeProvider } from './contexts/ThemeContext'
import { AppLayout } from './layouts/AppLayout'
import { NAV } from './navigation'
import Overview from './pages/Overview'
import Settings from './pages/Settings'
import Upcoming from './pages/Upcoming'

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <motion.div key={location.pathname} variants={page} initial="initial" animate="animate" exit="exit">
        <Routes location={location}>
          <Route path="/" element={<Overview />} />
          <Route path="/settings" element={<Settings />} />
          {NAV.filter(n => n.path !== '/' && n.path !== '/settings').map(n => (
            <Route key={n.path} path={n.path} element={<Upcoming item={n} />} />
          ))}
          <Route path="*" element={<p className="p-6 text-sm text-muted">Page not found.</p>} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    // reducedMotion="user" → respects the OS "reduce motion" setting everywhere
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <BrowserRouter>
          <AppLayout>
            <AnimatedRoutes />
          </AppLayout>
        </BrowserRouter>
      </ThemeProvider>
    </MotionConfig>
  )
}
