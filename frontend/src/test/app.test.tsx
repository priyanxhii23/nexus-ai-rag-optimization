import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AnswerText } from '../components/Answer'
import { NAV } from '../navigation'
import { ApiError, api } from '../services/api'

const health = {
  status: 'ok', app: 'NEXUS AI', version: '0.4.0', environment: 'test', timestamp: '2026-11-09T00:00:00Z', uptime_seconds: 60,
  components: { database: { status: 'ok', detail: 'SQLite' }, vector_store: { status: 'ok', detail: 'ChromaDB' },
    embeddings: { status: 'ok', detail: 'MiniLM' }, llm: { status: 'ok', detail: 'TEST MODE' } },
  llm_providers: { anthropic: false, gemini: false, openai_compatible: false }, mock_mode: true, models_available: 3,
}
const emptyOverview = {
  has_data: false, window_days: 30, total_queries: 0, errors: 0, cache_hit_rate: null, cache_miss_rate: null, avg_latency_ms: null,
  p95_latency_ms: null, avg_similarity: null, actual_cost_usd: 0, simulated_cost_usd: 0, saved_by_cache_usd: 0, saved_by_routing_usd: 0,
  llm_calls: 0, llm_calls_avoided: 0, small_model_queries: 0, medium_model_queries: 0, large_model_queries: 0, mock_queries: 0,
  daily: [], model_distribution: [], cache_breakdown: {}, recent_activity: [], recent_routing: [],
}
const runtime = { cache_enabled: true, similarity_threshold: 0.92, cache_ttl_hours: 72, routing_strategy: 'balanced', retrieval_top_k: 5, min_retrieval_score: 0.3 }
const model = { id: 'mock:mock-small', provider: 'mock', model_name: 'mock-small', display_name: 'Mock small (test mode)', tier: 'small', is_mock: true, enabled: true,
  available: true, unavailable_reason: null, effort: null, input_price_per_mtok: null, output_price_per_mtok: null, price_source: 'Simulated', simulates: 'anthropic:claude-haiku-5-5' }

const FIXTURES: [RegExp, unknown][] = [
  [/\/api\/health/, health],
  [/\/api\/metrics\/overview/, emptyOverview],
  [/\/api\/metrics\/costs/, { ...emptyOverview, has_data: false, is_simulated: false, unpriced_calls: 0, baseline_estimate_usd: 0, savings_pct: null,
    avg_cost_per_llm_query_usd: null, total_input_tokens: 0, total_output_tokens: 0, weekly: [], models: [], notes: [] }],
  [/\/api\/documents/, []],
  [/\/api\/models/, { mock_mode: true, providers: health.llm_providers, models: [model], strategies: { balanced: { simple: 'small', medium: 'medium', complex: 'large' } } }],
  [/\/api\/settings/, { runtime, defaults: runtime, routing_strategies: ['balanced'], environment: { app_env: 'test', version: '0.4.0', embedding_model: 'MiniLM',
    llm_mock_mode: 'auto', mock_mode_active: true, providers: health.llm_providers, max_upload_mb: 20, llm_timeout_seconds: 60, rate_limit_per_minute: 120,
    chunk_size_chars: 900, chunk_overlap_chars: 150, anthropic_server_fallbacks: true, gemini_models: { small: null, large: null }, openai_compatible: { base_url_set: false, model: null } } }],
  [/\/api\/cache\/stats/, { entries: 0, active: 0, expired: 0, invalidated: 0, total_hits_served: 0, hit_rate_30d: null, exact_hits_30d: 0, semantic_hits_30d: 0,
    misses_30d: 0, saved_usd_30d: 0, avg_hit_latency_ms: null, avg_miss_latency_ms: null, settings: { cache_enabled: true, similarity_threshold: 0.92, cache_ttl_hours: 72 } }],
  [/\/api\/cache\/entries/, { total: 0, entries: [] }],
  [/\/api\/router\/decisions/, []],
  [/\/api\/compare/, []],
  [/\/api\/benchmarks\/datasets/, [{ id: 'nexus_demo_v1', name: 'Demo', description: 'demo', documents: 3, questions: 22, pairs: 20 }]],
  [/\/api\/benchmarks\/runs/, []],
  [/\/api\/monitoring\/events/, []],
  [/\/api\/monitoring\/stats/, { total_processed: 0, queries_last_hour: 0, errors_last_24h: 0, hit_rate_last_hour: null, avg_latency_last_hour_ms: null,
    p95_latency_last_hour_ms: null, cost_last_hour_usd: 0, simulated_cost_last_hour_usd: 0, per_minute: [], model_usage_last_hour: {} }],
  [/\/api\/query\/history/, []],
]

function fakeBackend() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const hit = FIXTURES.find(([re]) => re.test(url))
    if (!hit) return new Response(JSON.stringify({ error: { code: 'not_found', message: 'nope' } }), { status: 404 })
    return new Response(JSON.stringify(hit[1]), { status: 200 })
  })
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.className = ''
  vi.stubGlobal('fetch', fakeBackend())
  window.history.pushState({}, '', '/')
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('navigation', () => {
  it('shows all 10 sections in the sidebar', async () => {
    render(<App />)
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    for (const item of NAV) expect(nav.textContent).toContain(item.label)
    expect(NAV).toHaveLength(10)
  })

  it.each(NAV.map(n => [n.label, n.path]))('%s page renders without errors', async (_label, path) => {
    const errors: unknown[] = []
    const spy = vi.spyOn(console, 'error').mockImplementation((...a) => { errors.push(a) })
    window.history.pushState({}, '', path)
    render(<App />)
    await waitFor(() => expect(document.querySelector('main h1')).not.toBeNull(), { timeout: 4000 })
    expect(document.querySelector('main')!.textContent).not.toContain('Page not found')
    spy.mockRestore()
    expect(errors.filter(e => !String(e).includes('act('))).toEqual([])
  })
})

describe('theme', () => {
  it('toggles dark mode and persists the choice', async () => {
    render(<App />)
    const button = await screen.findByRole('button', { name: /switch to dark mode/i })
    act(() => { fireEvent.click(button) })
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('nexus-theme')).toBe('dark')
    act(() => { fireEvent.click(screen.getByRole('button', { name: /switch to light mode/i })) })
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('nexus-theme')).toBe('light')
  })

  it('restores the saved theme after a reload', async () => {
    localStorage.setItem('nexus-theme', 'dark')
    render(<App />)
    await screen.findByRole('button', { name: /switch to light mode/i })
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})

describe('overview', () => {
  it('shows an honest empty state on a fresh install and the test-mode label', async () => {
    render(<App />)
    expect(await screen.findByText(/Welcome to NEXUS AI/)).toBeTruthy()
    expect(screen.getByText(/Nothing on this page is pre-filled/)).toBeTruthy()
    expect((await screen.findAllByText('Test mode')).length).toBeGreaterThan(0)
  })
})

describe('api client', () => {
  it('turns backend error JSON into a readable message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: { code: 'validation_error', message: 'The request is invalid.',
      fields: [{ field: 'query', message: 'must not be blank' }] } }), { status: 422 })))
    await expect(api.analyze(' ')).rejects.toMatchObject({ status: 422, code: 'validation_error', message: 'The request is invalid.: query must not be blank' })
  })
  it('reports an unreachable backend clearly', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    const err = await api.health().catch(e => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toMatch(/not reachable/)
  })
})

describe('answer rendering', () => {
  it('renders citations as chips and never injects HTML', () => {
    const onCite = vi.fn()
    const { container } = render(<AnswerText text={'Refunds take **5 days** [1].\n\n- item <img src=x onerror=alert(1)> [2]'} onCite={onCite} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(container.querySelector('strong')?.textContent).toBe('5 days')
    fireEvent.click(screen.getByTitle('Source 2'))
    expect(onCite).toHaveBeenCalledWith(2)
  })
})
