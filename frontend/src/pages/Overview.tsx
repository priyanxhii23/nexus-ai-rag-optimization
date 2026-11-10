import { motion } from 'framer-motion'
import { Activity, ArrowRight, BarChart3, Clock, Coins, Database, GitBranch, Layers, PiggyBank, Sigma, Sparkles, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { stagger } from '../animations/variants'
import { BarsChart, SERIES, ShareBar, TIER_COLOR, TrendChart } from '../components/charts'
import { Alert, Badge, CacheBadge, Card, EmptyState, Kpi, MockBadge, PageHeader, Segmented, Skeleton, StatusDot } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api } from '../services/api'
import { ago, int, ms, pct, shortModel, sim, usd } from '../services/format'

export default function Overview() {
  const [days, setDays] = useState('30')
  const metrics = usePolling(() => api.overview(Number(days)), 10000, [days])
  const health = usePolling(api.health, 10000)
  const m = metrics.data
  const simulated = !!m && m.simulated_cost_usd > 0 && m.actual_cost_usd === 0
  const spend = m ? m.actual_cost_usd + m.simulated_cost_usd : null
  const saved = m ? m.saved_by_cache_usd + m.saved_by_routing_usd : null

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Overview" description="How NEXUS AI is answering, caching, routing and spending - computed from recorded requests only."
        actions={<Segmented label="Time window" value={days} onChange={setDays} options={[{ value: '7', label: '7d' }, { value: '30', label: '30d' }, { value: '90', label: '90d' }]} />} />

      {metrics.error && <Alert title="Can't reach the backend">{metrics.error}. Start it with <code className="font-mono">start_all.bat</code> (or <code className="font-mono">start_backend.ps1</code>).</Alert>}

      {m && !m.has_data && (
        <motion.div variants={{ initial: { opacity: 0 }, animate: { opacity: 1 } }}
          className="card relative overflow-hidden p-6">
          <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-accent/10 blur-3xl" />
          <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="flex items-center gap-2 text-sm font-semibold"><Sparkles size={15} className="text-accent" />Welcome to NEXUS AI</p>
              <p className="mt-1 max-w-xl text-sm text-muted">No questions have been processed yet, so every metric below is empty. Nothing on this page is pre-filled.
                Upload a document, then ask a question in the Playground.</p>
            </div>
            <div className="flex gap-2">
              <Link to="/documents" className="focus-ring inline-flex h-9 items-center gap-2 rounded-lg bg-accent px-3.5 text-sm font-medium text-accent-contrast hover:brightness-110">Upload documents <ArrowRight size={14} /></Link>
              <Link to="/playground" className="focus-ring inline-flex h-9 items-center rounded-lg border border-line px-3.5 text-sm font-medium hover:bg-surface-2">Open Playground</Link>
            </div>
          </div>
        </motion.div>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Kpi loading={metrics.loading} label="Queries processed" icon={Activity} value={m?.total_queries} format={int} hint={m?.errors ? `${m.errors} failed` : `last ${days} days`} />
        <Kpi loading={metrics.loading} label="Cache hit rate" icon={Database} tone="accent" value={m?.cache_hit_rate} format={n => pct(n)} hint={m?.cache_miss_rate != null ? `miss rate ${pct(m.cache_miss_rate)}` : 'no cacheable queries yet'} />
        <Kpi loading={metrics.loading} label="Avg response latency" icon={Clock} value={m?.avg_latency_ms} format={ms} hint={m?.p95_latency_ms != null ? `p95 ${ms(m.p95_latency_ms)}` : undefined} />
        <Kpi loading={metrics.loading} label={simulated ? 'Simulated API spend' : 'Estimated API spend'} icon={Coins} value={m?.has_data ? spend : null} format={usd}
          hint={simulated ? 'test mode - not real spend' : 'tokens × list price'} />
        <Kpi loading={metrics.loading} label="Estimated savings" icon={PiggyBank} tone="ok" value={m?.has_data ? saved : null} format={usd} hint="counterfactual: cache + routing" />
        <Kpi loading={metrics.loading} label="LLM calls avoided" icon={Zap} value={m?.has_data ? m.llm_calls_avoided : null} format={int} hint={m ? `${int(m.llm_calls)} calls made` : undefined} />
        <Kpi loading={metrics.loading} label="Small-model queries" icon={Layers} value={m?.has_data ? m.small_model_queries : null} format={int} hint="routed to the economical tier" />
        <Kpi loading={metrics.loading} label="Large-model queries" icon={Layers} value={m?.has_data ? m.large_model_queries : null} format={int} hint={m ? `${int(m.medium_model_queries)} medium-tier` : undefined} />
        <Kpi loading={metrics.loading} label="Avg similarity" icon={Sigma} value={m?.avg_similarity} format={sim} hint="best cache match per query" />
        <Kpi loading={metrics.loading} label="Routing savings" icon={GitBranch} tone="ok" value={m?.has_data ? m.saved_by_routing_usd : null} format={usd} hint="vs always using the large model" />
      </div>

      {m?.has_data ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Cost trend" subtitle={simulated ? 'Simulated (test mode) - priced like the real models the mocks stand in for' : 'Estimated spend per day, and the counterfactual savings'}
              action={simulated ? <MockBadge /> : <Badge>estimated</Badge>}>
              <TrendChart data={m.daily.map(d => ({ ...d, spend: d.cost_usd + d.simulated_cost_usd }))} xKey="date" format={usd}
                series={[{ key: 'spend', name: simulated ? 'Simulated spend' : 'Estimated spend', color: SERIES[0] },
                  { key: 'saved_usd', name: 'Savings (counterfactual)', color: SERIES[2], dashed: true }]} />
            </Card>
            <Card title="Latency trend" subtitle="Average and p95 end-to-end response time per day">
              <TrendChart area={false} data={m.daily} xKey="date" format={ms}
                series={[{ key: 'avg_latency_ms', name: 'Average', color: SERIES[0] }, { key: 'p95_latency_ms', name: 'p95', color: SERIES[1], dashed: true }]} />
            </Card>
            <Card title="Cache hits vs misses" subtitle="Questions answered from the cache vs by an LLM">
              <BarsChart data={m.daily} xKey="date" format={int}
                series={[{ key: 'hits', name: 'Cache hits', color: SERIES[0], stack: 'a' }, { key: 'misses', name: 'Misses', color: SERIES[1], stack: 'a' }]} />
            </Card>
            <Card title="Query volume" subtitle="Questions per day">
              <BarsChart data={m.daily} xKey="date" format={int} series={[{ key: 'queries', name: 'Queries', color: SERIES[0] }]} />
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Model usage distribution" subtitle="Queries answered by each model (cache hits excluded)">
              {m.model_distribution.length ? (
                <ShareBar items={m.model_distribution.map(d => ({ label: d.name, value: d.count, color: TIER_COLOR[d.tier ?? 'small'] ?? SERIES[0] }))} />
              ) : <EmptyState icon={<Layers size={18} />} title="No LLM calls yet" body="Every answer so far came from the cache." />}
              <div className="mt-4 flex flex-wrap gap-3 border-t border-line pt-3 text-[11px] text-muted">
                {(['small', 'medium', 'large'] as const).map(t => <span key={t} className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: TIER_COLOR[t] }} />{t} tier</span>)}
              </div>
            </Card>
            <Card title="Cache outcome breakdown" subtitle={`Last ${days} days`}>
              <ShareBar items={[
                { label: 'Exact hits', value: m.cache_breakdown.exact_hit ?? 0, color: SERIES[0] },
                { label: 'Semantic hits', value: m.cache_breakdown.semantic_hit ?? 0, color: SERIES[2] },
                { label: 'Misses', value: m.cache_breakdown.miss ?? 0, color: SERIES[1] },
              ]} />
              {(m.cache_breakdown.bypass ?? 0) > 0 && <p className="mt-3 text-[11px] text-faint">{m.cache_breakdown.bypass} quer{m.cache_breakdown.bypass === 1 ? 'y' : 'ies'} bypassed the cache (baseline mode or cache disabled).</p>}
            </Card>
            <HealthCard health={health} />
          </div>

          <div className="grid gap-4 lg:grid-cols-5">
            <Card title="Recent activity" className="lg:col-span-3" action={<Link to="/monitoring" className="text-xs text-accent hover:underline">Live monitoring</Link>}>
              <ul className="-my-2 divide-y divide-line">
                {m.recent_activity.map(a => (
                  <li key={a.id} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm">{a.query_text}</p>
                      <p className="mt-0.5 text-[11px] text-faint">{ago(a.created_at)} · {shortModel(a.model)}{a.is_mock ? ' · test mode' : ''}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3 text-xs text-muted tabular">
                      <CacheBadge status={a.cache_status} />
                      <span className="hidden w-16 text-right sm:inline">{ms(a.total_latency_ms)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Recent routing decisions" className="lg:col-span-2" action={<Link to="/router" className="text-xs text-accent hover:underline">Model router</Link>}>
              {m.recent_routing.length ? (
                <ul className="-my-2 divide-y divide-line">
                  {m.recent_routing.map(r => (
                    <li key={r.id} className="py-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm">{r.query_text}</p>
                        <Badge tone={r.routed_by === 'manual' ? 'warn' : 'accent'}>{r.routed_by}</Badge>
                      </div>
                      <p className="mt-0.5 truncate text-[11px] text-faint" title={r.reason ?? ''}>{r.category} · {r.complexity} → {r.model_name}</p>
                    </li>
                  ))}
                </ul>
              ) : <EmptyState icon={<GitBranch size={18} />} title="No routing decisions yet" body="They appear when a question needs an LLM call." />}
            </Card>
          </div>
        </>
      ) : !metrics.loading && !metrics.error && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card title="Charts" className="lg:col-span-2">
            <EmptyState icon={<BarChart3 size={18} />} title="Charts appear after the first question"
              body="Cost, latency, cache hit/miss, query volume and model usage are plotted from real request records." />
          </Card>
          <HealthCard health={health} />
        </div>
      )}
    </motion.div>
  )
}

function HealthCard({ health }: { health: ReturnType<typeof usePolling<Awaited<ReturnType<typeof api.health>>>> }) {
  return (
    <Card title="System health" action={health.data && <span className="text-[11px] text-faint tabular">up {Math.round(health.data.uptime_seconds / 60)} min</span>}>
      {health.loading ? (
        <div className="space-y-3"><Skeleton className="h-5" /><Skeleton className="h-5" /><Skeleton className="h-5" /></div>
      ) : health.error ? (
        <p className="flex items-center gap-2 text-sm text-err"><StatusDot status="error" />Backend unreachable</p>
      ) : health.data && (
        <ul className="space-y-3 text-sm">
          {Object.entries(health.data.components).map(([name, c]) => (
            <li key={name} className="flex items-start gap-3">
              <span className="mt-1.5"><StatusDot status={c.status} /></span>
              <div className="min-w-0">
                <p className="capitalize">{name.replace('_', ' ')}</p>
                <p className="truncate text-[11px] text-faint" title={c.detail}>{c.detail}</p>
              </div>
            </li>
          ))}
          <li className="border-t border-line pt-3">
            <p className="mb-2 text-[11px] text-faint">LLM providers (keys stay on the server)</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(health.data.llm_providers).map(([p, on]) => (
                <Badge key={p} tone={on ? 'ok' : 'neutral'}>{p.replace('_', '-')}{on ? '' : ' · not set'}</Badge>
              ))}
            </div>
          </li>
        </ul>
      )}
    </Card>
  )
}
