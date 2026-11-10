import { motion } from 'framer-motion'
import { Download, FlaskConical, Gauge, Play, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { stagger } from '../animations/variants'
import { BarsChart, SERIES } from '../components/charts'
import { Alert, Badge, Button, Card, EmptyState, Input, Label, MockBadge, Modal, PageHeader, Progress, SectionNote, Select, Skeleton, Table } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { ApiError, api, type BenchmarkRun, type BenchmarkSummaryConfig } from '../services/api'
import { ago, int, ms, pct, shortModel, usd } from '../services/format'

const CONFIGS = [
  { id: 'baseline', label: 'A. Baseline RAG', desc: 'No cache, no routing (always the most capable model)' },
  { id: 'cache', label: 'B. + Semantic cache', desc: 'Cache on, routing off' },
  { id: 'optimized', label: 'C. + Cache + routing', desc: 'The full NEXUS AI pipeline' },
]
const COLOR: Record<string, string> = { baseline: SERIES[0], cache: SERIES[1], optimized: SERIES[2] }

export default function Benchmarks() {
  const datasets = usePolling(api.datasets, 0)
  const runs = usePolling(api.benchmarkRuns, 4000)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [name, setName] = useState('Benchmark run')
  const [dataset, setDataset] = useState('nexus_demo_v1')
  const [configs, setConfigs] = useState<string[]>(CONFIGS.map(c => c.id))
  const [threshold, setThreshold] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [confirm, setConfirm] = useState<number | null>(null)
  const latestId = runs.data?.[0]?.id ?? null
  const shownId = selectedId ?? latestId
  const run = usePolling<BenchmarkRun | null>(() => (shownId ? api.benchmarkRun(shownId) : Promise.resolve(null)), 3000, [shownId])
  const running = runs.data?.some(r => r.status === 'running' || r.status === 'queued')

  useEffect(() => { if (run.data?.status === 'completed') runs.refresh() }, [run.data?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  async function start(confirmCost = false) {
    setStarting(true); setErr(null)
    try {
      const r = await api.startBenchmark({ name, dataset, configs, threshold: threshold ? Number(threshold) : null, confirm_cost: confirmCost })
      setConfirm(null); setSelectedId(r.id); runs.refresh()
    } catch (e) {
      if (e instanceof ApiError && e.code === 'confirm_cost') setConfirm(Number(e.extra.max_llm_calls ?? 0))
      else setErr(e instanceof Error ? e.message : 'Failed to start')
    } finally { setStarting(false) }
  }

  const ds = datasets.data?.find(d => d.id === dataset)
  const r = run.data
  const summary = r?.summary?.configs
  const cfgs = summary ? Object.keys(summary) : []

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Benchmarking Lab" description="Runs identical questions over identical documents through three pipeline configurations and measures latency, cost, cache behaviour and answer quality. Nothing is estimated in advance - every number comes from the run." />
      {err && <Alert>{err}</Alert>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="New run" className="lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block"><Label>Run name</Label><Input value={name} onChange={e => setName(e.target.value)} maxLength={200} /></label>
            <label className="block"><Label>Dataset</Label>
              <Select value={dataset} onChange={e => setDataset(e.target.value)}>{datasets.data?.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></label>
          </div>
          {ds && <p className="mt-2 text-xs text-muted">{ds.description}</p>}
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            {CONFIGS.map(c => {
              const on = configs.includes(c.id)
              return (
                <button key={c.id} onClick={() => setConfigs(x => on ? x.filter(y => y !== c.id) : [...x, c.id])} aria-pressed={on}
                  className={`focus-ring rounded-xl border p-3 text-left transition-colors ${on ? 'border-accent/40 bg-accent-soft/60' : 'border-line hover:bg-surface-2'}`}>
                  <p className="flex items-center gap-2 text-sm font-medium"><span className="h-2 w-2 rounded-sm" style={{ background: COLOR[c.id] }} />{c.label}</p>
                  <p className="mt-0.5 text-[11px] text-muted">{c.desc}</p>
                </button>
              )
            })}
          </div>
          <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
            <label className="block w-48"><Label hint="optional">Similarity threshold</Label><Input type="number" min={0.5} max={1} step={0.01} placeholder="use current setting" value={threshold} onChange={e => setThreshold(e.target.value)} /></label>
            <Button variant="primary" icon={Play} loading={starting} disabled={!configs.length || !!running} onClick={() => start()}>{running ? 'A run is in progress' : 'Start benchmark'}</Button>
          </div>
          <div className="mt-3"><SectionNote>Each run uses an isolated temporary workspace (its own documents and an empty cache per configuration), so your library and cache are never touched. In test mode the run is labelled as simulated.</SectionNote></div>
        </Card>
        <Card title="Run history">
          {runs.loading ? <Skeleton className="h-24" /> : runs.data?.length ? (
            <ul className="-my-1.5 divide-y divide-line">
              {runs.data.map(x => (
                <li key={x.id} className="flex items-center gap-2 py-2">
                  <button onClick={() => setSelectedId(x.id)} className={`min-w-0 flex-1 text-left ${x.id === shownId ? 'text-accent' : 'hover:text-accent'}`}>
                    <p className="truncate text-sm font-medium">#{x.id} {x.name}</p>
                    <p className="text-[11px] text-faint">{x.status}{x.status === 'running' ? ` ${pct(x.progress, 0)}` : ''} · {ago(x.created_at)}{x.is_simulated ? ' · simulated' : ''}</p>
                  </button>
                  {x.status !== 'running' && x.status !== 'queued' && <Button size="sm" variant="ghost" icon={Trash2} aria-label="Delete run" className="hover:text-err"
                    onClick={async () => { await api.deleteBenchmark(x.id); if (selectedId === x.id) setSelectedId(null); runs.refresh() }} />}
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={<Gauge size={18} />} title="No runs yet" body="Start a run to compare the three configurations." />}
        </Card>
      </div>

      {r && (
        <Card title={`Run #${r.id}: ${r.name}`} subtitle={`${r.dataset} · ${r.configs.length} configuration(s) · started ${ago(r.created_at)}`}
          action={<>{r.is_simulated && <MockBadge />}{r.status === 'completed' && <>
            <a href={`/api/benchmarks/runs/${r.id}/report?format=md`} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-2.5 text-xs font-medium hover:bg-surface-2"><Download size={13} />Report</a>
            <a href={`/api/benchmarks/runs/${r.id}/report?format=csv`} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-2.5 text-xs font-medium hover:bg-surface-2"><Download size={13} />CSV</a></>}</>}>
          {(r.status === 'running' || r.status === 'queued') && (
            <div className="space-y-2"><div className="flex justify-between text-xs text-muted"><span>Running… each question goes through the real pipeline</span><span className="tabular">{pct(r.progress, 0)}</span></div><Progress value={r.progress} /></div>
          )}
          {r.status === 'failed' && <Alert>Run failed: {r.error}</Alert>}
          {summary && (
            <div className="space-y-5">
              {r.summary?.note && <Alert tone={r.is_simulated ? 'warn' : 'info'}>{r.summary.note}</Alert>}
              <div className="grid gap-4 lg:grid-cols-3">
                <div><p className="mb-2 text-xs font-medium text-muted">Latency (ms)</p>
                  <BarsChart data={[{ m: 'Average', ...Object.fromEntries(cfgs.map(c => [c, summary[c].avg_latency_ms])) }, { m: 'Median', ...Object.fromEntries(cfgs.map(c => [c, summary[c].median_latency_ms])) }, { m: 'p95', ...Object.fromEntries(cfgs.map(c => [c, summary[c].p95_latency_ms])) }]}
                    xKey="m" format={ms} height={200} series={cfgs.map(c => ({ key: c, name: summary[c].label, color: COLOR[c] }))} /></div>
                <div><p className="mb-2 text-xs font-medium text-muted">Total cost {r.is_simulated ? '(simulated)' : '(estimated)'}</p>
                  <BarsChart data={cfgs.map(c => ({ name: summary[c].label, cost: summary[c].cost_usd }))} xKey="name" format={usd} height={200} series={[{ key: 'cost', name: 'Cost', color: SERIES[0] }]} /></div>
                <div><p className="mb-2 text-xs font-medium text-muted">LLM calls made vs avoided</p>
                  <BarsChart data={cfgs.map(c => ({ name: summary[c].label, made: summary[c].llm_calls, avoided: summary[c].llm_calls_avoided }))} xKey="name" format={int} height={200}
                    series={[{ key: 'made', name: 'LLM calls', color: SERIES[0], stack: 's' }, { key: 'avoided', name: 'Avoided (cache)', color: SERIES[2], stack: 's' }]} /></div>
              </div>
              <Table head={['Metric', ...cfgs.map(c => summary[c].label)]}>
                {([
                  ['Average latency', (s) => ms(s.avg_latency_ms)], ['Median latency', (s) => ms(s.median_latency_ms)], ['P95 latency', (s) => ms(s.p95_latency_ms)],
                  ['Cache hit rate', (s) => pct(s.cache_hit_rate)], ['Cache miss rate', (s) => pct(s.cache_miss_rate)],
                  ['LLM calls', (s) => int(s.llm_calls)], ['LLM calls avoided', (s) => int(s.llm_calls_avoided)],
                  ['Input tokens', (s) => int(s.input_tokens)], ['Output tokens', (s) => int(s.output_tokens)], ['Total cost', (s) => usd(s.cost_usd)],
                  ['Cost reduction vs A', (s) => s.cost_reduction_vs_baseline == null ? '—' : pct(s.cost_reduction_vs_baseline)],
                  ['Latency reduction vs A', (s) => s.latency_reduction_vs_baseline == null ? '—' : pct(s.latency_reduction_vs_baseline)],
                  ['Retrieval relevance', (s) => pct(s.retrieval_relevance)], ['Answer correctness', (s) => pct(s.answer_correctness)],
                  ['Answer faithfulness', (s) => pct(s.answer_faithfulness)], ['Models used', (s) => s.models_used.map(shortModel).join(', ') || '—'],
                ] as [string, (s: BenchmarkSummaryConfig) => string][]).map(([label, f]) => (
                  <tr key={label}><td className="py-2 pr-4 text-muted">{label}</td>{cfgs.map(c => <td key={c} className="py-2 pr-4 tabular">{f(summary[c])}</td>)}</tr>
                ))}
              </Table>
              <SectionNote>Correctness = share of expected keywords found in the answer; faithfulness = share of answer sentences grounded in the retrieved passages (embedding similarity); retrieval relevance = gold document among the sources. These are automatic heuristics, not human ratings.</SectionNote>
              {r.results && (
                <details>
                  <summary className="cursor-pointer text-xs font-medium text-muted hover:text-fg">Per-question results ({r.results.length})</summary>
                  <div className="mt-3"><Table head={['Config', 'Q', 'Question', 'Cache', 'Model', 'Latency', 'Cost', 'Correct', 'Faithful']}>
                    {r.results.map((x, i) => (
                      <tr key={i}><td className="py-1.5 pr-3"><span className="h-2 w-2 rounded-sm inline-block mr-1.5" style={{ background: COLOR[x.config] }} />{x.config}</td>
                        <td className="py-1.5 pr-3 text-faint">{x.question_id}</td><td className="max-w-64 truncate py-1.5 pr-3 text-xs" title={x.question}>{x.question}</td>
                        <td className="py-1.5 pr-3"><Badge tone={x.cache_status.includes('hit') ? 'ok' : 'neutral'}>{x.cache_status}</Badge></td>
                        <td className="py-1.5 pr-3 text-xs">{x.llm_called ? shortModel(x.model) : '—'}</td><td className="py-1.5 pr-3 tabular">{ms(x.latency_ms)}</td>
                        <td className="py-1.5 pr-3 tabular">{usd(x.cost_usd)}</td><td className="py-1.5 pr-3 tabular">{pct(x.correctness, 0)}</td><td className="py-1.5 tabular">{pct(x.faithfulness, 0)}</td></tr>
                    ))}
                  </Table></div>
                </details>
              )}
            </div>
          )}
        </Card>
      )}
      {!r && !runs.loading && <Card><EmptyState icon={<FlaskConical size={18} />} title="No results to show" body="Benchmark results are only shown after a run has actually been executed." /></Card>}

      <Modal open={confirm !== null} onClose={() => setConfirm(null)} title="This run will use paid API calls">
        <p className="text-sm text-muted">Real LLM providers are configured. This benchmark can make up to <b className="text-fg">{confirm}</b> LLM calls (cache hits reduce this). Costs are charged to your provider account.</p>
        <div className="mt-4 flex justify-end gap-2"><Button onClick={() => setConfirm(null)}>Cancel</Button><Button variant="primary" loading={starting} onClick={() => start(true)}>I understand, start</Button></div>
      </Modal>
    </motion.div>
  )
}
