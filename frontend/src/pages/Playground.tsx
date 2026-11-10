import { AnimatePresence, motion } from 'framer-motion'
import { Bot, Check, ChevronDown, CircleDot, Cpu, Database, FileText, GitBranch, Loader2, MessageSquarePlus, Search, Send, Sparkles, Square, User } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnswerText } from '../components/Answer'
import { Alert, Badge, CacheBadge, KeyValue, MockBadge, Select } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api, streamQuery, type Analysis, type CacheCandidate, type Citation, type QueryResult, type Routing } from '../services/api'
import { COST_LABEL, int, ms, shortModel, sim, usd } from '../services/format'

type Stage = 'embedding' | 'cache' | 'retrieval' | 'routing' | 'llm'
interface Turn {
  id: string
  query: string
  answer: string
  pending: boolean
  stages: Partial<Record<Stage, 'active' | 'done' | 'skipped'>>
  cache?: { status: string; similarity: number | null; threshold?: number; reason: string | null; candidates?: CacheCandidate[] }
  analysis?: Analysis | null
  routing?: Routing | null
  citations: Citation[]
  result?: QueryResult
  error?: string
  fallback?: string
}

const CONV_KEY = 'nexus-conversation'
const newConvId = () => Math.random().toString(36).slice(2, 12) + Date.now().toString(36)
const readConv = () => { try { return localStorage.getItem(CONV_KEY) || newConvId() } catch { return newConvId() } }

function fromResult(r: QueryResult): Turn {
  return {
    id: String(r.request_id), query: r.query, answer: r.answer ?? '', pending: false, citations: r.citations, result: r,
    stages: {}, cache: r.cache, analysis: r.analysis, routing: r.routing, error: r.error ?? undefined,
  }
}

const STAGES: { key: Stage; label: string; icon: React.ElementType }[] = [
  { key: 'embedding', label: 'Embed', icon: Sparkles }, { key: 'cache', label: 'Cache', icon: Database },
  { key: 'retrieval', label: 'Retrieve', icon: Search }, { key: 'routing', label: 'Route', icon: GitBranch }, { key: 'llm', label: 'Generate', icon: Cpu },
]

function PipelineStrip({ stages }: { stages: Turn['stages'] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="Pipeline progress">
      {STAGES.map((s, i) => {
        const st = stages[s.key]
        return (
          <div key={s.key} className="flex items-center gap-1.5">
            <motion.span layout className={`flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset transition-colors ${
              st === 'done' ? 'bg-accent-soft text-accent ring-accent/20' : st === 'active' ? 'bg-cyan/10 text-cyan ring-cyan/25' : st === 'skipped' ? 'text-faint ring-line line-through' : 'text-faint ring-line'}`}>
              {st === 'active' ? <Loader2 size={11} className="animate-spin" /> : st === 'done' ? <Check size={11} /> : <s.icon size={11} />}{s.label}
            </motion.span>
            {i < STAGES.length - 1 && <span className="h-px w-2 bg-line" />}
          </div>
        )
      })}
    </div>
  )
}

function TechPanel({ t }: { t: Turn }) {
  const r = t.result
  const a = t.analysis
  if (!r) return null
  const hit = r.cache.status === 'exact_hit' || r.cache.status === 'semantic_hit'
  return (
    <div className="grid gap-4 rounded-xl border border-line bg-surface-2/60 p-4 text-xs md:grid-cols-2">
      <div className="space-y-3">
        <p className="font-semibold text-fg">Cache decision</p>
        <KeyValue items={[
          ['Result', <CacheBadge key="r" status={r.cache.status} />],
          ['Similarity', `${sim(r.cache.similarity)}${t.cache?.threshold ? ` (threshold ${t.cache.threshold.toFixed(2)})` : ''}`],
          ...(hit && r.cache.matched_query ? [['Matched question', `“${r.cache.matched_query}”`] as [string, string]] : []),
          ['Why', r.cache.reason ?? '—'],
        ]} />
        {!!t.cache?.candidates?.length && (
          <details className="group">
            <summary className="cursor-pointer text-muted hover:text-fg">Candidates checked ({t.cache.candidates.length})</summary>
            <ul className="mt-2 space-y-1.5">
              {t.cache.candidates.map(c => (
                <li key={c.entry_id} className="rounded-lg bg-surface p-2">
                  <p className="truncate text-fg">“{c.query_text}”</p>
                  <p className="text-faint">sim {sim(c.similarity)} · {c.accepted ? 'accepted' : c.reasons.join('; ')}</p>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
      <div className="space-y-3">
        <p className="font-semibold text-fg">Query intelligence & routing</p>
        <KeyValue items={[
          ['Category', a?.category ?? (hit ? 'not analysed (cache hit)' : '—')],
          ['Complexity', a ? `${a.complexity_level} (score ${a.complexity_score})` : '—'],
          ['Reasoning needed', a ? (a.reasoning_required ? 'yes' : 'no') : '—'],
          ['Model', r.model.id ? `${shortModel(r.model.id)} (${r.model.provider})` : 'none - no LLM call'],
          ['Routing', r.routing?.reason ?? (hit ? 'skipped - answered from cache' : '—')],
          ...(r.fallback_used ? [['Fallback', r.attempts.map(x => `${shortModel(x.model_id)} ${x.ok ? 'ok' : `failed (${x.error})`}`).join(' → ')] as [string, string]] : []),
        ]} />
        {a?.signals?.length ? <p className="text-faint">Signals: {a.signals.join(' · ')}</p> : null}
      </div>
      <div className="space-y-3 md:col-span-2">
        <p className="font-semibold text-fg">Tokens, cost & latency</p>
        <KeyValue items={[
          ['Tokens', r.llm_called ? `${int(r.usage.input_tokens)} in / ${int(r.usage.output_tokens)} out (${r.usage.source === 'provider' ? 'provider-reported' : r.usage.source})` : '0 - no LLM call'],
          ['Cost', r.llm_called ? `${usd(r.cost.usd)} (${COST_LABEL[r.cost.status ?? ''] ?? r.cost.status})` : '$0'],
          ['Saved', `${usd(r.cost.saved_by_cache_usd + r.cost.saved_by_routing_usd)} (counterfactual: cache ${usd(r.cost.saved_by_cache_usd)}, routing ${usd(r.cost.saved_by_routing_usd)})`],
          ['Latency', `${ms(r.latency_ms)} total · ` + Object.entries(r.stage_timings).filter(([k]) => k !== 'total').map(([k, v]) => `${k.replace('_', ' ')} ${ms(v)}`).join(' · ')],
        ]} />
      </div>
    </div>
  )
}

function Message({ t }: { t: Turn }) {
  const [open, setOpen] = useState(false)
  const [focus, setFocus] = useState<number | null>(null)
  const r = t.result
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="space-y-3">
      <div className="flex justify-end">
        <div className="flex max-w-[85%] items-start gap-2.5">
          <div className="rounded-2xl rounded-tr-md bg-accent px-4 py-2.5 text-sm text-accent-contrast shadow-sm">{t.query}</div>
          <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-surface-2 text-muted"><User size={14} /></div>
        </div>
      </div>
      <div className="flex items-start gap-2.5">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent to-cyan text-white"><Bot size={14} /></div>
        <div className="card min-w-0 flex-1 space-y-3 p-4">
          {t.pending && <PipelineStrip stages={t.stages} />}
          {t.error ? <Alert>{t.error}</Alert> : t.answer ? <AnswerText text={t.answer} onCite={n => { setFocus(n); setOpen(true) }} />
            : t.pending && <div className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" />Working…</div>}
          {t.fallback && <p className="text-xs text-warn">{t.fallback}</p>}

          {!!t.citations.length && (
            <div className="flex flex-wrap gap-1.5">
              {t.citations.map(c => (
                <button key={c.index} onClick={() => { setFocus(c.index); setOpen(true) }}
                  className={`focus-ring flex max-w-full items-center gap-1.5 rounded-lg border px-2 py-1 text-[11px] transition-colors hover:bg-surface-2 ${focus === c.index ? 'border-accent/40' : 'border-line'}`}>
                  <span className="font-semibold text-accent">{c.index}</span><FileText size={11} className="text-faint" />
                  <span className="truncate text-muted">{c.filename}{c.page ? ` · p.${c.page}` : ''}</span>
                </button>
              ))}
            </div>
          )}

          {r && (
            <div className="flex flex-wrap items-center gap-1.5 border-t border-line pt-3">
              <CacheBadge status={r.cache.status} />
              {r.is_mock && <MockBadge />}
              {r.cache.similarity != null && <Badge title="Best cache similarity">sim {sim(r.cache.similarity)}</Badge>}
              {r.model.id && <Badge tone="accent">{shortModel(r.model.id)}</Badge>}
              {r.analysis && <Badge>{r.analysis.category} · {r.analysis.complexity_level}</Badge>}
              <Badge>{ms(r.latency_ms)}</Badge>
              {r.llm_called && <Badge>{int(r.usage.input_tokens + r.usage.output_tokens)} tok</Badge>}
              <Badge tone={r.llm_called ? 'neutral' : 'ok'}>{r.llm_called ? usd(r.cost.usd) : 'no LLM cost'}</Badge>
              <button onClick={() => setOpen(o => !o)} aria-expanded={open}
                className="focus-ring ml-auto flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-muted hover:bg-surface-2 hover:text-fg">
                How was this generated? <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
              </button>
            </div>
          )}
          <AnimatePresence initial={false}>
            {open && r && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                <TechPanel t={t} />
                {!!t.citations.length && (
                  <div className="mt-3 space-y-2">
                    {t.citations.map(c => (
                      <div key={c.index} className={`rounded-xl border p-3 text-xs ${focus === c.index ? 'border-accent/40 bg-accent-soft/40' : 'border-line'}`}>
                        <p className="mb-1 flex items-center justify-between gap-2 font-medium text-fg">
                          <span>[{c.index}] {c.filename}{c.page ? ` · page ${c.page}` : ''} · v{c.document_version}</span>
                          <span className="font-normal text-faint">relevance {sim(c.score)}</span>
                        </p>
                        <p className="leading-relaxed text-muted">{c.snippet}</p>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  )
}

export default function Playground() {
  const [conv, setConv] = useState(readConv)
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [selected, setSelected] = useState<number[]>([])
  const [model, setModel] = useState('')
  const [busy, setBusy] = useState(false)
  const [showDocs, setShowDocs] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const docs = usePolling(api.documents, 0)
  const models = usePolling(api.models, 0)
  const available = useMemo(() => models.data?.models.filter(m => m.available) ?? [], [models.data])
  const indexed = docs.data?.filter(d => d.status === 'indexed') ?? []

  useEffect(() => { try { localStorage.setItem(CONV_KEY, conv) } catch { /* ignore */ } }, [conv])
  useEffect(() => {
    let cancelled = false
    api.history(conv).then(h => { if (!cancelled) setTurns(h.map(fromResult)) }).catch(() => {})
    return () => { cancelled = true }
  }, [conv])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns])

  const update = (id: string, fn: (t: Turn) => Turn) => setTurns(ts => ts.map(t => (t.id === id ? fn(t) : t)))

  async function send() {
    const q = input.trim()
    if (!q || busy) return
    const id = `t${Date.now()}`
    setInput('')
    setBusy(true)
    setTurns(ts => [...ts, { id, query: q, answer: '', pending: true, citations: [], stages: { embedding: 'active' } }])
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      await streamQuery({ query: q, document_ids: selected.length ? selected : null, model_id: model || null, conversation_id: conv }, ev => {
        switch (ev.type) {
          case 'stage': update(id, t => ({ ...t, stages: { ...t.stages, embedding: 'done', cache: 'active' } })); break
          case 'cache': {
            const hit = ev.status === 'exact_hit' || ev.status === 'semantic_hit'
            update(id, t => ({ ...t, cache: ev, stages: { ...t.stages, embedding: 'done', cache: 'done',
              ...(hit ? { retrieval: 'skipped', routing: 'skipped', llm: 'skipped' } : { retrieval: 'active' }) } }))
            break
          }
          case 'analysis': update(id, t => ({ ...t, analysis: ev.analysis })); break
          case 'retrieval': update(id, t => ({ ...t, citations: ev.citations, stages: { ...t.stages, retrieval: t.stages.retrieval === 'skipped' ? 'skipped' : 'done', routing: t.stages.routing === 'skipped' ? 'skipped' : 'active' } })); break
          case 'routing': update(id, t => ({ ...t, routing: ev.routing, stages: { ...t.stages, routing: 'done', llm: 'active' } })); break
          case 'fallback': update(id, t => ({ ...t, fallback: `${shortModel(ev.failed_model)} failed (${ev.error}) - trying the next model…` })); break
          case 'token': update(id, t => ({ ...t, answer: t.answer + ev.text })); break
          case 'done': update(id, t => ({ ...fromResult(ev.result), id: t.id, cache: { ...ev.result.cache, threshold: t.cache?.threshold, candidates: t.cache?.candidates }, fallback: t.fallback })); break
          case 'error': update(id, t => ({ ...t, pending: false, error: ev.message })); break
        }
      }, ctrl.signal)
    } catch (e) {
      const aborted = e instanceof DOMException && e.name === 'AbortError'
      update(id, t => ({ ...t, pending: false, error: aborted ? 'Stopped.' : e instanceof Error ? e.message : 'Request failed' }))
    } finally {
      setBusy(false)
      abortRef.current = null
      docs.refresh()
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">AI Playground</h1>
          <p className="mt-0.5 text-sm text-muted">Ask about your documents. Every answer shows how it was produced.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <button onClick={() => setShowDocs(s => !s)} aria-expanded={showDocs}
              className="focus-ring flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm hover:bg-surface-2">
              <FileText size={14} className="text-muted" />{selected.length ? `${selected.length} document${selected.length > 1 ? 's' : ''}` : 'All documents'}<ChevronDown size={13} className="text-muted" />
            </button>
            <AnimatePresence>
              {showDocs && (
                <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                  className="card absolute right-0 z-20 mt-1.5 w-72 p-2 shadow-xl">
                  <button onClick={() => setSelected([])} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-surface-2">
                    <CircleDot size={13} className={selected.length ? 'text-faint' : 'text-accent'} />All indexed documents
                  </button>
                  <div className="my-1 h-px bg-line" />
                  <div className="scrollbar-thin max-h-64 overflow-y-auto">
                    {indexed.length ? indexed.map(d => (
                      <label key={d.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surface-2">
                        <input type="checkbox" className="accent-[var(--accent)]" checked={selected.includes(d.id)}
                          onChange={e => setSelected(s => e.target.checked ? [...s, d.id] : s.filter(x => x !== d.id))} />
                        <span className="truncate">{d.filename}</span><span className="ml-auto text-[11px] text-faint">v{d.version}</span>
                      </label>
                    )) : <p className="px-2 py-2 text-xs text-muted">No documents yet. <Link className="text-accent" to="/documents">Upload some</Link>.</p>}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <div className="w-64">
            <Select aria-label="Model" value={model} onChange={e => setModel(e.target.value)}>
              <option value="">Auto-route (recommended)</option>
              {available.map(m => <option key={m.id} value={m.id}>{m.display_name} · {m.tier}</option>)}
            </Select>
          </div>
          <button onClick={() => { setConv(newConvId()); setTurns([]) }} title="New conversation"
            className="focus-ring grid h-9 w-9 place-items-center rounded-lg border border-line text-muted hover:bg-surface-2 hover:text-fg"><MessageSquarePlus size={15} /></button>
        </div>
      </div>

      {models.data?.mock_mode && (
        <div className="pb-3"><Alert tone="warn" title="Test mode">No LLM API key is configured, so answers come from a mock provider that quotes the retrieved passages. They are labelled and are not real LLM output. Add a key to <code className="font-mono">.env</code> and restart the backend to use Claude, Gemini or an OpenAI-compatible model.</Alert></div>
      )}

      <div className="scrollbar-thin -mx-1 flex-1 space-y-6 overflow-y-auto px-1 pb-4">
        {!turns.length && (
          <div className="flex h-full flex-col items-center justify-center gap-4 py-10 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-accent to-cyan text-white shadow-lg"><Sparkles size={20} /></div>
            <div>
              <p className="font-medium">Ask a question about your documents</p>
              <p className="mt-1 max-w-md text-sm text-muted">{indexed.length ? `${indexed.length} indexed document${indexed.length > 1 ? 's' : ''} available. Ask the same thing twice (or rephrase it) to see the semantic cache at work.` : 'Upload a PDF or TXT file in the Document Library first.'}</p>
            </div>
            {!indexed.length && <Link to="/documents" className="text-sm text-accent hover:underline">Go to Document Library →</Link>}
          </div>
        )}
        {turns.map(t => <Message key={t.id} t={t} />)}
        <div ref={endRef} />
      </div>

      <form onSubmit={e => { e.preventDefault(); send() }} className="card flex items-end gap-2 p-2">
        <textarea value={input} onChange={e => setInput(e.target.value)} rows={1} maxLength={2000} aria-label="Your question"
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Ask about your documents…  (Enter to send, Shift+Enter for a new line)"
          className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-faint" />
        {busy ? (
          <button type="button" onClick={() => abortRef.current?.abort()} aria-label="Stop"
            className="focus-ring grid h-9 w-9 place-items-center rounded-lg border border-line text-muted hover:bg-surface-2"><Square size={14} /></button>
        ) : (
          <button type="submit" disabled={!input.trim()} aria-label="Send"
            className="focus-ring grid h-9 w-9 place-items-center rounded-lg bg-accent text-accent-contrast transition hover:brightness-110 disabled:opacity-40"><Send size={15} /></button>
        )}
      </form>
      <p className="pt-2 text-center text-[11px] text-faint">Answers come only from your documents · token costs are estimates (tokens × list price)</p>
    </div>
  )
}
