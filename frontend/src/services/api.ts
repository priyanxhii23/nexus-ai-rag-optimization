// Typed client for the FastAPI backend. All requests go to /api (proxied by Vite to :8000),
// so API keys never exist in the browser.

export interface ComponentHealth { status: 'ok' | 'error' | 'pending' | 'loading' | 'not_configured'; detail: string }
export interface Health {
  status: 'ok' | 'degraded'; app: string; version: string; environment: string; timestamp: string
  uptime_seconds: number; components: Record<string, ComponentHealth>; llm_providers: Record<string, boolean>
  mock_mode: boolean; models_available: number
}
export interface DailyPoint {
  date: string; queries: number; hits: number; misses: number; errors: number; cost_usd: number
  simulated_cost_usd: number; saved_usd: number; avg_latency_ms: number | null; p95_latency_ms: number | null
}
export interface ActivityItem {
  id: number; query_text: string; cache_status: string; total_latency_ms: number; model: string | null
  cost_usd: number; cost_status: string | null; is_mock: boolean; created_at: string
}
export interface RoutingItem {
  id: number; query_text: string; category: string | null; complexity: string | null; complexity_score: number | null
  model: string | null; model_name: string | null; routed_by: string | null; reason: string | null; created_at: string
}
export interface Overview {
  has_data: boolean; window_days: number; total_queries: number; errors: number
  cache_hit_rate: number | null; cache_miss_rate: number | null; avg_latency_ms: number | null; p95_latency_ms: number | null
  avg_similarity: number | null; actual_cost_usd: number; simulated_cost_usd: number
  saved_by_cache_usd: number; saved_by_routing_usd: number; llm_calls: number; llm_calls_avoided: number
  small_model_queries: number; medium_model_queries: number; large_model_queries: number; mock_queries: number
  daily: DailyPoint[]; model_distribution: { model_id: string; name: string; tier: string | null; count: number }[]
  cache_breakdown: Record<string, number>; recent_activity: ActivityItem[]; recent_routing: RoutingItem[]
}
export interface CostModel {
  model_id: string; name: string; tier: string | null; calls: number; failed_calls: number; input_tokens: number
  output_tokens: number; provider_reported_calls: number; estimated_usage_calls: number; cost_usd: number
  cost_status: string | null; avg_latency_ms: number | null; p95_latency_ms: number | null
}
export interface CostReport {
  window_days: number; has_data: boolean; is_simulated: boolean; actual_cost_usd: number; simulated_cost_usd: number
  unpriced_calls: number; saved_by_cache_usd: number; saved_by_routing_usd: number; baseline_estimate_usd: number
  savings_pct: number | null; avg_cost_per_llm_query_usd: number | null; total_input_tokens: number
  total_output_tokens: number; daily: DailyPoint[]
  weekly: { week: string; cost_usd: number; simulated_cost_usd: number; saved_usd: number; queries: number }[]
  models: CostModel[]; notes: string[]
}
export interface DocumentInfo {
  id: number; filename: string; file_type: string | null; version: number; size_bytes: number; chunk_count: number
  page_count: number | null; char_count: number | null; status: string; flagged_chunks: number; content_hash: string
  error: string | null; created_at: string; updated_at: string
}
export interface UploadResult { filename: string; status: 'created' | 'duplicate' | 'rejected'; document?: DocumentInfo; message?: string | null; code?: string }
export interface Citation {
  index: number; document_id: number; filename: string; page: number | null; chunk_index: number; score: number
  snippet: string; document_version: number
}
export interface Analysis {
  category: string; complexity_score: number; complexity_level: string; retrieval_required: boolean
  reasoning_required: boolean; multi_step: boolean; word_count: number; signals: string[]
  matched_categories: string[]; processing_path: string
}
export interface Routing {
  model_id: string; model?: string; provider?: string; tier?: string; wanted_tier?: string; routed_by: string
  reason: string; fallback_chain?: string[]
}
export interface CacheCandidate { entry_id: number; query_text: string; similarity: number; accepted: boolean; reasons: string[] }
export interface QueryResult {
  request_id: number; conversation_id: string | null; query: string; answer: string | null; is_mock: boolean; mode: string
  created_at: string | null
  cache: { status: string; similarity: number | null; reason: string | null; entry_id: number | null; matched_query?: string | null; entry_created_at?: string | null }
  analysis: Analysis | null; routing: Routing | null; model: { id: string | null; provider: string | null }
  citations: Citation[]; usage: { input_tokens: number; output_tokens: number; source: string | null }
  cost: { usd: number; status: string | null; saved_by_cache_usd: number; saved_by_routing_usd: number; note: string }
  latency_ms: number; stage_timings: Record<string, number>; fallback_used: boolean
  attempts: { model_id: string; ok: boolean; error?: string; ms: number }[]; llm_called: boolean | null
  retrieval: { count: number; top_score: number | null }; error: string | null
}
export type StreamEvent =
  | { type: 'started'; request_id: number; conversation_id: string; mock_mode: boolean }
  | { type: 'stage'; stage: string; ms: number }
  | { type: 'cache'; status: string; similarity: number | null; threshold: number; reason: string; candidates: CacheCandidate[] }
  | { type: 'analysis'; analysis: Analysis }
  | { type: 'retrieval'; count: number; citations: Citation[]; ms: number | null }
  | { type: 'routing'; routing: Routing }
  | { type: 'fallback'; failed_model: string; error: string }
  | { type: 'token'; text: string }
  | { type: 'done'; result: QueryResult }
  | { type: 'error'; code: string; message: string }
export interface ModelInfo {
  id: string; provider: string; model_name: string; display_name: string; tier: 'small' | 'medium' | 'large'
  is_mock: boolean; enabled: boolean; available: boolean; unavailable_reason: string | null; effort: string | null
  input_price_per_mtok: number | null; output_price_per_mtok: number | null; price_source: string | null; simulates: string | null
}
export interface ModelsResponse { mock_mode: boolean; providers: Record<string, boolean>; models: ModelInfo[]; strategies: Record<string, Record<string, string>> }
export interface CacheEntry {
  id: number; query_text: string; status: string; invalidated_reason: string | null; intent_category: string | null
  scope_key: string; documents: { document_id: number; version: number; filename: string | null; current_version: number | null; exists: boolean }[]
  model: string | null; provider: string | null; is_mock: boolean; original_cost_usd: number | null
  original_latency_ms: number | null; input_tokens: number | null; output_tokens: number | null; hit_count: number
  last_similarity: number | null; last_hit_at: string | null; created_at: string; expires_at: string; response_preview: string
  response_text?: string; citations?: Citation[]
  hit_history?: { request_id: number; query_text: string; status: string; similarity: number | null; reason: string | null; created_at: string }[]
}
export interface CacheStats {
  entries: number; active: number; expired: number; invalidated: number; total_hits_served: number
  hit_rate_30d: number | null; exact_hits_30d: number; semantic_hits_30d: number; misses_30d: number; saved_usd_30d: number
  avg_hit_latency_ms: number | null; avg_miss_latency_ms: number | null
  settings: { cache_enabled: boolean; similarity_threshold: number; cache_ttl_hours: number }
}
export interface ThresholdResult {
  threshold: number; reuse_rate: number | null; false_match_rate: number | null; reuse_rate_with_guard: number
  false_match_rate_with_guard: number | null; precision: number | null; projected_avg_latency_ms?: number
}
export interface ThresholdExperiment {
  pairs: { a: string; b: string; same_intent: boolean; similarity: number; guard_blocks: string[] }[]
  results: ThresholdResult[]; recommended_threshold: number; recommendation_reason: string; current_threshold: number | null
  positives: number; negatives: number; latency_note: string; embedding_model: string
}
export interface CompareResultItem {
  model_id: string; model: string; provider: string; tier: string; is_mock?: boolean; answer?: string; error?: string
  latency_ms: number; input_tokens?: number; output_tokens?: number; usage_source?: string; cost_usd?: number | null
  cost_status?: string; faithfulness?: number | null; citations_used?: number; answer_chars?: number; reference_similarity?: number | null
}
export interface Comparison { id: number; query: string; document_ids: number[]; context: Citation[]; results: CompareResultItem[]; is_mock: boolean; created_at: string }
export interface BenchmarkSummaryConfig {
  label: string; questions: number; avg_latency_ms: number | null; median_latency_ms: number | null; p95_latency_ms: number | null
  cache_hit_rate: number | null; cache_miss_rate: number | null; llm_calls: number; llm_calls_avoided: number
  input_tokens: number; output_tokens: number; cost_usd: number; retrieval_relevance: number | null
  answer_correctness: number | null; answer_faithfulness: number | null; models_used: string[]
  cost_reduction_vs_baseline?: number | null; latency_reduction_vs_baseline?: number | null
}
export interface BenchmarkRun {
  id: number; name: string; dataset: string; configs: string[]; settings: { threshold?: number | null } | null; status: string
  progress: number; is_simulated: boolean; error: string | null; created_at: string; finished_at: string | null
  summary: { configs: Record<string, BenchmarkSummaryConfig>; is_simulated: boolean; note: string } | null
  results?: { config: string; question_id: string; question: string; cache_status: string; model: string | null; complexity: string | null;
    latency_ms: number; input_tokens: number; output_tokens: number; cost_usd: number; llm_called: boolean;
    retrieval_hit: number | null; correctness: number | null; faithfulness: number | null }[]
}
export interface Dataset { id: string; name: string; description: string; documents: number; questions: number; pairs: number }
export interface SystemEvent { id: number; type: string; level: 'info' | 'warning' | 'error'; message: string; request_id: number | null; data: Record<string, unknown> | null; created_at: string }
export interface MonitoringStats {
  total_processed: number; queries_last_hour: number; errors_last_24h: number; hit_rate_last_hour: number | null
  avg_latency_last_hour_ms: number | null; p95_latency_last_hour_ms: number | null; cost_last_hour_usd: number
  simulated_cost_last_hour_usd: number; per_minute: { minute: string; queries: number }[]; model_usage_last_hour: Record<string, number>
}
export interface RuntimeSettings {
  cache_enabled: boolean; similarity_threshold: number; cache_ttl_hours: number
  routing_strategy: 'balanced' | 'cost_saver' | 'quality_first'; retrieval_top_k: number; min_retrieval_score: number
}
export interface SettingsResponse {
  runtime: RuntimeSettings; defaults: RuntimeSettings; routing_strategies: string[]
  environment: {
    app_env: string; version: string; embedding_model: string; llm_mock_mode: string; mock_mode_active: boolean
    providers: Record<string, boolean>; max_upload_mb: number; llm_timeout_seconds: number; rate_limit_per_minute: number
    chunk_size_chars: number; chunk_overlap_chars: number; anthropic_server_fallbacks: boolean
    gemini_models: { small: string | null; large: string | null }; openai_compatible: { base_url_set: boolean; model: string | null }
  }
}
export interface RouterDecision {
  id: number; query_text: string; category: string | null; complexity: string | null; complexity_score: number | null
  model: string | null; routed_by: string | null; reason: string | null; fallback_used: boolean; latency_ms: number
  cost_usd: number | null; cost_status: string | null; saved_by_routing_usd: number | null; created_at: string
}

export class ApiError extends Error {
  status: number
  code: string
  extra: Record<string, unknown>
  constructor(status: number, code: string, message: string, extra: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.extra = extra
  }
}

async function request<T>(method: string, path: string, body?: unknown, timeoutMs = 30000): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const isForm = body instanceof FormData
    const res = await fetch(`/api${path}`, {
      method, signal: ctrl.signal,
      headers: body && !isForm ? { 'Content-Type': 'application/json' } : undefined,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    })
    const text = await res.text()
    let json: unknown = null
    try { json = text ? JSON.parse(text) : null } catch { /* non-JSON (e.g. proxy error page) */ }
    if (!res.ok) {
      const err = (json as { error?: { code?: string; message?: string; fields?: { field: string; message: string }[] } } | null)?.error
      const detail = err?.fields?.length ? `: ${err.fields.map(f => `${f.field} ${f.message}`).join('; ')}` : ''
      throw new ApiError(res.status, err?.code ?? 'http_error',
        (err?.message ?? (res.status === 502 || res.status === 504 ? 'Backend is not reachable' : `HTTP ${res.status}`)) + detail,
        (err ?? {}) as Record<string, unknown>)
    }
    return json as T
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') throw new ApiError(0, 'timeout', 'The request timed out')
    throw new ApiError(0, 'network', 'Backend is not reachable - is it running on port 8000?')
  } finally {
    clearTimeout(timer)
  }
}

const get = <T>(p: string) => request<T>('GET', p)
const qs = (o: Record<string, string | number | boolean | undefined | null>) => {
  const s = Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
  return s ? `?${s}` : ''
}

/** Streams a question through the pipeline (Server-Sent Events over a POST). */
export async function streamQuery(body: { query: string; document_ids?: number[] | null; model_id?: string | null; conversation_id?: string | null },
  onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
  let res: Response
  try {
    res = await fetch('/api/query/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
  } catch {
    throw new ApiError(0, 'network', 'Backend is not reachable - is it running on port 8000?')
  }
  if (!res.ok || !res.body) {
    let message = `HTTP ${res.status}`
    try { message = (await res.json()).error?.message ?? message } catch { /* ignore */ }
    throw new ApiError(res.status, 'http_error', message)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const line = chunk.split('\n').find(l => l.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)) as StreamEvent)
    }
  }
}

export const api = {
  health: () => get<Health>('/health'),
  overview: (days = 30) => get<Overview>(`/metrics/overview${qs({ days })}`),
  costs: (days = 30) => get<CostReport>(`/metrics/costs${qs({ days })}`),

  documents: () => get<DocumentInfo[]>('/documents'),
  uploadDocuments: (files: File[]) => {
    const fd = new FormData()
    files.forEach(f => fd.append('files', f))
    return request<{ results: UploadResult[] }>('POST', '/documents', fd, 300000)
  },
  updateDocument: (id: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<{ document: DocumentInfo; cache_entries_invalidated: number }>('PUT', `/documents/${id}`, fd, 300000)
  },
  deleteDocument: (id: number) => request<{ deleted: number; cache_entries_invalidated: number }>('DELETE', `/documents/${id}`),
  documentChunks: (id: number, offset = 0) =>
    get<{ total: number; chunks: { index: number; page: number | null; text: string; chars: number; flagged: boolean }[] }>(`/documents/${id}/chunks${qs({ offset, limit: 50 })}`),

  analyze: (query: string, model_id?: string | null) =>
    request<{ analysis: Analysis; routing: Routing | { error: string }; strategy: string }>('POST', '/query/analyze', { query, model_id }),
  history: (conversation_id?: string) => get<QueryResult[]>(`/query/history${qs({ conversation_id, limit: 100 })}`),

  cacheStats: () => get<CacheStats>('/cache/stats'),
  cacheEntries: (p: { search?: string; status?: string; offset?: number }) =>
    get<{ total: number; entries: CacheEntry[] }>(`/cache/entries${qs({ ...p, limit: 50 })}`),
  cacheEntry: (id: number) => get<CacheEntry>(`/cache/entries/${id}`),
  deleteCacheEntry: (id: number) => request<{ deleted: number }>('DELETE', `/cache/entries/${id}`),
  clearCache: () => request<{ deleted: number }>('DELETE', '/cache'),
  thresholdExperiment: () => request<ThresholdExperiment>('POST', '/cache/threshold-experiment', {}, 120000),

  models: () => get<ModelsResponse>('/models'),
  updateModel: (id: string, body: Partial<{ enabled: boolean; tier: string; input_price_per_mtok: number; output_price_per_mtok: number; price_source: string; clear_prices: boolean }>) =>
    request<{ ok: boolean }>('PATCH', `/models/${encodeURIComponent(id)}`, body),
  addModel: (body: { provider: string; model_name: string; tier: string; input_price_per_mtok?: number; output_price_per_mtok?: number; price_source?: string }) =>
    request<{ id: string }>('POST', '/models', body),
  discoverModels: (provider: string) => get<{ provider: string; models: string[] }>(`/models/discover/${provider}`),
  routerDecisions: () => get<RouterDecision[]>('/router/decisions?limit=100'),

  compare: (body: { query: string; model_ids: string[]; document_ids?: number[] | null; reference_answer?: string | null }) =>
    request<Comparison>('POST', '/compare', body, 600000),
  comparisons: () => get<{ id: number; query: string; models: string[]; is_mock: boolean; created_at: string }[]>('/compare'),
  comparison: (id: number) => get<Comparison>(`/compare/${id}`),

  datasets: () => get<Dataset[]>('/benchmarks/datasets'),
  benchmarkRuns: () => get<BenchmarkRun[]>('/benchmarks/runs'),
  benchmarkRun: (id: number) => get<BenchmarkRun>(`/benchmarks/runs/${id}`),
  startBenchmark: (body: { name: string; dataset: string; configs: string[]; threshold?: number | null; confirm_cost?: boolean }) =>
    request<BenchmarkRun>('POST', '/benchmarks/runs', body),
  deleteBenchmark: (id: number) => request<{ deleted: number }>('DELETE', `/benchmarks/runs/${id}`),

  events: (after_id = 0, limit = 100) => get<SystemEvent[]>(`/monitoring/events${qs({ after_id, limit })}`),
  monitoringStats: () => get<MonitoringStats>('/monitoring/stats'),

  settings: () => get<SettingsResponse>('/settings'),
  updateSettings: (body: Partial<RuntimeSettings>) => request<SettingsResponse>('PUT', '/settings', body),
}
