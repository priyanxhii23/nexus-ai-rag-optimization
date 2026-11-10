import { motion } from 'framer-motion'
import { Activity, BarChart3, Clock, Database, DollarSign, Layers, PiggyBank, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AnimatedNumber, Badge, Card, EmptyState, Skeleton, StatusDot } from '../components/ui'
import { stagger } from '../animations/variants'
import { usePolling } from '../hooks/usePolling'
import { api } from '../services/api'

const pct = (n: number) => `${(n * 100).toFixed(1)}%`
const ms = (n: number) => `${Math.round(n)} ms`
const usd = (n: number) => `$${n.toFixed(4)}`
const int = (n: number) => Math.round(n).toLocaleString()

export default function Overview() {
  const metrics = usePolling(api.overview, 10000)
  const health = usePolling(api.health, 10000)
  const m = metrics.data

  const tiles = [
    { label: 'Total queries', icon: Activity, value: m?.total_queries ?? null, fmt: int },
    { label: 'Cache hit rate', icon: Database, value: m?.cache_hit_rate ?? null, fmt: pct },
    { label: 'Avg latency', icon: Clock, value: m?.avg_latency_ms ?? null, fmt: ms },
    { label: 'Estimated API cost', icon: DollarSign, value: m?.has_data ? m.estimated_cost_usd : null, fmt: usd },
    { label: 'LLM calls made', icon: Zap, value: m?.has_data ? m.llm_calls : null, fmt: int },
    { label: 'LLM calls avoided', icon: PiggyBank, value: m?.has_data ? m.llm_calls_avoided : null, fmt: int },
  ]

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-6">
      {metrics.error && (
        <div role="alert" className="rounded-lg border border-err/30 bg-err/10 px-4 py-3 text-sm text-err">
          Can't reach the backend ({metrics.error}). Start it with <code className="font-mono">uvicorn app.main:app --reload</code>.
        </div>
      )}

      {m && !m.has_data && (
        <Card>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium">No queries processed yet</p>
              <p className="mt-1 text-sm text-muted">
                Metrics appear here once real questions flow through the pipeline. Nothing on this page is pre-filled.
              </p>
            </div>
            <Link to="/documents"
              className="inline-flex h-9 shrink-0 items-center rounded-lg bg-accent px-4 text-sm font-medium text-white hover:opacity-90 dark:text-bg">
              Go to Document Library
            </Link>
          </div>
        </Card>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {tiles.map(t => (
          <Card key={t.label} className="!p-4">
            <div className="flex items-center justify-between text-muted">
              <span className="text-xs">{t.label}</span>
              <t.icon size={14} />
            </div>
            <div className="mt-3 text-2xl font-semibold tracking-tight tabular">
              {metrics.loading ? <Skeleton className="h-7 w-20" />
                : t.value === null ? <span className="text-muted">—</span>
                : <AnimatedNumber value={t.value} format={t.fmt} />}
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Cost trend" action={<Badge>estimated</Badge>}>
          <EmptyState icon={<BarChart3 size={20} />} title="No cost data yet"
            body="Plotted from token counts × configured pricing once LLM calls are made (Milestone 7)." />
        </Card>
        <Card title="Latency trend">
          <EmptyState icon={<Clock size={20} />} title="No latency data yet"
            body="Every request's end-to-end latency is logged and charted here." />
        </Card>
        <Card title="Cache hits vs misses">
          <EmptyState icon={<Database size={20} />} title="Cache is empty"
            body="Exact hits, semantic hits and misses will be broken down here (Milestone 5)." />
        </Card>
        <Card title="Model distribution">
          <EmptyState icon={<Layers size={20} />} title="No models called yet"
            body="Share of requests routed to each configured model (Milestone 6)." />
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Recent activity" className="lg:col-span-2">
          {m && m.recent_activity.length > 0 ? (
            <ul className="divide-y divide-line">
              {m.recent_activity.map(a => (
                <li key={a.id} className="flex items-center justify-between py-2.5 text-sm">
                  <span className="truncate">{a.query_text}</span>
                  <span className="flex items-center gap-3 text-xs text-muted">
                    <Badge tone={a.cache_status === 'miss' ? 'neutral' : 'ok'}>{a.cache_status}</Badge>
                    {ms(a.total_latency_ms)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={<Activity size={20} />} title="No activity yet" body="Each question you ask will appear here in real time." />
          )}
        </Card>

        <Card title="System health" action={health.data && <span className="text-xs text-muted tabular">up {Math.round(health.data.uptime_seconds)}s</span>}>
          {health.loading ? (
            <div className="space-y-3"><Skeleton className="h-5" /><Skeleton className="h-5" /><Skeleton className="h-5" /></div>
          ) : health.error ? (
            <p className="text-sm text-err">Backend unreachable</p>
          ) : health.data && (
            <ul className="space-y-3 text-sm">
              {Object.entries(health.data.components).map(([name, c]) => (
                <li key={name} className="flex items-start gap-3">
                  <span className="mt-1.5"><StatusDot status={c.status} /></span>
                  <div className="min-w-0">
                    <p className="capitalize">{name.replace('_', ' ')}</p>
                    <p className="truncate text-xs text-muted" title={c.detail}>{c.detail}</p>
                  </div>
                </li>
              ))}
              <li className="border-t border-line pt-3">
                <p className="mb-2 text-xs text-muted">LLM providers configured</p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(health.data.llm_providers).map(([p, on]) => (
                    <Badge key={p} tone={on ? 'accent' : 'neutral'}>{p.replace('_', '-')}{on ? '' : ' · no key'}</Badge>
                  ))}
                </div>
              </li>
            </ul>
          )}
        </Card>
      </div>
    </motion.div>
  )
}
