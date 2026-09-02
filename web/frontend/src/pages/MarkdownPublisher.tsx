import { FormEvent, useEffect, useState } from 'react'
import { Eye, FileUp, Loader2, RefreshCw, Send, Upload } from 'lucide-react'
import {
  JobResponse,
  MarkdownDocument,
  getMarkdownDocument,
  listJobs,
  listMarkdownDocuments,
  pollJob,
  publishMarkdownDocument,
  renderMarkdownDocument
} from '../api/client'
import FileField, { Field } from '../components/FileField'

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
    try {
      setRecent(await listMarkdownDocuments())
    } catch {
      /* empty history is fine */
    }
  }

  useEffect(() => {
    void loadRecent()
  }, [])

  useEffect(() => {
    if (!document) return
    void listJobs({ slug: document.document_id, target: 'markdown_publish', limit: 1 })
      .then(async ([job]) => {
        if (!job || (job.status !== 'pending' && job.status !== 'running')) return
        setPublishing(true)
        const settled = await pollJob(job.job_id, (update) => setStatus(update.progress || '正在上传到微信公众号...'))
        finishPublish(settled)
      })
      .catch(() => undefined)
  }, [document?.document_id])

  async function render(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setRendering(true)
    setError(null)
    setStatus('正在生成公众号 HTML...')
    try {
      const next = await renderMarkdownDocument({ file, images, cover })
      setDocument(next)
      setTitle(next.title)
      setStatus('HTML 已生成，可预览或上传到微信公众号草稿箱。')
      await loadRecent()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus(null)
    } finally {
      setRendering(false)
    }
  }

  function finishPublish(job: JobResponse) {
    setPublishing(false)
    if (job.status === 'succeeded') setStatus('已上传到微信公众号草稿箱。')
    else setError(job.error || '微信公众号上传失败')
  }

  async function publish() {
    if (!document) return
    setPublishing(true)
    setError(null)
    setStatus('正在上传到微信公众号...')
    try {
      const job = await publishMarkdownDocument(document.document_id, {
        title: title.trim() || undefined,
        author: author || undefined,
        digest: digest || undefined,
        thumb_media_id: thumbMediaId || undefined
      })
      const settled = await pollJob(job.job_id, (update) => setStatus(update.progress || '正在上传到微信公众号...'))
      finishPublish(settled)
    } catch (err) {
      setPublishing(false)
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function openRecent(item: MarkdownDocument) {
    setError(null)
    try {
      const full = await getMarkdownDocument(item.document_id)
      setDocument(full)
      setTitle(full.title)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <section className="mx-auto max-w-6xl animate-fade-up">
      <div>
        <p className="page-kicker">Publish</p>
        <h1 className="page-title mt-1">Markdown 发布到公众号</h1>
        <p className="page-subtitle">上传 Markdown，生成微信兼容 HTML，确认预览后写入公众号草稿箱。</p>
      </div>
      {error ? <div className="alert-error mt-4">{error}</div> : null}
      {status ? <div className="alert-success mt-4">{status}</div> : null}

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
        <div className="space-y-4">
          <form className="side-panel space-y-4" onSubmit={render}>
            <h2 className="panel-title">1. 上传与排版</h2>
            <FileField
              label="Markdown 文件"
              accept=".md,.markdown,text/markdown"
              required
              files={file ? [file] : []}
              onChange={(next) => setFile(next[0] ?? null)}
              emptyLabel="选择 .md 文件"
              icon="file"
            />
            <FileField
              label="正文本地图片"
              hint="可选。文件名需与 Markdown 中的图片引用一致。"
              accept="image/png,image/jpeg,image/gif"
              multiple
              files={images}
              onChange={setImages}
              emptyLabel="添加正文图片"
              icon="image"
            />
            <FileField
              label="公众号封面"
              hint="可选。不上传则按标题自动生成纯色封面。"
              accept="image/png,image/jpeg"
              files={cover ? [cover] : []}
              onChange={(next) => setCover(next[0] ?? null)}
              emptyLabel="选择封面图"
              icon="image"
            />
            <Field label="主题" hint="当前仅支持摸鱼绿。">
              <div className="field-select-trigger cursor-default opacity-90">
                <span>摸鱼绿（默认）</span>
              </div>
            </Field>
            <button className="button-primary h-11 w-full justify-center" disabled={!file || rendering} type="submit">
              {rendering ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
              生成 HTML
            </button>
          </form>

          <section className="side-panel space-y-3">
            <h2 className="panel-title">2. 上传到 WeChat</h2>
            <Field label="文章标题" hint="默认取自 Markdown 标题；留空时发布仍会回退到文档标题。">
              <input
                className="field-input"
                placeholder="默认使用文档标题"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </Field>
            <Field label="作者">
              <input
                className="field-input"
                placeholder="可选"
                value={author}
                onChange={(event) => setAuthor(event.target.value)}
              />
            </Field>
            <Field label="摘要">
              <textarea
                className="field-textarea min-h-20"
                placeholder="可选"
                value={digest}
                onChange={(event) => setDigest(event.target.value)}
              />
            </Field>
            <Field label="thumb_media_id" hint="可留空；未填且未上传封面时会自动生成标题封面。">
              <input
                className="field-input font-mono text-xs"
                placeholder="可选"
                value={thumbMediaId}
                onChange={(event) => setThumbMediaId(event.target.value)}
              />
            </Field>
            <button
              className="button-primary h-11 w-full justify-center"
              disabled={!document || publishing}
              onClick={() => void publish()}
            >
              {publishing ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              上传到草稿箱
            </button>
          </section>

          {recent.length > 0 ? (
            <section className="side-panel">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="panel-title">最近生成</h2>
                <button className="icon-button h-7 w-7" onClick={() => void loadRecent()} title="刷新">
                  <RefreshCw size={13} />
                </button>
              </div>
              <div className="space-y-2">
                {recent.map((item) => (
                  <button
                    key={item.document_id}
                    className="block w-full rounded-lg border border-line bg-fog/40 p-3 text-left transition hover:border-moss/40 hover:bg-canvas hover:shadow-soft"
                    onClick={() => void openRecent(item)}
                  >
                    <p className="line-clamp-1 text-sm font-medium">{item.title}</p>
                    <p className="mt-1 text-xs text-body">{new Date(item.created_at).toLocaleString()}</p>
                  </button>
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <section className="min-h-[720px] overflow-hidden rounded-xl border border-line bg-canvas shadow-soft">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <span className="inline-flex items-center gap-2 text-sm font-medium">
              <Eye size={16} className="text-moss" />
              HTML 预览
            </span>
            {document ? (
              <a
                className="action-button"
                href={`/api/publishing/markdown/${document.document_id}/preview`}
                target="_blank"
                rel="noreferrer"
              >
                <Upload size={14} />
                新窗口打开
              </a>
            ) : null}
          </div>
          {document?.html ? (
            <iframe title="公众号 HTML 预览" className="h-[680px] w-full border-0 bg-white" srcDoc={document.html} />
          ) : (
            <div className="flex h-[680px] flex-col items-center justify-center gap-2 px-8 text-center">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl border border-line bg-fog text-muted">
                <Eye size={20} />
              </div>
              <p className="text-sm font-medium text-ink">还没有预览</p>
              <p className="max-w-xs text-sm text-body">上传 Markdown 并生成 HTML 后，排版结果会显示在这里。</p>
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
