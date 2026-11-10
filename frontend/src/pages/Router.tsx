import { motion } from 'framer-motion'
import { Brain, GitBranch, Wand2 } from 'lucide-react'
import { useState } from 'react'
import { stagger } from '../animations/variants'
import { BarsChart, SERIES, TIER_COLOR } from '../components/charts'
import { Alert, Badge, Button, Card, EmptyState, Input, KeyValue, PageHeader, Progress, Segmented, SectionNote, Skeleton, Table } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api, type Analysis, type Routing } from '../services/api'
import { ago, ms, shortModel, usd } from '../services/format'

const EXAMPLES = [
  'What is the refund deadline?',
  'Compare the Basic and Pro plans in terms of storage and support',
  'Why do we publish a root-cause analysis after incidents, and how fast is it shared?',
  'First explain the refund window, then list what is never refundable, then describe how to appeal',
]
const LEVEL_TONE = { simple: 'ok', medium: 'cyan', complex: 'warn' } as const

export default function RouterPage() {
  const models = usePolling(api.models, 0)
  const settings = usePolling(api.settings, 0)
  const decisions = usePolling(api.routerDecisions, 10000)
  const costs = usePolling(() => api.costs(30), 15000)
  const [q, setQ] = useState(EXAMPLES[1])
  const [res, setRes] = useState<{ analysis: Analysis; routing: Routing | { error: string } } | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function analyze(text = q) {
    if (!text.trim()) return
    setBusy(true); setErr(null)
    try { setRes(await api.analyze(text)) } catch (e) { setErr(e instanceof Error ? e.message : 'Failed') } finally { setBusy(false) }
  }
  async function setStrategy(v: string) {
    try { await api.updateSettings({ routing_strategy: v as 'balanced' }); settings.refresh(); if (res) analyze() } catch (e) { setErr(e instanceof Error ? e.message : 'Failed') }
  }

  const strategy = settings.data?.runtime.routing_strategy ?? 'balanced'
  const map = models.data?.strategies[strategy]
  const a = res?.analysis
  const routing = res && !('error' in res.routing) ? res.routing : null

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Model Router" description="Every question is classified (category + complexity) and routed to the cheapest model tier that suits it. Rule-based and fully explainable; the interface is ready for an ML classifier."
        actions={<Segmented label="Routing strategy" value={strategy} onChange={setStrategy}
          options={[{ value: 'cost_saver', label: 'Cost saver' }, { value: 'balanced', label: 'Balanced' }, { value: 'quality_first', label: 'Quality first' }]} />} />
      {err && <Alert>{err}</Alert>}

      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="Query intelligence" subtitle="Analyse any question - no LLM is called" className="lg:col-span-3">
          <form onSubmit={e => { e.preventDefault(); analyze() }} className="flex gap-2">
            <Input aria-label="Question to analyse" value={q} onChange={e => setQ(e.target.value)} placeholder="Type a question…" />
            <Button variant="primary" icon={Wand2} loading={busy} type="submit">Analyse</Button>
          </form>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {EXAMPLES.map(x => <button key={x} onClick={() => { setQ(x); analyze(x) }} className="rounded-md border border-line px-2 py-0.5 text-[11px] text-muted hover:bg-surface-2 hover:text-fg">{x.length > 46 ? x.slice(0, 46) + '…' : x}</button>)}
          </div>
          {a ? (
            <motion.div key={q} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-5 grid gap-5 md:grid-cols-2">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="accent"><Brain size={11} />{a.category.replace('_', '-')}</Badge>
                  <Badge tone={LEVEL_TONE[a.complexity_level as keyof typeof LEVEL_TONE]}>{a.complexity_level}</Badge>
                  {a.reasoning_required && <Badge>reasoning</Badge>}{a.retrieval_required && <Badge>retrieval</Badge>}
                </div>
                <div><div className="mb-1 flex justify-between text-xs text-muted"><span>Complexity score</span><span className="tabular text-fg">{a.complexity_score} / 100</span></div><Progress value={a.complexity_score / 100} /></div>
                <ul className="space-y-1 text-xs text-muted">{a.signals.map((s, i) => <li key={i}>• {s}</li>)}</ul>
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold">Routing decision</p>
                {routing ? (
                  <>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="rounded-md bg-surface-2 px-2 py-1 text-xs">{a.complexity_level}</span><GitBranch size={14} className="text-faint" />
                      <span className="rounded-md px-2 py-1 text-xs font-medium text-white" style={{ background: TIER_COLOR[routing.tier ?? 'small'] }}>{routing.tier} tier</span>
                      <span className="truncate font-medium">{routing.model}</span>
                    </div>
                    <p className="text-xs text-muted">{routing.reason}</p>
                    {!!routing.fallback_chain?.length && <p className="text-[11px] text-faint">Fallback order if it fails: {routing.fallback_chain.map(shortModel).join(' → ')}</p>}
                  </>
                ) : <p className="text-xs text-err">{res && 'error' in res.routing ? res.routing.error : ''}</p>}
                <p className="text-[11px] text-faint">Processing path: {a.processing_path}</p>
              </div>
            </motion.div>
          ) : <div className="mt-5"><EmptyState icon={<Brain size={18} />} title="Analyse a question" body="Pick an example or type your own to see its category, complexity score, reasoning signals and the model it would be routed to." /></div>}
        </Card>

        <Card title="Strategy map" subtitle={`Complexity → tier (${strategy.replace('_', ' ')})`} className="lg:col-span-2">
          {map ? (
            <div className="space-y-2.5">
              {(['simple', 'medium', 'complex'] as const).map(l => (
                <div key={l} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-sm">
                  <Badge tone={LEVEL_TONE[l]}>{l}</Badge><GitBranch size={13} className="text-faint" />
                  <span className="flex items-center gap-2 font-medium"><span className="h-2 w-2 rounded-sm" style={{ background: TIER_COLOR[map[l]] }} />{map[l]} tier</span>
                </div>
              ))}
              <SectionNote>If no model is available in a tier, the nearest tier is used (preferring more capable). Failed calls automatically fall back to the next model.</SectionNote>
            </div>
          ) : <Skeleton className="h-28" />}
        </Card>
      </div>

      <Card title="Configured models" subtitle={models.data?.mock_mode ? 'Test mode: only the mock models can run. Add an API key in .env to enable real providers.' : 'Models the router can choose from'}>
        {models.loading ? <Skeleton className="h-24" /> : (
          <Table head={['Model', 'Provider', 'Tier', 'Price (input / output per 1M tokens)', 'Status']}>
            {models.data?.models.map(m => (
              <tr key={m.id}>
                <td className="py-2.5 pr-4"><p className="font-medium">{m.display_name}</p><p className="text-[11px] text-faint">{m.model_name}{m.effort ? ` · effort ${m.effort}` : ''}</p></td>
                <td className="py-2.5 pr-4 text-muted">{m.provider}</td>
                <td className="py-2.5 pr-4"><span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: TIER_COLOR[m.tier] }} />{m.tier}</span></td>
                <td className="py-2.5 pr-4 text-xs"><span className="tabular">{m.is_mock ? `simulated as ${shortModel(m.simulates)}` : m.input_price_per_mtok == null ? <Badge tone="warn">unpriced</Badge> : `$${m.input_price_per_mtok} / $${m.output_price_per_mtok}`}</span>
                  <p className="max-w-72 truncate text-[11px] text-faint" title={m.price_source ?? ''}>{m.price_source}</p></td>
                <td className="py-2.5">{m.available ? <Badge tone="ok">available</Badge> : <Badge title={m.unavailable_reason ?? ''}>{m.unavailable_reason?.split(' (')[0]}</Badge>}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Spend by model (30d)" subtitle={costs.data?.is_simulated ? 'Simulated (test mode)' : 'Estimated from tokens × list price'}>
          {costs.data?.models.length ? (
            <BarsChart horizontal data={costs.data.models.map(m => ({ name: m.name, cost: m.cost_usd }))} xKey="name" format={usd} height={Math.max(140, costs.data.models.length * 44)}
              series={[{ key: 'cost', name: 'Cost', color: SERIES[0] }]} />
          ) : <EmptyState icon={<GitBranch size={18} />} title="No model calls yet" body="Spend per model appears after questions are answered." />}
        </Card>
        <Card title="Latency by model (30d)" subtitle="Average LLM call time">
          {costs.data?.models.length ? (
            <BarsChart horizontal data={costs.data.models.map(m => ({ name: m.name, avg: m.avg_latency_ms ?? 0 }))} xKey="name" format={ms} height={Math.max(140, costs.data.models.length * 44)}
              series={[{ key: 'avg', name: 'Average latency', color: SERIES[0] }]} />
          ) : <EmptyState icon={<GitBranch size={18} />} title="No model calls yet" body="Latency per model appears after questions are answered." />}
        </Card>
      </div>

      <Card title="Routing decisions" subtitle="Every routed question, with the reason">
        {decisions.loading ? <Skeleton className="h-24" /> : (
          <Table head={['Question', 'Category', 'Complexity', 'Model', 'By', 'Reason', 'Latency', 'Cost', 'When']}
            empty={!decisions.data?.length && <div className="pt-3"><EmptyState icon={<GitBranch size={18} />} title="No routing decisions yet" body="Ask a question in the Playground - cache hits skip routing, so only LLM calls appear here." /></div>}>
            {decisions.data?.map(d => (
              <tr key={d.id}>
                <td className="max-w-56 py-2.5 pr-4"><p className="truncate" title={d.query_text}>{d.query_text}</p></td>
                <td className="py-2.5 pr-4 text-muted">{d.category}</td>
                <td className="py-2.5 pr-4">{d.complexity && <Badge tone={LEVEL_TONE[d.complexity as keyof typeof LEVEL_TONE]}>{d.complexity} {d.complexity_score}</Badge>}</td>
                <td className="py-2.5 pr-4">{shortModel(d.model)}{d.fallback_used && <Badge tone="warn" className="ml-1">fallback</Badge>}</td>
                <td className="py-2.5 pr-4"><Badge tone={d.routed_by === 'manual' ? 'warn' : 'accent'}>{d.routed_by}</Badge></td>
                <td className="max-w-72 py-2.5 pr-4"><p className="truncate text-xs text-muted" title={d.reason ?? ''}>{d.reason}</p></td>
                <td className="py-2.5 pr-4 tabular text-muted">{ms(d.latency_ms)}</td>
                <td className="py-2.5 pr-4 tabular text-muted">{usd(d.cost_usd)}</td>
                <td className="whitespace-nowrap py-2.5 text-muted">{ago(d.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
        {decisions.data?.length ? <div className="mt-3"><KeyValue items={[['Routing savings (30d)', `${usd(costs.data?.saved_by_routing_usd)} - counterfactual: what the same tokens would have cost on the most capable available model`]]} /></div> : null}
      </Card>
    </motion.div>
  )
}
