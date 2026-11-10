import { AnimatePresence, motion } from 'framer-motion'
import { Activity, AlertOctagon, Clock, Coins, Database, Pause, Play, Radio, Search, Sparkles, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { stagger } from '../animations/variants'
import { BarsChart, SERIES } from '../components/charts'
import { Alert, Badge, Button, Card, EmptyState, Kpi, PageHeader, Select, StatusDot } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api, type SystemEvent } from '../services/api'
import { int, ms, pct, usd } from '../services/format'

const ICON: Record<string, React.ElementType> = {
  query_received: Activity, embedding: Sparkles, cache_hit: Database, cache_miss: Database, retrieval: Search,
  routing: Zap, llm_call: Zap, llm_error: AlertOctagon, fallback: AlertOctagon, error: AlertOctagon, query_completed: Activity,
}
const FILTERS = ['', 'query_received', 'embedding', 'cache_hit', 'cache_miss', 'retrieval', 'routing', 'llm_call', 'llm_error', 'fallback', 'error', 'query_completed', 'document_uploaded', 'security']
const MAX = 300

export default function Monitoring() {
  const stats = usePolling(api.monitoringStats, 5000)
  const health = usePolling(api.health, 5000)
  const [events, setEvents] = useState<SystemEvent[]>([])
  const [live, setLive] = useState(true)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)
  const lastId = useRef(0)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const fresh = lastId.current ? await api.events(lastId.current, 200) : await api.events(0, 80)
        if (!alive) return
        setError(null)
        if (fresh.length) {
          lastId.current = fresh[fresh.length - 1].id
          setEvents(prev => [...fresh.reverse(), ...prev].slice(0, MAX))
        }
      } catch (e) { if (alive) setError(e instanceof Error ? e.message : 'Polling failed') }
    }
    tick()
    if (!live) return () => { alive = false }
    const id = setInterval(() => !document.hidden && tick(), 1500)
    return () => { alive = false; clearInterval(id) }
  }, [live])

  const s = stats.data
  const shown = filter ? events.filter(e => e.type === filter) : events
  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Live Monitoring" description="Every step of every request as it happens: embedding, cache decision and similarity, retrieval, routing, model execution, tokens, cost and errors."
        actions={<>
          <span className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-xs text-muted"><StatusDot status={health.error ? 'offline' : health.data?.status === 'ok' ? 'ok' : 'degraded'} />{health.error ? 'API offline' : `API ${health.data?.status ?? '…'}`}</span>
          <Button icon={live ? Pause : Play} onClick={() => setLive(l => !l)}>{live ? 'Pause' : 'Resume'}</Button>
        </>} />
      {error && <Alert>{error}</Alert>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi loading={stats.loading} label="Total processed" icon={Activity} value={s?.total_processed} format={int} />
        <Kpi loading={stats.loading} label="Queries (last hour)" icon={Radio} value={s?.queries_last_hour} format={int} />
        <Kpi loading={stats.loading} label="Hit rate (last hour)" icon={Database} tone="accent" value={s?.hit_rate_last_hour} format={n => pct(n)} />
        <Kpi loading={stats.loading} label="Avg latency (last hour)" icon={Clock} value={s?.avg_latency_last_hour_ms} format={ms} hint={s?.p95_latency_last_hour_ms != null ? `p95 ${ms(s.p95_latency_last_hour_ms)}` : undefined} />
        <Kpi loading={stats.loading} label="Cost (last hour)" icon={Coins} value={s ? s.cost_last_hour_usd + s.simulated_cost_last_hour_usd : null} format={usd} hint={s?.simulated_cost_last_hour_usd ? 'includes simulated test-mode cost' : 'estimated'} />
        <Kpi loading={stats.loading} label="Errors (24h)" icon={AlertOctagon} value={s?.errors_last_24h} format={int} />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="Query volume - last 30 minutes" className="lg:col-span-3">
          {s && <BarsChart data={s.per_minute} xKey="minute" format={int} height={180} series={[{ key: 'queries', name: 'Queries', color: SERIES[0] }]} />}
        </Card>
        <Card title="Service status" className="lg:col-span-2">
          {health.data ? (
            <ul className="space-y-2.5 text-sm">
              {Object.entries(health.data.components).map(([k, c]) => (
                <li key={k} className="flex items-center gap-2.5"><StatusDot status={c.status} /><span className="capitalize">{k.replace('_', ' ')}</span><span className="ml-auto truncate pl-3 text-[11px] text-faint" title={c.detail}>{c.detail}</span></li>
              ))}
              <li className="flex items-center gap-2.5 border-t border-line pt-2.5 text-xs text-muted">Model usage (last hour): {s && Object.keys(s.model_usage_last_hour).length ? Object.entries(s.model_usage_last_hour).map(([m, n]) => `${m.split(':')[1]} ×${n}`).join(', ') : 'none'}</li>
            </ul>
          ) : <p className="text-sm text-muted">{health.error ? 'Backend unreachable' : 'Loading…'}</p>}
        </Card>
      </div>

      <Card title={<span className="flex items-center gap-2">Event stream {live && <span className="flex items-center gap-1.5 text-[11px] font-normal text-ok"><StatusDot status="ok" />live</span>}</span>}
        subtitle="Newest first · polled every 1.5 s · event data never contains document text or answers"
        action={<Select aria-label="Filter events" value={filter} onChange={e => setFilter(e.target.value)} className="w-44">{FILTERS.map(f => <option key={f} value={f}>{f ? f.replace('_', ' ') : 'All events'}</option>)}</Select>}>
        {shown.length ? (
          <ul className="scrollbar-thin -mx-2 max-h-[560px] overflow-y-auto">
            <AnimatePresence initial={false}>
              {shown.map(e => {
                const Icon = ICON[e.type] ?? Activity
                return (
                  <motion.li key={e.id} layout initial={{ opacity: 0, x: -8, backgroundColor: 'var(--accent-soft)' }} animate={{ opacity: 1, x: 0, backgroundColor: 'rgba(0,0,0,0)' }} transition={{ duration: 0.6 }}
                    className="flex items-start gap-3 rounded-lg px-2 py-2">
                    <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md ${e.level === 'error' ? 'bg-err/10 text-err' : e.level === 'warning' ? 'bg-warn/10 text-warn' : e.type === 'cache_hit' ? 'bg-ok/10 text-ok' : 'bg-surface-2 text-muted'}`}><Icon size={13} /></span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm">{e.message}</p>
                      <p className="mt-0.5 flex flex-wrap gap-x-3 text-[11px] text-faint">
                        <span>{new Date(e.created_at).toLocaleTimeString()}</span><span>{e.type}</span>{e.request_id && <span>request #{e.request_id}</span>}
                        {e.data && typeof e.data.similarity === 'number' && <span>similarity {(e.data.similarity as number).toFixed(3)}</span>}
                      </p>
                    </div>
                    {e.level !== 'info' && <Badge tone={e.level === 'error' ? 'err' : 'warn'}>{e.level}</Badge>}
                  </motion.li>
                )
              })}
            </AnimatePresence>
          </ul>
        ) : <EmptyState icon={<Radio size={18} />} title="Waiting for events" body="Ask a question in the Playground (in another tab) and watch each pipeline stage appear here." />}
      </Card>
    </motion.div>
  )
}
