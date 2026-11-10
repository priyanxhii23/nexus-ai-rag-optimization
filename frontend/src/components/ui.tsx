import { AnimatePresence, animate, motion, useReducedMotion } from 'framer-motion'
import { AlertTriangle, FlaskConical, Info, Loader2, X } from 'lucide-react'
import { useEffect, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { rise } from '../animations/variants'

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

export function Card({ title, subtitle, action, children, className = '', bodyClass = '' }: {
  title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; bodyClass?: string
}) {
  return (
    <motion.section variants={rise} className={cx('card min-w-0', className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4">
          <div className="min-w-0">
            {title && <h2 className="text-[13px] font-semibold tracking-tight text-fg">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
        </header>
      )}
      <div className={cx('p-5', title || action ? 'pt-4' : '', bodyClass)}>{children}</div>
    </motion.section>
  )
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <motion.div variants={rise} className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </motion.div>
  )
}

/** Number that counts up when it first appears / changes. Respects reduced motion. */
export function AnimatedNumber({ value, format }: { value: number; format: (n: number) => string }) {
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(0)
  const from = useRef(0)
  useEffect(() => {
    if (reduce) return
    const controls = animate(from.current, value, { duration: 0.8, ease: [0.22, 1, 0.36, 1], onUpdate: v => setShown(v) })
    from.current = value
    return () => controls.stop()
  }, [value, reduce])
  return <>{format(reduce ? value : shown)}</>
}

export function Kpi({ label, value, format, icon: Icon, hint, tone, loading }: {
  label: string; value: number | null | undefined; format: (n: number) => string; icon?: React.ElementType
  hint?: ReactNode; tone?: 'accent' | 'ok' | 'warn'; loading?: boolean
}) {
  return (
    <motion.div variants={rise} className="card group relative overflow-hidden p-4 transition-colors hover:border-line-strong">
      <div className="flex items-center justify-between text-muted">
        <span className="text-xs font-medium">{label}</span>
        {Icon && <Icon size={14} className={tone === 'accent' ? 'text-accent' : tone === 'ok' ? 'text-ok' : undefined} />}
      </div>
      <div className="mt-2.5 text-[22px] font-semibold leading-none tracking-tight tabular">
        {loading ? <Skeleton className="h-6 w-20" /> : value === null || value === undefined
          ? <span className="text-faint">—</span> : <AnimatedNumber value={value} format={format} />}
      </div>
      {hint && <div className="mt-2 truncate text-[11px] text-faint">{hint}</div>}
    </motion.div>
  )
}

export type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'err' | 'cyan'
const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-muted ring-line',
  accent: 'bg-accent-soft text-accent ring-accent/20',
  ok: 'bg-ok/10 text-ok ring-ok/20',
  warn: 'bg-warn/10 text-warn ring-warn/25',
  err: 'bg-err/10 text-err ring-err/20',
  cyan: 'bg-cyan/10 text-cyan ring-cyan/20',
}
export function Badge({ children, tone = 'neutral', className = '', title }: { children: ReactNode; tone?: Tone; className?: string; title?: string }) {
  return <span title={title} className={cx('inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset', TONES[tone], className)}>{children}</span>
}

export function CacheBadge({ status }: { status: string | null | undefined }) {
  const map: Record<string, [Tone, string]> = {
    exact_hit: ['ok', 'Exact hit'], semantic_hit: ['cyan', 'Semantic hit'], miss: ['neutral', 'Miss'],
    bypass: ['neutral', 'Bypassed'], error: ['err', 'Error'],
  }
  const [tone, label] = map[status ?? ''] ?? ['neutral', status ?? '—']
  return <Badge tone={tone}>{label}</Badge>
}

export function MockBadge() {
  return <Badge tone="warn" title="Produced by the mock provider in test mode - not real LLM output"><FlaskConical size={11} />Test mode</Badge>
}

export function StatusDot({ status }: { status: string }) {
  const color = { ok: 'bg-ok', error: 'bg-err', offline: 'bg-err', degraded: 'bg-warn', pending: 'bg-warn', loading: 'bg-warn', not_configured: 'bg-faint' }[status] ?? 'bg-faint'
  return (
    <span className="relative inline-flex h-2 w-2 shrink-0" aria-hidden>
      {status === 'ok' && <span className={`absolute inset-0 animate-ping rounded-full opacity-40 motion-reduce:hidden ${color}`} />}
      <span className={`relative h-2 w-2 rounded-full ${color}`} />
    </span>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={cx('animate-pulse rounded-md bg-surface-2', className)} />
}

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line px-6 py-8 text-center">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-surface-2 text-muted">{icon}</div>
      <p className="text-sm font-medium text-fg">{title}</p>
      <p className="max-w-sm text-xs leading-relaxed text-muted">{body}</p>
      {action && <div className="pt-2">{action}</div>}
    </div>
  )
}

export function Alert({ tone = 'err', children, title }: { tone?: 'err' | 'warn' | 'info'; title?: string; children: ReactNode }) {
  const styles = { err: 'border-err/30 bg-err/8 text-err', warn: 'border-warn/30 bg-warn/8 text-warn', info: 'border-accent/25 bg-accent-soft text-accent' }[tone]
  const Icon = tone === 'info' ? Info : AlertTriangle
  return (
    <motion.div role={tone === 'err' ? 'alert' : 'status'} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
      className={cx('flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm', styles)}>
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0">{title && <p className="font-medium">{title}</p>}<div className={title ? 'mt-0.5 opacity-90' : ''}>{children}</div></div>
    </motion.div>
  )
}

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export function Button({ variant = 'secondary', size = 'md', loading, icon: Icon, children, className = '', ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: 'sm' | 'md'; loading?: boolean; icon?: React.ElementType }) {
  const v = {
    primary: 'bg-accent text-accent-contrast hover:brightness-110 shadow-sm',
    secondary: 'border border-line bg-surface text-fg hover:bg-surface-2',
    ghost: 'text-muted hover:bg-surface-2 hover:text-fg',
    danger: 'border border-err/30 text-err hover:bg-err/10',
  }[variant]
  const s = size === 'sm' ? 'h-8 px-2.5 text-xs gap-1.5' : 'h-9 px-3.5 text-sm gap-2'
  return (
    <button {...rest} disabled={rest.disabled || loading}
      className={cx('focus-ring inline-flex items-center justify-center rounded-lg font-medium transition-all active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50', v, s, className)}>
      {loading ? <Loader2 size={size === 'sm' ? 13 : 15} className="animate-spin" /> : Icon && <Icon size={size === 'sm' ? 13 : 15} />}
      {children}
    </button>
  )
}

const field = 'focus-ring rounded-lg border border-line bg-surface px-3 text-sm text-fg placeholder:text-faint transition-colors hover:border-line-strong'
// full width unless the caller sets its own width (w-*)
const width = (c?: string) => (c && /(^|\s)w-/.test(c) ? '' : 'w-full')
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(field, width(props.className), 'h-9', props.className)} />
}
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(field, width(props.className), 'py-2 leading-relaxed', props.className)} />
}
export function Select({ children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(field, width(props.className), 'h-9 pr-8', props.className)}>{children}</select>
}
export function Label({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return <span className="mb-1.5 flex items-center justify-between text-xs font-medium text-muted">{children}{hint && <span className="font-normal text-faint">{hint}</span>}</span>
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)}
      className={cx('focus-ring relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-50', checked ? 'bg-accent' : 'bg-surface-3')}>
      <motion.span layout transition={{ type: 'spring', stiffness: 600, damping: 35 }}
        className={cx('h-4 w-4 rounded-full bg-white shadow', checked ? 'ml-[18px]' : 'ml-0.5')} />
    </button>
  )
}

export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
      {options.map(o => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={cx('focus-ring relative rounded-md px-2.5 py-1 text-xs font-medium transition-colors', value === o.value ? 'text-fg' : 'text-muted hover:text-fg')}>
          {value === o.value && <motion.span layoutId={`seg-${label}`} className="absolute inset-0 rounded-md bg-surface shadow-sm ring-1 ring-line" transition={{ type: 'spring', stiffness: 500, damping: 40 }} />}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  )
}

export function Progress({ value, className = '' }: { value: number; className?: string }) {
  return (
    <div className={cx('h-1.5 overflow-hidden rounded-full bg-surface-2', className)} role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <motion.div className="h-full rounded-full bg-gradient-to-r from-accent to-cyan" initial={{ width: 0 }} animate={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} transition={{ ease: 'easeOut', duration: 0.5 }} />
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={onClose} />
          <motion.div role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : undefined}
            initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 420, damping: 34 }}
            className={cx('card relative flex max-h-[90vh] w-full flex-col overflow-hidden rounded-b-none sm:rounded-b-[14px]', wide ? 'sm:max-w-3xl' : 'sm:max-w-lg')}>
            <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3.5">
              <h2 className="min-w-0 truncate text-sm font-semibold">{title}</h2>
              <button onClick={onClose} aria-label="Close" className="focus-ring rounded-md p-1 text-muted hover:bg-surface-2 hover:text-fg"><X size={16} /></button>
            </header>
            <div className="scrollbar-thin overflow-y-auto p-5">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function KeyValue({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-5 gap-y-1.5 text-xs">
      {items.map(([k, v], i) => (<div key={i} className="contents"><dt className="text-muted">{k}</dt><dd className="min-w-0 break-words text-fg tabular">{v}</dd></div>))}
    </dl>
  )
}

export function Table({ head, children, empty }: { head: ReactNode[]; children: ReactNode; empty?: ReactNode }) {
  return (
    <div className="scrollbar-thin -mx-5 overflow-x-auto px-5">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead><tr className="border-b border-line text-[11px] uppercase tracking-wide text-faint">{head.map((h, i) => <th key={i} className="whitespace-nowrap py-2 pr-4 font-medium">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
      {empty}
    </div>
  )
}

export function SectionNote({ children }: { children: ReactNode }) {
  return <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-faint"><Info size={12} className="mt-0.5 shrink-0" />{children}</p>
}
