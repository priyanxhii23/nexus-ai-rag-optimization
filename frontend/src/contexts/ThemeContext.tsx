import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'dark'
const THEME_KEY = 'nexus-theme'
const MOTION_KEY = 'nexus-reduce-motion'

function read(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}
function write(key: string, value: string) {
  try { localStorage.setItem(key, value) } catch { /* storage blocked - theme still works for this session */ }
}

function initialTheme(): Theme {
  const saved = read(THEME_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

interface ThemeValue {
  theme: Theme
  toggle: () => void
  setTheme: (t: Theme) => void
  reduceMotion: boolean
  setReduceMotion: (v: boolean) => void
}

const ThemeCtx = createContext<ThemeValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(initialTheme)
  const [reduceMotion, setReduceMotionState] = useState(() => read(MOTION_KEY) === 'true')

  useEffect(() => {
    const root = document.documentElement
    root.classList.add('theme-transition')
    root.classList.toggle('dark', theme === 'dark')
    write(THEME_KEY, theme)
    const t = window.setTimeout(() => root.classList.remove('theme-transition'), 300)
    return () => window.clearTimeout(t)
  }, [theme])

  useEffect(() => {
    document.documentElement.classList.toggle('reduce-motion', reduceMotion)
    write(MOTION_KEY, String(reduceMotion))
  }, [reduceMotion])

  const setTheme = useCallback((t: Theme) => setThemeState(t), [])
  const toggle = useCallback(() => setThemeState(t => (t === 'dark' ? 'light' : 'dark')), [])

  return (
    <ThemeCtx.Provider value={{ theme, toggle, setTheme, reduceMotion, setReduceMotion: setReduceMotionState }}>
      {children}
    </ThemeCtx.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const ctx = useContext(ThemeCtx)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
