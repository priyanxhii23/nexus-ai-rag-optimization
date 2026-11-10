import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Copy, Eye, FileText, RefreshCw, ShieldAlert, Trash2, UploadCloud, XCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { stagger } from '../animations/variants'
import { Alert, Badge, Button, Card, EmptyState, Modal, PageHeader, SectionNote, Skeleton, Table } from '../components/ui'
import { usePolling } from '../hooks/usePolling'
import { api, type DocumentInfo, type UploadResult } from '../services/api'
import { ago, bytes, int } from '../services/format'

export default function Documents() {
  const docs = usePolling(api.documents, 0)
  const [results, setResults] = useState<UploadResult[]>([])
  const [uploading, setUploading] = useState(false)
  const [drag, setDrag] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [viewing, setViewing] = useState<DocumentInfo | null>(null)
  const [deleting, setDeleting] = useState<DocumentInfo | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const replaceRef = useRef<HTMLInputElement>(null)
  const replaceTarget = useRef<DocumentInfo | null>(null)

  async function upload(files: File[]) {
    if (!files.length) return
    setUploading(true); setError(null); setNotice(null)
    try {
      const r = await api.uploadDocuments(files)
      setResults(r.results)
      docs.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed') } finally { setUploading(false) }
  }

  async function replace(file: File) {
    const target = replaceTarget.current
    if (!target) return
    setBusyId(target.id); setError(null); setNotice(null)
    try {
      const r = await api.updateDocument(target.id, file)
      setNotice(`'${target.filename}' is now version ${r.document.version}. ${r.cache_entries_invalidated} cached answer(s) based on the old version were invalidated.`)
      docs.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Update failed') } finally { setBusyId(null) }
  }

  async function remove(d: DocumentInfo) {
    setBusyId(d.id); setError(null); setNotice(null)
    try {
      const r = await api.deleteDocument(d.id)
      setNotice(`'${d.filename}' deleted with its vectors. ${r.cache_entries_invalidated} cached answer(s) invalidated.`)
      setDeleting(null)
      docs.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Delete failed') } finally { setBusyId(null) }
  }

  const list = docs.data ?? []
  const totalChunks = list.reduce((a, d) => a + d.chunk_count, 0)

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
      <PageHeader title="Document Library" description="Upload PDF, TXT or Markdown files. Each file is split into chunks, embedded with all-MiniLM-L6-v2 and stored in ChromaDB."
        actions={<Button variant="primary" icon={UploadCloud} onClick={() => fileRef.current?.click()} loading={uploading}>Upload files</Button>} />
      <input ref={fileRef} type="file" multiple accept=".pdf,.txt,.md" hidden onChange={e => { upload(Array.from(e.target.files ?? [])); e.target.value = '' }} />
      <input ref={replaceRef} type="file" accept=".pdf,.txt,.md" hidden onChange={e => { const f = e.target.files?.[0]; if (f) replace(f); e.target.value = '' }} />

      {error && <Alert>{error}</Alert>}
      {notice && <Alert tone="info">{notice}</Alert>}

      <motion.div
        onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); upload(Array.from(e.dataTransfer.files)) }}
        onClick={() => fileRef.current?.click()} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && fileRef.current?.click()}
        animate={{ scale: drag ? 1.01 : 1 }}
        className={`focus-ring flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-line-strong'}`}>
        <div className="grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent">
          {uploading ? <RefreshCw size={20} className="animate-spin" /> : <UploadCloud size={20} />}
        </div>
        <p className="text-sm font-medium">{uploading ? 'Extracting, chunking and embedding…' : 'Drop files here or click to browse'}</p>
        <p className="text-xs text-muted">PDF, TXT, MD · up to 20 files at once · size limit set in .env (MAX_UPLOAD_MB)</p>
      </motion.div>

      <AnimatePresence>
        {results.length > 0 && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
            <Card title="Upload results" action={<Button size="sm" variant="ghost" onClick={() => setResults([])}>Dismiss</Button>}>
              <ul className="space-y-2">
                {results.map((r, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm">
                    {r.status === 'created' ? <CheckCircle2 size={16} className="mt-0.5 text-ok" /> : r.status === 'duplicate' ? <Copy size={16} className="mt-0.5 text-warn" /> : <XCircle size={16} className="mt-0.5 text-err" />}
                    <div className="min-w-0">
                      <p className="truncate font-medium">{r.filename}</p>
                      <p className="text-xs text-muted">
                        {r.status === 'created' && r.document ? `Indexed ${r.document.chunk_count} chunks${r.document.page_count ? ` from ${r.document.page_count} pages` : ''}.` : r.message}
                        {r.document?.flagged_chunks ? ` ${r.document.flagged_chunks} chunk(s) contain instruction-like text and will be treated strictly as data.` : ''}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      <Card title="Documents" subtitle={list.length ? `${list.length} document${list.length > 1 ? 's' : ''} · ${int(totalChunks)} chunks indexed` : undefined}>
        {docs.loading ? <div className="space-y-2"><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : docs.error ? <Alert>{docs.error}</Alert> : (
          <Table head={['Name', 'Version', 'Chunks', 'Size', 'Status', 'Updated', '']}
            empty={!list.length && <div className="pt-3"><EmptyState icon={<FileText size={18} />} title="No documents yet" body="Upload a PDF or TXT file to start asking questions about it." /></div>}>
            {list.map(d => (
              <tr key={d.id} className="group">
                <td className="max-w-64 py-2.5 pr-4">
                  <div className="flex items-center gap-2">
                    <FileText size={15} className="shrink-0 text-faint" />
                    <span className="truncate font-medium" title={d.filename}>{d.filename}</span>
                    {d.flagged_chunks > 0 && <span title={`${d.flagged_chunks} chunk(s) look like prompt-injection attempts; they are wrapped as untrusted data`}><ShieldAlert size={14} className="text-warn" /></span>}
                  </div>
                  <p className="pl-6 text-[11px] uppercase text-faint">{d.file_type}{d.page_count ? ` · ${d.page_count} pages` : ''} · #{d.content_hash}</p>
                </td>
                <td className="py-2.5 pr-4 tabular">v{d.version}</td>
                <td className="py-2.5 pr-4 tabular">{d.chunk_count}</td>
                <td className="py-2.5 pr-4 tabular text-muted">{bytes(d.size_bytes)}</td>
                <td className="py-2.5 pr-4">{d.status === 'indexed' ? <Badge tone="ok">indexed</Badge> : d.status === 'failed' ? <Badge tone="err">failed</Badge> : <Badge tone="warn">{d.status}</Badge>}</td>
                <td className="whitespace-nowrap py-2.5 pr-4 text-muted">{ago(d.updated_at)}</td>
                <td className="py-2.5">
                  <div className="flex justify-end gap-1">
                    <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(d)} aria-label={`View chunks of ${d.filename}`}>Chunks</Button>
                    <Button size="sm" variant="ghost" icon={RefreshCw} loading={busyId === d.id} onClick={() => { replaceTarget.current = d; replaceRef.current?.click() }} aria-label={`Replace ${d.filename}`}>Replace</Button>
                    <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setDeleting(d)} aria-label={`Delete ${d.filename}`} className="hover:text-err" />
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
        <div className="mt-4"><SectionNote>Uploading identical content again is detected (SHA-256) and skipped. “Replace” creates a new version and invalidates every cached answer that used the old one. Document text is never written to the logs.</SectionNote></div>
      </Card>

      <ChunksModal doc={viewing} onClose={() => setViewing(null)} />
      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Delete document?">
        <div className="space-y-4 text-sm">
          <p className="flex items-start gap-2 text-muted"><AlertTriangle size={16} className="mt-0.5 shrink-0 text-warn" />
            “{deleting?.filename}”, its {deleting?.chunk_count} chunk vectors and the stored file will be removed. Cached answers that used it will be invalidated. This cannot be undone.</p>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setDeleting(null)}>Cancel</Button>
            <Button variant="danger" icon={Trash2} loading={busyId === deleting?.id} onClick={() => deleting && remove(deleting)}>Delete</Button>
          </div>
        </div>
      </Modal>
    </motion.div>
  )
}

function ChunksModal({ doc, onClose }: { doc: DocumentInfo | null; onClose: () => void }) {
  const chunks = usePolling(() => (doc ? api.documentChunks(doc.id) : Promise.resolve(null)), 0, [doc?.id])
  return (
    <Modal open={!!doc} onClose={onClose} title={doc ? `${doc.filename} · v${doc.version}` : ''} wide>
      {chunks.loading ? <Skeleton className="h-24" /> : chunks.error ? <Alert>{chunks.error}</Alert> : chunks.data && (
        <div className="space-y-2.5">
          <p className="text-xs text-muted">{chunks.data.total} chunks{chunks.data.total > 50 ? ' (first 50 shown)' : ''}. Each chunk is embedded separately; retrieval returns the most similar chunks.</p>
          {chunks.data.chunks.map(c => (
            <div key={c.index} className="rounded-xl border border-line p-3">
              <p className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-faint">
                <span className="font-semibold text-muted">Chunk {c.index + 1}</span>{c.page && <span>page {c.page}</span>}<span>{c.chars} chars</span>
                {c.flagged && <Badge tone="warn"><ShieldAlert size={11} />instruction-like text</Badge>}
              </p>
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-fg">{c.text}</p>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
