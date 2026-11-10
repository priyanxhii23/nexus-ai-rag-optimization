import { motion } from 'framer-motion'
import { Download, FlaskConical, History, Play } from 'lucide-react'
import { useMemo, useState } from 'react'
import { stagger } from '../animations/variants'
import { AnswerText } from '../components/Answer'
import { BarsChart, SERIES, TIER_COLOR } from '../components/charts'
import { Alert, Badge, Button, Card, EmptyState, KeyValue, Label, MockBadge, PageHeader, SectionNote, Select, Skeleton, Textarea } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api, type Comparison } from '../services/api'
import { ago, int, ms, sim, usd } from '../services/format'

export default function Compare() {
  const models = usePolling(api.models, 0)
  const docs = usePolling(api.documents, 0)
  const history = usePolling(api.comparisons, 0)
  const available = useMemo(() => models.data?.models.filter(m => m.available) ?? [], [models.data])
  const [chosen, setPicked] = useState<string[] | null>(null)
  // default selection = first three available models, until the user changes it
  const picked = chosen ?? available.slice(0, 3).map(m => m.id)
  const [query, setQuery] = useState('')
  const [reference, setReference] = useState('')
  const [docId, setDocId] = useState('')
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<Comparison | null>(null)


  async function run() {
    setRunning(true); setErr(null)
    try {
      const r = await api.compare({ query, model_ids: picked, document_ids: docId ? [Number(docId)] : null, reference_answer: reference || null })
      setResult(r); history.refresh()
    } catch (e) { setErr(e instanceof Error ? e.message : 'Comparison failed') } finally { setRunning(false) }
  }
  async function open(id: number) {
    try { setResult(await api.comparison(id)) } catch (e) { setErr(e instanceof Error ? e.message : 'Failed') }
  }

  const ok = result?.results.filter(r => !r.error) ?? []
  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Model Comparison Lab" description="Send the same question with the same retrieved context to several models at once. The cache is bypassed so every model really answers." />
      {err && <Alert>{err}</Alert>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Set up a comparison" className="lg:col-span-2">
          <div className="space-y-4">
            <label className="block"><Label>Question</Label><Textarea rows={2} value={query} onChange={e => setQuery(e.target.value)} placeholder="e.g. What does the Pro plan include?" /></label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block"><Label>Documents</Label>
                <Select value={docId} onChange={e => setDocId(e.target.value)}>
                  <option value="">All indexed documents</option>
                  {docs.data?.filter(d => d.status === 'indexed').map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
                </Select></label>
              <label className="block"><Label hint="optional">Reference answer</Label><Textarea rows={1} value={reference} onChange={e => setReference(e.target.value)} placeholder="Used to score similarity to an ideal answer" /></label>
            </div>
            <div>
              <Label hint={`${picked.length} selected (max 6)`}>Models</Label>
              {models.loading ? <Skeleton className="h-9" /> : available.length ? (
                <div className="flex flex-wrap gap-2">
                  {available.map(m => {
                    const on = picked.includes(m.id)
                    return (
                      <button key={m.id} onClick={() => setPicked(on ? picked.filter(x => x !== m.id) : picked.length < 6 ? [...picked, m.id] : picked)} aria-pressed={on}
                        className={`focus-ring flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${on ? 'border-accent/40 bg-accent-soft text-fg' : 'border-line text-muted hover:bg-surface-2'}`}>
                        <span className="h-2 w-2 rounded-sm" style={{ background: TIER_COLOR[m.tier] }} />{m.display_name}
                      </button>
                    )
                  })}
                </div>
              ) : <p className="text-xs text-muted">No models available.</p>}
            </div>
            <div className="flex items-center justify-between gap-3">
              <SectionNote>{models.data?.mock_mode ? 'Test mode: the mock models give extractive, labelled answers and simulated costs.' : 'This calls every selected model once - real API cost.'}</SectionNote>
              <Button variant="primary" icon={Play} loading={running} disabled={!query.trim() || !picked.length} onClick={run}>Compare</Button>
            </div>
          </div>
        </Card>
        <Card title="Previous comparisons" action={<History size={14} className="text-faint" />}>
          {history.data?.length ? (
            <ul className="-my-1.5 divide-y divide-line">
              {history.data.slice(0, 8).map(h => (
                <li key={h.id}><button onClick={() => open(h.id)} className="w-full py-2 text-left hover:text-accent">
                  <p className="truncate text-sm">{h.query}</p><p className="text-[11px] text-faint">{h.models.length} models · {ago(h.created_at)}{h.is_mock ? ' · test mode' : ''}</p>
                </button></li>
              ))}
            </ul>
          ) : <EmptyState icon={<FlaskConical size={18} />} title="None yet" body="Comparisons are saved so you can reopen and download them." />}
        </Card>
      </div>

      {result && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <Card title={`Results: “${result.query}”`} subtitle={`${result.context.length} passages shared by every model · ${new Date(result.created_at).toLocaleString()}`}
            action={<>{result.is_mock && <MockBadge />}<a href={`/api/compare/${result.id}/report`} className="focus-ring inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-2.5 text-xs font-medium hover:bg-surface-2"><Download size={13} />Report (.md)</a></>}>
            {ok.length > 0 && (
              <div className="grid gap-4 md:grid-cols-2">
                <BarsChart horizontal data={ok.map(r => ({ name: r.model, latency: r.latency_ms }))} xKey="name" format={ms} height={Math.max(120, ok.length * 42)} series={[{ key: 'latency', name: 'Latency', color: SERIES[0] }]} />
                <BarsChart horizontal data={ok.map(r => ({ name: r.model, cost: r.cost_usd ?? 0 }))} xKey="name" format={usd} height={Math.max(120, ok.length * 42)} series={[{ key: 'cost', name: 'Cost', color: SERIES[0] }]} />
              </div>
            )}
          </Card>
          <div className={`grid gap-4 ${result.results.length > 1 ? 'md:grid-cols-2' : ''} ${result.results.length > 2 ? 'xl:grid-cols-3' : ''}`}>
            {result.results.map(r => (
              <Card key={r.model_id} title={<span className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm" style={{ background: TIER_COLOR[r.tier] }} />{r.model}</span>} subtitle={`${r.provider} · ${r.tier} tier`}>
                {r.error ? <Alert>{r.error}</Alert> : (
                  <div className="space-y-4">
                    <KeyValue items={[
                      ['Latency', ms(r.latency_ms)],
                      ['Tokens', `${int(r.input_tokens)} in / ${int(r.output_tokens)} out (${r.usage_source === 'provider' ? 'provider-reported' : r.usage_source})`],
                      ['Cost', r.cost_usd == null ? 'unpriced - set a price in Settings' : `${usd(r.cost_usd)} (${r.cost_status === 'priced' ? 'estimated' : r.cost_status})`],
                      ['Faithfulness', r.faithfulness == null ? '—' : `${Math.round(r.faithfulness * 100)}% of sentences grounded`],
                      ['Citations used', String(r.citations_used ?? 0)],
                      ...(r.reference_similarity != null ? [['Similarity to reference', sim(r.reference_similarity)] as [string, string]] : []),
                    ]} />
                    <div className="max-h-80 overflow-y-auto rounded-xl border border-line bg-surface-2/40 p-3"><AnswerText text={r.answer ?? ''} /></div>
                  </div>
                )}
              </Card>
            ))}
          </div>
          <Card title="Shared context" subtitle="Every model received exactly these passages, in this order">
            <ul className="space-y-2 text-xs">{result.context.map(c => <li key={c.index} className="rounded-lg border border-line p-2.5"><p className="font-medium">[{c.index}] {c.filename}{c.page ? ` · p.${c.page}` : ''} <Badge className="ml-1">score {sim(c.score)}</Badge></p><p className="mt-1 text-muted">{c.snippet}</p></li>)}</ul>
            <div className="mt-3"><SectionNote>Quality columns are automatic heuristics (sentence-level grounding in the passages and similarity to your reference), not human ratings.</SectionNote></div>
          </Card>
        </motion.div>
      )}
    </motion.div>
  )
}
