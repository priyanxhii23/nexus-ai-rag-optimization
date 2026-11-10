import { useCallback, useEffect, useRef, useState } from 'react'

/** Calls `fn` now and then every `intervalMs` (0 = once). Never overlaps requests,
 *  never sets state after unmount, pauses while the browser tab is hidden. */
export function usePolling<T>(fn: () => Promise<T>, intervalMs = 10000, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  const busy = useRef(false)
  const alive = useRef(true)

  useEffect(() => { fnRef.current = fn })

  const refresh = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    try {
      const value = await fnRef.current()
      if (alive.current) { setData(value); setError(null) }
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      busy.current = false
      if (alive.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    alive.current = true
    refresh()
    if (!intervalMs) return () => { alive.current = false }
    const id = setInterval(() => { if (!document.hidden) refresh() }, intervalMs)
    return () => { alive.current = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, intervalMs, ...deps])

  return { data, error, loading, refresh, setData }
}
