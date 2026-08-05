import { FormEvent, useEffect, useState } from 'react'
import { Eye, FileUp, Loader2, RefreshCw, Send, Upload } from 'lucide-react'
import { JobResponse, MarkdownDocument, getMarkdownDocument, listJobs, listMarkdownDocuments, pollJob, publishMarkdownDocument, renderMarkdownDocument } from '../api/client'

export default function MarkdownPublisher() {
  const [file, setFile] = useState<File | null>(null)
  const [images, setImages] = useState<File[]>([])
  const [cover, setCover] = useState<File | null>(null)
  const [document, setDocument] = useState<MarkdownDocument | null>(null)
  const [recent, setRecent] = useState<MarkdownDocument[]>([])
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [digest, setDigest] = useState('')
  const [thumbMediaId, setThumbMediaId] = useState('')
  const [rendering, setRendering] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadRecent() {
    try { setRecent(await listMarkdownDocuments()) } catch { /* empty history is fine */ }
  }

  useEffect(() => { void loadRecent() }, [])

  useEffect(() => {
    if (!document) return
    void listJobs({ slug: document.document_id, target: 'markdown_publish', limit: 1 }).then(async ([job]) => {
      if (!job || (job.status !== 'pending' && job.status !== 'running')) return
      setPublishing(true)
      const settled = await pollJob(job.job_id, (update) => setStatus(update.progress || '正在上传到微信公众号...'))
      finishPublish(settled)
    }).catch(() => undefined)
  }, [document?.document_id])

  async function render(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setRendering(true); setError(null); setStatus('正在生成公众号 HTML...')
    try {
      const next = await renderMarkdownDocument({ file, images, cover })
      setDocument(next); setTitle(next.title); setStatus('HTML 已生成，可预览或上传到微信公众号草稿箱。')
      await loadRecent()
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); setStatus(null) }
    finally { setRendering(false) }
  }

  function finishPublish(job: JobResponse) {
    setPublishing(false)
    if (job.status === 'succeeded') setStatus('已上传到微信公众号草稿箱。')
    else setError(job.error || '微信公众号上传失败')
  }

  async function publish() {
    if (!document) return
    setPublishing(true); setError(null); setStatus('正在上传到微信公众号...')
    try {
      const job = await publishMarkdownDocument(document.document_id, { title, author: author || undefined, digest: digest || undefined, thumb_media_id: thumbMediaId || undefined })
      const settled = await pollJob(job.job_id, (update) => setStatus(update.progress || '正在上传到微信公众号...'))
      finishPublish(settled)
    } catch (err) { setPublishing(false); setError(err instanceof Error ? err.message : String(err)) }
  }

  async function openRecent(item: MarkdownDocument) {
    setError(null)
    try { const full = await getMarkdownDocument(item.document_id); setDocument(full); setTitle(full.title) }
    catch (err) { setError(err instanceof Error ? err.message : String(err)) }
  }

  return (
    <section className="mx-auto max-w-6xl">
      <div><h1 className="font-serif text-[26px] font-semibold">Markdown 发布到公众号</h1><p className="mt-1 text-sm text-body">上传 Markdown，生成微信兼容 HTML，确认预览后写入公众号草稿箱。</p></div>
      {error ? <div className="mt-4 rounded-lg border border-error-line bg-error-soft p-3 text-sm text-error">{error}</div> : null}
      {status ? <div className="mt-4 rounded-lg border border-line bg-canvas p-3 text-sm text-moss">{status}</div> : null}

      <div className="mt-5 grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <form className="side-panel space-y-3" onSubmit={render}>
            <h2 className="panel-title">1. 上传与排版</h2>
            <label className="block text-sm"><span className="mb-1 block text-body">Markdown 文件</span><input type="file" accept=".md,.markdown,text/markdown" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
            <label className="block text-sm"><span className="mb-1 block text-body">正文本地图片（可选，文件名需与 Markdown 引用一致）</span><input type="file" accept="image/png,image/jpeg,image/gif" multiple onChange={(event) => setImages(Array.from(event.target.files ?? []))} /></label>
            <label className="block text-sm"><span className="mb-1 block text-body">公众号封面（可选）</span><input type="file" accept="image/png,image/jpeg" onChange={(event) => setCover(event.target.files?.[0] ?? null)} /></label>
            <label className="block text-sm"><span className="mb-1 block text-body">主题</span><select className="h-9 w-full rounded-lg border border-line bg-canvas px-3" disabled><option>摸鱼绿（默认）</option></select></label>
            <button className="button-primary h-10 w-full justify-center" disabled={!file || rendering} type="submit">{rendering ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}生成 HTML</button>
          </form>

          <section className="side-panel space-y-3">
            <h2 className="panel-title">2. 上传到 WeChat</h2>
            <input className="h-9 w-full rounded-lg border border-line px-3 text-sm" placeholder="文章标题" value={title} onChange={(event) => setTitle(event.target.value)} />
            <input className="h-9 w-full rounded-lg border border-line px-3 text-sm" placeholder="作者（可选）" value={author} onChange={(event) => setAuthor(event.target.value)} />
            <textarea className="editor min-h-20" placeholder="摘要（可选）" value={digest} onChange={(event) => setDigest(event.target.value)} />
            <input className="h-9 w-full rounded-lg border border-line px-3 text-sm" placeholder="thumb_media_id（有默认封面时可空）" value={thumbMediaId} onChange={(event) => setThumbMediaId(event.target.value)} />
            <button className="button-primary h-10 w-full justify-center" disabled={!document || !title.trim() || publishing} onClick={() => void publish()}>{publishing ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}上传到草稿箱</button>
            <p className="text-xs leading-5 text-body">未上传封面时，会使用环境配置中的 WECHAT_COVER_PATH 或 WECHAT_THUMB_MEDIA_ID。</p>
          </section>

          {recent.length > 0 ? <section className="side-panel"><div className="mb-2 flex items-center justify-between"><h2 className="panel-title">最近生成</h2><button className="icon-button h-7 w-7" onClick={() => void loadRecent()}><RefreshCw size={13} /></button></div><div className="space-y-2">{recent.map((item) => <button key={item.document_id} className="block w-full rounded-lg border border-line p-2 text-left hover:border-moss" onClick={() => void openRecent(item)}><p className="line-clamp-1 text-sm font-medium">{item.title}</p><p className="mt-1 text-xs text-body">{new Date(item.created_at).toLocaleString()}</p></button>)}</div></section> : null}
        </div>

        <section className="min-h-[720px] overflow-hidden rounded-xl border border-line bg-canvas">
          <div className="flex items-center justify-between border-b border-line px-4 py-3"><span className="inline-flex items-center gap-2 text-sm font-medium"><Eye size={16} />HTML 预览</span>{document ? <a className="action-button" href={`/api/publishing/markdown/${document.document_id}/preview`} target="_blank" rel="noreferrer"><Upload size={14} />新窗口打开</a> : null}</div>
          {document?.html ? <iframe title="公众号 HTML 预览" className="h-[680px] w-full border-0 bg-white" srcDoc={document.html} /> : <div className="flex h-[680px] items-center justify-center text-sm text-body">上传 Markdown 后在这里确认排版。</div>}
        </section>
      </div>
    </section>
  )
}
