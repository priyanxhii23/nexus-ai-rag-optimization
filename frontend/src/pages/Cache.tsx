import { motion } from 'framer-motion'
import { Database, Eye, FlaskConical, Gauge, Search, ShieldCheck, Trash2, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { stagger } from '../animations/variants'
import { AnswerText } from '../components/Answer'
import { SERIES, TrendChart } from '../components/charts'
import { Alert, Badge, Button, Card, EmptyState, Input, KeyValue, Kpi, Label, MockBadge, Modal, PageHeader, SectionNote, Select, Skeleton, Table, Toggle } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api, type CacheEntry, type ThresholdExperiment } from '../services/api'
import { ago, dateTime, int, ms, pct, shortModel, sim, usd } from '../services/format'

const STATUS_TONE = { active: 'ok', expired: 'warn', invalidated: 'err' } as const

export default function CachePage() {
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const stats = usePolling(api.cacheStats, 10000)
  const entries = usePolling(() => api.cacheEntries({ search: q, status }), 10000, [q, status])
  const [inspect, setInspect] = useState<number | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'info' | 'err'; text: string } | null>(null)
  const s = stats.data

  useEffect(() => { const t = setTimeout(() => setQ(search.trim()), 300); return () => clearTimeout(t) }, [search])

  async function saveSetting(body: Parameters<typeof api.updateSettings>[0]) {
    try { await api.updateSettings(body); stats.refresh(); setMsg({ tone: 'info', text: 'Cache settings saved.' }) }
    catch (e) { setMsg({ tone: 'err', text: e instanceof Error ? e.message : 'Save failed' }) }
  }
  async function remove(id: number) {
    try { await api.deleteCacheEntry(id); setInspect(null); entries.refresh(); stats.refresh() }
    catch (e) { setMsg({ tone: 'err', text: e instanceof Error ? e.message : 'Delete failed' }) }
  }
  async function clearAll() {
    try { const r = await api.clearCache(); setConfirmClear(false); setMsg({ tone: 'info', text: `Cache cleared (${r.deleted} entries).` }); entries.refresh(); stats.refresh() }
    catch (e) { setMsg({ tone: 'err', text: e instanceof Error ? e.message : 'Clear failed' }) }
  }

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Semantic Cache" description="Previously answered questions are reused only when they are similar enough AND their source documents, tenant, mode and intent still match."
        actions={<Button variant="danger" icon={Trash2} onClick={() => setConfirmClear(true)} disabled={!s?.entries}>Clear cache</Button>} />
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi loading={stats.loading} label="Active entries" icon={Database} value={s?.active} format={int} hint={s ? `${s.expired} expired · ${s.invalidated} invalidated` : undefined} />
        <Kpi loading={stats.loading} label="Hit rate (30d)" icon={Gauge} tone="accent" value={s?.hit_rate_30d} format={n => pct(n)} />
        <Kpi loading={stats.loading} label="Exact hits (30d)" icon={Zap} value={s?.exact_hits_30d} format={int} />
        <Kpi loading={stats.loading} label="Semantic hits (30d)" icon={Zap} value={s?.semantic_hits_30d} format={int} />
        <Kpi loading={stats.loading} label="Avg hit latency" value={s?.avg_hit_latency_ms} format={ms} hint={s?.avg_miss_latency_ms != null ? `miss (LLM) ${ms(s.avg_miss_latency_ms)}` : undefined} />
        <Kpi loading={stats.loading} label="Saved by cache (30d)" tone="ok" value={s && s.saved_usd_30d ? s.saved_usd_30d : s ? 0 : null} format={usd} hint="counterfactual estimate" />
      </div>

      {s && (
        <Card title="Cache settings" subtitle="Stored in the database; defaults come from .env">
          <div className="grid gap-5 md:grid-cols-3">
            <div className="flex items-center justify-between gap-4 rounded-xl border border-line p-3">
              <div><p className="text-sm font-medium">Semantic cache</p><p className="text-xs text-muted">Turn off to send every question to an LLM.</p></div>
              <Toggle label="Semantic cache enabled" checked={s.settings.cache_enabled} onChange={v => saveSetting({ cache_enabled: v })} />
            </div>
            <ThresholdInput value={s.settings.similarity_threshold} onSave={v => saveSetting({ similarity_threshold: v })} />
            <label className="block">
              <Label hint="1 - 8760">Time to live (hours)</Label>
              <Select value={s.settings.cache_ttl_hours} onChange={e => saveSetting({ cache_ttl_hours: Number(e.target.value) })}>
                {[...new Set([1, 6, 24, 48, 72, 168, 720, s.settings.cache_ttl_hours])].sort((a, b) => a - b).map(h => <option key={h} value={h}>{h} h{h >= 24 ? ` (${(h / 24).toFixed(h % 24 ? 1 : 0)} d)` : ''}</option>)}
              </Select>
            </label>
          </div>
        </Card>
      )}

      <Card title="Cached answers" subtitle={entries.data ? `${entries.data.total} entr${entries.data.total === 1 ? 'y' : 'ies'}` : undefined}
        action={
          <div className="flex gap-2">
            <div className="relative w-56"><Search size={14} className="absolute left-2.5 top-2.5 text-faint" /><Input aria-label="Search cached questions" placeholder="Search questions or answers" value={search} onChange={e => setSearch(e.target.value)} className="pl-8" /></div>
            <Select aria-label="Filter by status" value={status} onChange={e => setStatus(e.target.value)} className="w-36">
              <option value="">All statuses</option><option value="active">Active</option><option value="expired">Expired</option><option value="invalidated">Invalidated</option>
            </Select>
          </div>}>
        {entries.loading ? <Skeleton className="h-24" /> : entries.error ? <Alert>{entries.error}</Alert> : (
          <Table head={['Question', 'Status', 'Model', 'Hits', 'Last sim.', 'Orig. cost', 'Created', 'Expires', '']}
            empty={!entries.data?.entries.length && <div className="pt-3"><EmptyState icon={<Database size={18} />} title={q || status ? 'No matching entries' : 'The cache is empty'} body="Every answered question is stored here and reused for equivalent questions later." /></div>}>
            {entries.data?.entries.map(e => (
              <tr key={e.id}>
                <td className="max-w-72 py-2.5 pr-4"><p className="truncate font-medium" title={e.query_text}>{e.query_text}</p>
                  <p className="truncate text-[11px] text-faint">#{e.id} · {e.intent_category} · {e.documents.map(d => d.filename ?? `doc ${d.document_id}`).join(', ') || 'no source documents'}</p></td>
                <td className="py-2.5 pr-4"><Badge tone={STATUS_TONE[e.status as keyof typeof STATUS_TONE] ?? 'neutral'}>{e.status}</Badge> {e.is_mock && <MockBadge />}</td>
                <td className="py-2.5 pr-4 text-muted">{shortModel(e.model)}</td>
                <td className="py-2.5 pr-4 tabular">{e.hit_count}</td>
                <td className="py-2.5 pr-4 tabular">{sim(e.last_similarity)}</td>
                <td className="py-2.5 pr-4 tabular text-muted">{usd(e.original_cost_usd)}</td>
                <td className="whitespace-nowrap py-2.5 pr-4 text-muted">{ago(e.created_at)}</td>
                <td className="whitespace-nowrap py-2.5 pr-4 text-muted">{new Date(e.expires_at) < new Date() ? 'expired' : dateTime(e.expires_at)}</td>
                <td className="py-2.5"><div className="flex justify-end gap-1">
                  <Button size="sm" variant="ghost" icon={Eye} onClick={() => setInspect(e.id)}>Inspect</Button>
                  <Button size="sm" variant="ghost" icon={Trash2} aria-label="Delete entry" className="hover:text-err" onClick={() => remove(e.id)} />
                </div></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <ThresholdLab current={s?.settings.similarity_threshold} onApply={v => saveSetting({ similarity_threshold: v })} />

      <InspectModal id={inspect} onClose={() => setInspect(null)} onDelete={remove} />
      <Modal open={confirmClear} onClose={() => setConfirmClear(false)} title="Clear the whole cache?">
        <p className="text-sm text-muted">All {s?.entries} entries and their vectors will be deleted. The next questions will call an LLM again.</p>
        <div className="mt-4 flex justify-end gap-2"><Button onClick={() => setConfirmClear(false)}>Cancel</Button><Button variant="danger" icon={Trash2} onClick={clearAll}>Clear cache</Button></div>
      </Modal>
    </motion.div>
  )
}

function ThresholdInput({ value, onSave }: { value: number; onSave: (v: number) => void }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  return (
    <label className="block">
      <Label hint={v.toFixed(2)}>Similarity threshold</Label>
      <input type="range" min={0.5} max={1} step={0.01} value={v} onChange={e => setV(Number(e.target.value))}
        onPointerUp={() => v !== value && onSave(v)} onKeyUp={() => v !== value && onSave(v)}
        className="mt-2 w-full accent-[var(--accent)]" aria-label="Similarity threshold" />
      <p className="mt-1 text-[11px] text-faint">Higher = safer reuse, fewer hits. Use the optimizer below to choose.</p>
    </label>
  )
}

function InspectModal({ id, onClose, onDelete }: { id: number | null; onClose: () => void; onDelete: (id: number) => void }) {
  const entry = usePolling<CacheEntry | null>(() => (id ? api.cacheEntry(id) : Promise.resolve(null)), 0, [id])
  const e = entry.data
  return (
    <Modal open={!!id} onClose={onClose} title={e ? `Cache entry #${e.id}` : 'Cache entry'} wide>
      {entry.loading ? <Skeleton className="h-32" /> : entry.error ? <Alert>{entry.error}</Alert> : e && (
        <div className="space-y-5 text-sm">
          <div>
            <p className="text-xs text-muted">Original question</p>
            <p className="mt-0.5 font-medium">{e.query_text}</p>
          </div>
          <KeyValue items={[
            ['Status', <span key="s"><Badge tone={STATUS_TONE[e.status as keyof typeof STATUS_TONE] ?? 'neutral'}>{e.status}</Badge>{e.invalidated_reason ? ` - ${e.invalidated_reason}` : ''}</span>],
            ['Intent category', e.intent_category ?? '—'], ['Document scope', e.scope_key === 'all' ? 'whole library' : 'selected documents'],
            ['Model', `${shortModel(e.model)}${e.is_mock ? ' (test mode)' : ''}`],
            ['Original cost / latency', `${usd(e.original_cost_usd)} · ${ms(e.original_latency_ms)} · ${int(e.input_tokens)} in / ${int(e.output_tokens)} out tokens`],
            ['Created / expires', `${dateTime(e.created_at)} → ${dateTime(e.expires_at)}`],
            ['Hits served', `${e.hit_count}${e.last_hit_at ? ` (last ${ago(e.last_hit_at)}, similarity ${sim(e.last_similarity)})` : ''}`],
          ]} />
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold"><ShieldCheck size={13} className="text-ok" />Context validation - source documents</p>
            {e.documents.length ? (
              <ul className="space-y-1.5 text-xs">
                {e.documents.map(d => {
                  const ok = d.exists && d.current_version === d.version
                  return (
                    <li key={d.document_id} className="flex items-center justify-between rounded-lg border border-line px-3 py-2">
                      <span>{d.filename ?? `document ${d.document_id}`} · cached against v{d.version}</span>
                      <Badge tone={ok ? 'ok' : 'err'}>{!d.exists ? 'deleted' : ok ? 'unchanged' : `now v${d.current_version}`}</Badge>
                    </li>
                  )
                })}
              </ul>
            ) : <p className="text-xs text-muted">No source documents (pure arithmetic answer).</p>}
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold">Cached answer</p>
            <div className="rounded-xl border border-line bg-surface-2/50 p-3"><AnswerText text={e.response_text ?? ''} /></div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold">Why later questions matched (hit history)</p>
            {e.hit_history?.length ? (
              <ul className="space-y-1.5 text-xs">
                {e.hit_history.map(h => (
                  <li key={h.request_id} className="rounded-lg border border-line p-2.5">
                    <p className="font-medium">“{h.query_text}”</p>
                    <p className="mt-0.5 text-muted">{h.status.replace('_', ' ')} · similarity {sim(h.similarity)} · {ago(h.created_at)}</p>
                    {h.reason && <p className="mt-0.5 text-faint">{h.reason}</p>}
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-muted">This entry has not been reused yet.</p>}
          </div>
          <div className="flex justify-end"><Button variant="danger" icon={Trash2} onClick={() => onDelete(e.id)}>Delete entry</Button></div>
        </div>
      )}
    </Modal>
  )
}

function ThresholdLab({ current, onApply }: { current?: number; onApply: (v: number) => void }) {
  const [data, setData] = useState<ThresholdExperiment | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function run() {
    setRunning(true); setError(null)
    try { setData(await api.thresholdExperiment()) } catch (e) { setError(e instanceof Error ? e.message : 'Experiment failed') } finally { setRunning(false) }
  }
  return (
    <Card title="Adaptive similarity threshold optimizer"
      subtitle="Measures, with the real embedding model, how often each threshold would reuse an answer correctly vs wrongly on labelled question pairs."
      action={<Button variant="primary" icon={FlaskConical} loading={running} onClick={run}>{data ? 'Run again' : 'Run experiment'}</Button>}>
      {error && <Alert>{error}</Alert>}
      {!data && !error && <EmptyState icon={<FlaskConical size={18} />} title="No experiment run yet" body="The experiment embeds 20 labelled question pairs (10 same-intent, 10 different-intent) and evaluates thresholds from 0.70 to 0.98. It takes a few seconds and calls no LLM." />}
      {data && (
        <div className="space-y-5">
          <div className="flex flex-col gap-3 rounded-xl border border-accent/25 bg-accent-soft/50 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold">Recommended threshold: <span className="text-accent tabular">{data.recommended_threshold.toFixed(2)}</span>
                {current != null && <span className="ml-2 text-xs font-normal text-muted">(current {current.toFixed(2)})</span>}</p>
              <p className="mt-1 max-w-3xl text-xs text-muted">{data.recommendation_reason}</p>
            </div>
            <Button variant="primary" disabled={current === data.recommended_threshold} onClick={() => onApply(data.recommended_threshold)}>Apply {data.recommended_threshold.toFixed(2)}</Button>
          </div>
          <TrendChart area={false} xKey="threshold" format={n => pct(n, 0)} height={240}
            data={data.results.map(r => ({ ...r, threshold: r.threshold.toFixed(2) }))}
            series={[
              { key: 'reuse_rate_with_guard', name: 'Correct reuse (with intent guard)', color: SERIES[0] },
              { key: 'false_match_rate_with_guard', name: 'Wrong matches (with intent guard)', color: SERIES[1] },
              { key: 'false_match_rate', name: 'Wrong matches (similarity only)', color: SERIES[1], dashed: true },
            ]} />
          <details>
            <summary className="cursor-pointer text-xs font-medium text-muted hover:text-fg">Show the {data.pairs.length} measured pairs</summary>
            <div className="mt-3"><Table head={['Similarity', 'Label', 'Question A', 'Question B', 'Intent guard']}>
              {[...data.pairs].sort((a, b) => b.similarity - a.similarity).map((p, i) => (
                <tr key={i}>
                  <td className="py-2 pr-4 tabular">{p.similarity.toFixed(3)}</td>
                  <td className="py-2 pr-4"><Badge tone={p.same_intent ? 'ok' : 'warn'}>{p.same_intent ? 'same' : 'different'}</Badge></td>
                  <td className="max-w-52 py-2 pr-4 text-xs">{p.a}</td><td className="max-w-52 py-2 pr-4 text-xs">{p.b}</td>
                  <td className="py-2 text-xs text-muted">{p.guard_blocks.join('; ') || '—'}</td>
                </tr>
              ))}
            </Table></div>
          </details>
          <SectionNote>{data.latency_note} Embedding model: {data.embedding_model}. The recommendation never lowers the threshold just to increase hits - correctness comes first.</SectionNote>
        </div>
      )}
    </Card>
  )
}
