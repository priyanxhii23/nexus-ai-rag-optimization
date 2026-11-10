// Formatting helpers used across pages.
export const pct = (n: number | null | undefined, digits = 1) => (n === null || n === undefined ? '—' : `${(n * 100).toFixed(digits)}%`)
export const ms = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : n >= 1000 ? `${(n / 1000).toFixed(2)} s` : `${Math.round(n)} ms`
export const int = (n: number | null | undefined) => (n === null || n === undefined ? '—' : Math.round(n).toLocaleString())
export function usd(n: number | null | undefined) {
  if (n === null || n === undefined) return '—'
  if (n === 0) return '$0.00'
  if (Math.abs(n) < 0.01) return `$${n.toFixed(5)}`
  return `$${n.toFixed(Math.abs(n) < 10 ? 4 : 2)}`
}
export const sim = (n: number | null | undefined) => (n === null || n === undefined ? '—' : n.toFixed(3))
export const bytes = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`)

export function ago(iso: string | null | undefined) {
  if (!iso) return '—'
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 5) return 'just now'
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}
export const dateTime = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString() : '—')
export const shortModel = (id: string | null | undefined) => (id ? id.split(':').slice(1).join(':') || id : '—')

export const CACHE_LABEL: Record<string, string> = {
  exact_hit: 'Exact hit', semantic_hit: 'Semantic hit', miss: 'Miss', bypass: 'Bypassed', error: 'Error', disabled: 'Disabled',
}
export const COST_LABEL: Record<string, string> = {
  priced: 'estimated', simulated: 'simulated', unpriced: 'unpriced', none: 'no LLM call',
}
