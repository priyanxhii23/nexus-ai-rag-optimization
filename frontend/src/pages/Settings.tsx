import { motion } from 'framer-motion'
import { KeyRound, Moon, Plus, RefreshCw, Save, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { stagger } from '../animations/variants'
import { TIER_COLOR } from '../components/charts'
import { Alert, Badge, Button, Card, Input, KeyValue, Label, Modal, PageHeader, SectionNote, Select, Skeleton, Table, Toggle } from '../components/ui'
import { useTheme } from '../contexts/ThemeContext'
import { usePolling } from '../hooks/usePolling'
import { api, type ModelInfo, type RuntimeSettings } from '../services/api'

export default function Settings() {
  const { theme, setTheme, reduceMotion, setReduceMotion } = useTheme()
  const settings = usePolling(api.settings, 0)
  const models = usePolling(api.models, 0)
  const [draft, setDraft] = useState<RuntimeSettings | null>(null)
  const [msg, setMsg] = useState<{ tone: 'info' | 'err'; text: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [pricing, setPricing] = useState<ModelInfo | null>(null)
  const [adding, setAdding] = useState<string | null>(null)

  useEffect(() => { if (settings.data && !draft) setDraft(settings.data.runtime) }, [settings.data, draft])
  const env = settings.data?.environment

  async function save() {
    if (!draft) return
    setSaving(true); setMsg(null)
    try { const r = await api.updateSettings(draft); setDraft(r.runtime); settings.refresh(); setMsg({ tone: 'info', text: 'Settings saved. They take effect immediately and survive restarts.' }) }
    catch (e) { setMsg({ tone: 'err', text: e instanceof Error ? e.message : 'Save failed' }) } finally { setSaving(false) }
  }
  async function toggleModel(m: ModelInfo, enabled: boolean) {
    try { await api.updateModel(m.id, { enabled }); models.refresh() } catch (e) { setMsg({ tone: 'err', text: e instanceof Error ? e.message : 'Failed' }) }
  }

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Settings" description="Cache, routing and retrieval settings are stored in the database. API keys live only in the .env file on your computer and are never sent to the browser." />
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

      <Card title="Appearance">
        <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Theme">
          {(['light', 'dark'] as const).map(t => (
            <button key={t} role="radio" aria-checked={theme === t} onClick={() => setTheme(t)}
              className={`focus-ring flex items-center gap-3 rounded-xl border p-4 text-left text-sm transition-colors ${theme === t ? 'border-accent bg-accent-soft' : 'border-line hover:bg-surface-2'}`}>
              {t === 'light' ? <Sun size={16} /> : <Moon size={16} />}<span className="font-medium capitalize">{t} mode</span>
              {theme === t && <Badge tone="accent" className="ml-auto">active</Badge>}
            </button>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between rounded-xl border border-line p-3">
          <div><p className="text-sm font-medium">Reduce motion</p><p className="text-xs text-muted">Turns off animations (your operating-system setting is also respected).</p></div>
          <Toggle label="Reduce motion" checked={reduceMotion} onChange={setReduceMotion} />
        </div>
        <p className="mt-3 text-xs text-faint">Saved in this browser and restored after refresh.</p>
      </Card>

      <Card title="Cache, routing & retrieval" action={<Button variant="primary" icon={Save} loading={saving} onClick={save} disabled={!draft}>Save</Button>}>
        {!draft ? <Skeleton className="h-32" /> : (
          <div className="grid gap-5 md:grid-cols-2">
            <div className="flex items-center justify-between rounded-xl border border-line p-3 md:col-span-2">
              <div><p className="text-sm font-medium">Semantic cache</p><p className="text-xs text-muted">Reuse validated answers to equivalent questions.</p></div>
              <Toggle label="Semantic cache" checked={draft.cache_enabled} onChange={v => setDraft({ ...draft, cache_enabled: v })} />
            </div>
            <label className="block"><Label hint={draft.similarity_threshold.toFixed(2)}>Similarity threshold</Label>
              <input type="range" min={0.5} max={1} step={0.01} value={draft.similarity_threshold} onChange={e => setDraft({ ...draft, similarity_threshold: Number(e.target.value) })} className="w-full accent-[var(--accent)]" aria-label="Similarity threshold" />
              <p className="text-[11px] text-faint">Use the optimizer on the Semantic Cache page to pick a measured value.</p></label>
            <label className="block"><Label>Cache time to live (hours)</Label>
              <Input type="number" min={1} max={8760} value={draft.cache_ttl_hours} onChange={e => setDraft({ ...draft, cache_ttl_hours: Math.max(1, Math.round(Number(e.target.value))) })} /></label>
            <label className="block"><Label>Routing strategy</Label>
              <Select value={draft.routing_strategy} onChange={e => setDraft({ ...draft, routing_strategy: e.target.value as RuntimeSettings['routing_strategy'] })}>
                <option value="cost_saver">Cost saver - prefer small models</option><option value="balanced">Balanced - match tier to complexity</option><option value="quality_first">Quality first - prefer large models</option>
              </Select></label>
            <label className="block"><Label hint="1 - 20">Passages retrieved per question</Label>
              <Input type="number" min={1} max={20} value={draft.retrieval_top_k} onChange={e => setDraft({ ...draft, retrieval_top_k: Math.min(20, Math.max(1, Math.round(Number(e.target.value)))) })} /></label>
            <label className="block"><Label hint={draft.min_retrieval_score.toFixed(2)}>Minimum passage relevance</Label>
              <input type="range" min={0} max={0.8} step={0.01} value={draft.min_retrieval_score} onChange={e => setDraft({ ...draft, min_retrieval_score: Number(e.target.value) })} className="w-full accent-[var(--accent)]" aria-label="Minimum passage relevance" />
              <p className="text-[11px] text-faint">Passages below this cosine similarity are ignored. If nothing passes, NEXUS AI says the documents don't contain the answer (no LLM call).</p></label>
          </div>
        )}
      </Card>

      <Card title="LLM providers & models" subtitle="Keys are configured in .env (never here). Prices you enter are stored with their source.">
        {env && (
          <div className="mb-4 grid gap-2 sm:grid-cols-3">
            {Object.entries(env.providers).map(([p, on]) => (
              <div key={p} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-sm">
                <span className="flex items-center gap-2"><KeyRound size={14} className="text-faint" />{p.replace('_', '-')}</span>
                <span className="flex items-center gap-1.5">
                  <Badge tone={on ? 'ok' : 'neutral'}>{on ? 'configured' : 'not set'}</Badge>
                  {on && p !== 'anthropic' && <Button size="sm" variant="ghost" icon={Plus} onClick={() => setAdding(p)} aria-label={`Add a ${p} model`} />}
                </span>
              </div>
            ))}
          </div>
        )}
        {env?.mock_mode_active && <div className="mb-4"><Alert tone="warn" title="Test mode is active">LLM_MOCK_MODE={env.llm_mock_mode}. Answers come from the labelled mock provider. Add ANTHROPIC_API_KEY or GEMINI_API_KEY to .env and restart the backend to use real models.</Alert></div>}
        {models.loading ? <Skeleton className="h-24" /> : (
          <Table head={['Model', 'Tier', 'Price per 1M tokens', 'Status', 'Enabled', '']}>
            {models.data?.models.map(m => (
              <tr key={m.id}>
                <td className="py-2.5 pr-4"><p className="font-medium">{m.display_name}</p><p className="text-[11px] text-faint">{m.id}</p></td>
                <td className="py-2.5 pr-4"><span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: TIER_COLOR[m.tier] }} />{m.tier}</span></td>
                <td className="py-2.5 pr-4 text-xs">{m.is_mock ? <span className="text-muted">simulated as {m.simulates?.split(':')[1]}</span> : m.input_price_per_mtok == null ? <Badge tone="warn">unpriced</Badge> : <span className="tabular">${m.input_price_per_mtok} in / ${m.output_price_per_mtok} out</span>}
                  {!m.is_mock && <p className="max-w-60 truncate text-[11px] text-faint" title={m.price_source ?? ''}>{m.price_source}</p>}</td>
                <td className="py-2.5 pr-4">{m.available ? <Badge tone="ok">available</Badge> : <span className="text-[11px] text-faint">{m.unavailable_reason}</span>}</td>
                <td className="py-2.5 pr-4"><Toggle label={`Enable ${m.display_name}`} checked={m.enabled} onChange={v => toggleModel(m, v)} /></td>
                <td className="py-2.5">{!m.is_mock && <Button size="sm" variant="ghost" onClick={() => setPricing(m)}>Edit price</Button>}</td>
              </tr>
            ))}
          </Table>
        )}
        <div className="mt-3"><SectionNote>Claude prices are Anthropic's published list prices. Gemini and OpenAI-compatible prices are never guessed: enter them from the provider's official pricing page. Costs for unpriced models are reported as "unpriced".</SectionNote></div>
      </Card>

      {env && (
        <Card title="Environment (read-only, from .env)">
          <KeyValue items={[
            ['Version / environment', `${env.version} · ${env.app_env}`], ['Embedding model', env.embedding_model],
            ['LLM_MOCK_MODE', `${env.llm_mock_mode} (test mode ${env.mock_mode_active ? 'active' : 'off'})`],
            ['Upload limit', `${env.max_upload_mb} MB per file`], ['Chunking', `${env.chunk_size_chars} chars, ${env.chunk_overlap_chars} overlap`],
            ['LLM timeout', `${env.llm_timeout_seconds} s`], ['Rate limit', `${env.rate_limit_per_minute} write requests / minute`],
            ['Claude refusal fallback', env.anthropic_server_fallbacks ? 'on (Opus / Sonnet 5.5)' : 'off'],
            ['Gemini models from .env', `${env.gemini_models.small ?? '—'} (small) · ${env.gemini_models.large ?? '—'} (large)`],
            ['OpenAI-compatible', env.openai_compatible.base_url_set ? `${env.openai_compatible.model ?? 'no model set'}` : 'not configured'],
          ]} />
        </Card>
      )}

      <PriceModal model={pricing} onClose={() => setPricing(null)} onSaved={() => { setPricing(null); models.refresh() }} />
      <AddModelModal provider={adding} onClose={() => setAdding(null)} onSaved={() => { setAdding(null); models.refresh() }} />
    </motion.div>
  )
}

function PriceModal({ model, onClose, onSaved }: { model: ModelInfo | null; onClose: () => void; onSaved: () => void }) {
  const [inp, setInp] = useState('')
  const [out, setOut] = useState('')
  const [src, setSrc] = useState('')
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setInp(model?.input_price_per_mtok?.toString() ?? ''); setOut(model?.output_price_per_mtok?.toString() ?? ''); setSrc(''); setErr(null) }, [model])
  async function save() {
    if (!model) return
    try { await api.updateModel(model.id, { input_price_per_mtok: Number(inp), output_price_per_mtok: Number(out), price_source: src || undefined }); onSaved() }
    catch (e) { setErr(e instanceof Error ? e.message : 'Failed') }
  }
  return (
    <Modal open={!!model} onClose={onClose} title={`Price for ${model?.display_name ?? ''}`}>
      <div className="space-y-4">
        {err && <Alert>{err}</Alert>}
        <div className="grid grid-cols-2 gap-3">
          <label><Label>Input $ / 1M tokens</Label><Input type="number" min={0} step="any" value={inp} onChange={e => setInp(e.target.value)} /></label>
          <label><Label>Output $ / 1M tokens</Label><Input type="number" min={0} step="any" value={out} onChange={e => setOut(e.target.value)} /></label>
        </div>
        <label className="block"><Label>Source</Label><Input placeholder="e.g. ai.google.dev/gemini-api/docs/pricing, checked 2026-11-09" value={src} onChange={e => setSrc(e.target.value)} /></label>
        <SectionNote>Copy prices from the provider's official pricing page. They are used for cost estimates only.</SectionNote>
        <div className="flex justify-between gap-2">
          <Button variant="ghost" onClick={async () => { if (model) { await api.updateModel(model.id, { clear_prices: true }); onSaved() } }}>Clear price</Button>
          <div className="flex gap-2"><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={inp === '' || out === ''} onClick={save}>Save price</Button></div>
        </div>
      </div>
    </Modal>
  )
}

function AddModelModal({ provider, onClose, onSaved }: { provider: string | null; onClose: () => void; onSaved: () => void }) {
  const [list, setList] = useState<string[] | null>(null)
  const [name, setName] = useState('')
  const [tier, setTier] = useState('small')
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  async function discover() {
    if (!provider) return
    setLoading(true); setErr(null)
    try { setList((await api.discoverModels(provider)).models) } catch (e) { setErr(e instanceof Error ? e.message : 'Failed') } finally { setLoading(false) }
  }
  useEffect(() => { setList(null); setName(''); setErr(null); if (provider) discover() }, [provider]) // eslint-disable-line react-hooks/exhaustive-deps
  async function add() {
    if (!provider) return
    try { await api.addModel({ provider, model_name: name, tier }); onSaved() } catch (e) { setErr(e instanceof Error ? e.message : 'Failed') }
  }
  return (
    <Modal open={!!provider} onClose={onClose} title={`Add a ${provider ?? ''} model`}>
      <div className="space-y-4">
        {err && <Alert>{err}</Alert>}
        <p className="text-xs text-muted">The list below comes from the provider's API for your key - nothing is guessed. After adding, set its price with “Edit price”.</p>
        <label className="block"><Label hint={<button onClick={discover} className="inline-flex items-center gap-1 text-accent"><RefreshCw size={11} />reload</button>}>Model</Label>
          {loading ? <Skeleton className="h-9" /> : list?.length ? (
            <Select value={name} onChange={e => setName(e.target.value)}><option value="">Choose a model…</option>{list.map(m => <option key={m} value={m}>{m}</option>)}</Select>
          ) : <Input placeholder="model id" value={name} onChange={e => setName(e.target.value)} />}
        </label>
        <label className="block"><Label>Tier</Label><Select value={tier} onChange={e => setTier(e.target.value)}><option value="small">small</option><option value="medium">medium</option><option value="large">large</option></Select></label>
        <div className="flex justify-end gap-2"><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon={Plus} disabled={!name} onClick={add}>Add model</Button></div>
      </div>
    </Modal>
  )
}
