import { Fragment, type ReactNode } from 'react'

/** Minimal, safe renderer for model answers: paragraphs, bullet lists, **bold**, `code`
 *  and [n] citation chips. Never injects HTML. */
function inline(text: string, onCite?: (n: number) => void): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g)
  return parts.map((p, i) => {
    if (/^\*\*[^*]+\*\*$/.test(p)) return <strong key={i}>{p.slice(2, -2)}</strong>
    if (/^`[^`]+`$/.test(p)) return <code key={i}>{p.slice(1, -1)}</code>
    const m = p.match(/^\[(\d+)\]$/)
    if (m) return (
      <button key={i} type="button" onClick={() => onCite?.(Number(m[1]))}
        className="mx-0.5 inline-flex h-4 min-w-4 -translate-y-px items-center justify-center rounded bg-accent-soft px-1 align-middle text-[10px] font-semibold text-accent hover:brightness-95"
        title={`Source ${m[1]}`}>{m[1]}</button>
    )
    return <Fragment key={i}>{p}</Fragment>
  })
}

export function AnswerText({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  const blocks = text.split(/\n{2,}/)
  return (
    <div className="answer text-sm leading-relaxed text-fg">
      {blocks.map((b, i) => {
        const lines = b.split('\n').filter(Boolean)
        if (lines.length && lines.every(l => /^\s*([-*•]|\d+\.)\s+/.test(l))) {
          return <ul key={i}>{lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*([-*•]|\d+\.)\s+/, ''), onCite)}</li>)}</ul>
        }
        return <p key={i}>{lines.map((l, j) => <Fragment key={j}>{j > 0 && <br />}{inline(l, onCite)}</Fragment>)}</p>
      })}
    </div>
  )
}
