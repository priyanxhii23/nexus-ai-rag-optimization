import { motion } from 'framer-motion'
import { Moon, Sun } from 'lucide-react'
import { Fragment } from 'react'
import { Badge, Card } from '../components/ui'
import { stagger } from '../animations/variants'
import { useTheme } from '../contexts/ThemeContext'
import { usePolling } from '../hooks/usePolling'
import { api } from '../services/api'

export default function Settings() {
  const { theme, toggle } = useTheme()
  const health = usePolling(api.health, 15000)

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-3xl space-y-4 p-6">
      <Card title="Appearance">
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Theme">
          {(['light', 'dark'] as const).map(t => (
            <button key={t} role="radio" aria-checked={theme === t} onClick={() => theme !== t && toggle()}
              className={`flex items-center gap-3 rounded-lg border p-4 text-left text-sm transition-colors ${
                theme === t ? 'border-accent bg-accent-soft' : 'border-line hover:bg-surface-2'}`}>
              {t === 'light' ? <Sun size={16} /> : <Moon size={16} />}
              <span className="capitalize">{t} mode</span>
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">Saved in this browser and restored after refresh.</p>
      </Card>

      <Card title="Backend configuration" action={<Badge>read-only · edit .env</Badge>}>
        {health.data ? (
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted">Environment</dt><dd>{health.data.environment}</dd>
            <dt className="text-muted">API version</dt><dd>{health.data.version}</dd>
            <dt className="text-muted">Mock LLM mode</dt><dd>{health.data.mock_mode ? 'on' : 'off'}</dd>
            {Object.entries(health.data.llm_providers).map(([p, on]) => (
              <Fragment key={p}><dt className="text-muted">{p}</dt><dd>{on ? 'configured' : 'not configured'}</dd></Fragment>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-muted">{health.error ? 'Backend unreachable.' : 'Loading…'}</p>
        )}
        <p className="mt-4 text-xs text-muted">API keys are never sent to the browser — only whether each one is set.</p>
      </Card>
    </motion.div>
  )
}
