// Typed wrappers around the FastAPI endpoints.

export interface ComponentHealth { status: 'ok' | 'error' | 'pending' | 'not_configured'; detail: string }
export interface Health {
  status: 'ok' | 'degraded'
  app: string
  version: string
  environment: string
  timestamp: string
  uptime_seconds: number
  components: Record<string, ComponentHealth>
  llm_providers: Record<string, boolean>
  mock_mode: boolean
}
export interface ActivityItem { id: number; query_text: string; cache_status: string; total_latency_ms: number; created_at: string }
export interface OverviewMetrics {
  has_data: boolean
  total_queries: number
  cache_hit_rate: number | null
  avg_latency_ms: number | null
  estimated_cost_usd: number
  llm_calls: number
  llm_calls_avoided: number
  recent_activity: ActivityItem[]
}

async function get<T>(path: string, timeoutMs = 8000): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`/api${path}`, { signal: ctrl.signal })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as T
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  health: () => get<Health>('/health'),
  overview: () => get<OverviewMetrics>('/metrics/overview'),
}
