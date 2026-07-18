import { useEffect, useMemo, useState } from 'react'
import { Check, Edit3, Eye, FileJson, Loader2, Radio, Save, Send, Sparkles, Wand2 } from 'lucide-react'
import {
  getPaper,
  markPriorWorksReviewed,
  PaperDetail as PaperDetailType,
  pollJob,
  PriorWorksPayload,
  publishWeChat,
  renderBlogHtml,
  startIngest,
  updateMeta,
  updatePriorWorks,
  updateSummary
} from '../api/client'
import MarkdownView from '../components/MarkdownView'
import PriorWorksView from '../components/PriorWorksView'
import ReviewBadge from '../components/ReviewBadge'
import { normalizeQuotes } from '../utils/textFormat'

type Props = {
  slug: string | null
  onChanged: () => void
}

type MetaDraft = {
  title: string
  authorsText: string
  venue: string
  year: string
  arxivId: string
}

function draftFromDetail(detail: PaperDetailType): MetaDraft {
  return {
    title: detail.meta.title,
    authorsText: detail.meta.authors.join(', '),
    venue: detail.meta.venue,
    year: detail.meta.year ? String(detail.meta.year) : '',
    arxivId: detail.meta.arxiv_id
  }
}

export default function PaperDetail({ slug, onChanged }: Props) {
  const [detail, setDetail] = useState<PaperDetailType | null>(null)
  const [summaryDraft, setSummaryDraft] = useState('')
  const [metaDraft, setMetaDraft] = useState<MetaDraft | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [publishHtml, setPublishHtml] = useState('blog.html')
  const [publishing, setPublishing] = useState(false)
  const [htmlProgress, setHtmlProgress] = useState<string | null>(null)
  const [summaryMode, setSummaryMode] = useState<'preview' | 'edit'>('preview')
  const [priorWorksMode, setPriorWorksMode] = useState<'preview' | 'edit'>('preview')
  const [metaMode, setMetaMode] = useState<'preview' | 'edit'>('preview')

  useEffect(() => {
    if (!slug) {
      setDetail(null)
      setSummaryDraft('')
      setMetaDraft(null)
      setSummaryMode('preview')
      setPriorWorksMode('preview')
      setMetaMode('preview')
      return
    }
    setError(null)
    void getPaper(slug)
      .then((paper) => {
        setDetail(paper)
        setSummaryDraft(paper.summary)
        setMetaDraft(draftFromDetail(paper))
        setPublishHtml(paper.meta.blog_html_path || 'blog.html')
        setSummaryMode('preview')
        setPriorWorksMode('preview')
        setMetaMode('preview')
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
  }, [slug])

  const patternLabel = useMemo(() => {
    const pattern = detail?.sci_pattern
    if (!pattern) return ''
    return [pattern.primary_pattern, pattern.primary_pattern_name].filter(Boolean).join(' ')
  }, [detail])

  async function runAction(action: () => Promise<void>) {
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  if (!slug) {
    return (
      <section className="flex min-h-[calc(100vh-112px)] items-center justify-center lg:h-full lg:min-h-0">
        <div className="text-center">
          <FileJson className="mx-auto mb-3 text-moss" size={32} />
          <h1 className="font-serif text-lg font-semibold">Paper detail</h1>
          <p className="mt-1 text-sm text-body">Select a paper from the list.</p>
        </div>
      </section>
    )
  }

  async function saveSummary() {
    if (!detail) return
    const next = await updateSummary(detail.slug, detail.updated_at, summaryDraft)
    setDetail(next)
    setSummaryDraft(next.summary)
    setSummaryMode('preview')
    setStatus('Summary saved')
    onChanged()
  }

  async function reviewMeta() {
    if (!detail || !metaDraft) return
    const next = await updateMeta(detail.slug, detail.updated_at, {
      title: metaDraft.title,
      authors: metaDraft.authorsText
        .split(',')
        .map((author) => author.trim())
        .filter(Boolean),
      abstract: detail.meta.abstract,
      year: metaDraft.year.trim() ? Number(metaDraft.year) : null,
      venue: metaDraft.venue,
      arxiv_id: metaDraft.arxivId,
      tags: detail.meta.tags
    })
    setDetail(next)
    setMetaDraft(draftFromDetail(next))
    setMetaMode('preview')
    setStatus('元信息已更新')
    onChanged()
  }

  async function reviewPriorWorks(payload: PriorWorksPayload) {
    if (!detail) return
    const afterContent = await updatePriorWorks(detail.slug, detail.updated_at, payload)
    const afterReview = await markPriorWorksReviewed(detail.slug, afterContent.updated_at)
    setDetail(afterReview)
    setPriorWorksMode('preview')
    setStatus('前作信息已更新')
    onChanged()
  }

  async function regenerateSummary() {
    if (!detail) return
    const job = await startIngest(detail.slug, ['summary'], true)
    setStatus(job.progress || `Job ${job.status}`)
    const settled = await pollJob(job.job_id, (next) => setStatus(next.progress || `Job ${next.status}`))
    if (settled.status === 'succeeded') {
      const paper = await getPaper(detail.slug)
      setDetail(paper)
      setSummaryDraft(paper.summary)
      onChanged()
    } else {
      setError(settled.error ?? 'Ingest failed')
    }
  }

  async function publish() {
    if (!detail) return
    setPublishing(true)
    try {
      await publishWeChat(detail.slug, {
        html_path: publishHtml,
        title: detail.meta.title || detail.slug
      })
      setStatus('已发布到微信公众号草稿箱')
    } finally {
      setPublishing(false)
    }
  }

  async function generateBlogHtml() {
    if (!detail) return
    setHtmlProgress('正在排版博客 HTML...')
    try {
      const job = await renderBlogHtml(detail.slug)
      const settled = await pollJob(job.job_id, (next) => setHtmlProgress(next.progress || `Job ${next.status}`))
      if (settled.status === 'succeeded') {
        const htmlPath = typeof settled.result?.html_path === 'string' ? settled.result.html_path : ''
        if (htmlPath) setPublishHtml(htmlPath)
        const paper = await getPaper(detail.slug)
        setDetail(paper)
        setStatus('博客 HTML 生成完成')
      } else {
        setError(settled.error ?? 'HTML 生成失败')
      }
    } finally {
      setHtmlProgress(null)
    }
  }

  function confirmAndGenerateBlogHtml() {
    if (!detail) return
    if (detail.meta.blog_html_path) {
      const confirmed = window.confirm(
        `已经生成过 HTML（${detail.meta.blog_html_path}），重新生成大约需要 2-3 分钟，确定要重新生成吗？`
      )
      if (!confirmed) return
    }
    void runAction(generateBlogHtml)
  }

  return (
    <section className="flex min-w-0 flex-col lg:h-full lg:min-h-0">
      {error ? <div className="mb-3 flex-none rounded-lg border border-error-line bg-error-soft p-3 text-sm text-error">{error}</div> : null}
      {status ? <div className="mb-3 flex-none rounded-lg border border-line bg-canvas p-3 text-sm text-moss">{status}</div> : null}
      {!detail ? (
        <div className="flex items-center gap-2 text-sm text-body">
          <Loader2 size={16} className="animate-spin" />
          Loading
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:min-h-0 lg:flex-1 2xl:grid-cols-[minmax(0,1fr)_360px]">
          <article className="min-w-0 lg:h-full lg:min-h-0 lg:overflow-y-auto">
            <div className="mb-4">
              <div className="flex items-start justify-between gap-3">
                {metaMode === 'edit' ? (
                  <input
                    className="w-full rounded-lg border border-line bg-canvas px-2 py-1 font-serif text-[26px] font-semibold leading-tight outline-none focus:border-moss"
                    value={metaDraft?.title ?? ''}
                    onChange={(event) => setMetaDraft((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
                  />
                ) : (
                  <h1 className="font-serif text-[26px] font-semibold leading-tight">{detail.meta.title || detail.slug}</h1>
                )}
                <ReviewBadge reviewed={detail.meta.meta_reviewed} label="元信息" />
              </div>
              {metaMode === 'edit' ? (
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <input
                    className="rounded-lg border border-line bg-canvas px-2 py-1 text-sm outline-none focus:border-moss sm:col-span-2"
                    placeholder="Authors (comma separated)"
                    value={metaDraft?.authorsText ?? ''}
                    onChange={(event) =>
                      setMetaDraft((prev) => (prev ? { ...prev, authorsText: event.target.value } : prev))
                    }
                  />
                  <input
                    className="rounded-lg border border-line bg-canvas px-2 py-1 text-sm outline-none focus:border-moss"
                    placeholder="Venue"
                    value={metaDraft?.venue ?? ''}
                    onChange={(event) => setMetaDraft((prev) => (prev ? { ...prev, venue: event.target.value } : prev))}
                  />
                  <input
                    className="rounded-lg border border-line bg-canvas px-2 py-1 text-sm outline-none focus:border-moss"
                    placeholder="Year"
                    type="number"
                    value={metaDraft?.year ?? ''}
                    onChange={(event) => setMetaDraft((prev) => (prev ? { ...prev, year: event.target.value } : prev))}
                  />
                  <input
                    className="rounded-lg border border-line bg-canvas px-2 py-1 text-sm outline-none focus:border-moss sm:col-span-4"
                    placeholder="arXiv ID"
                    value={metaDraft?.arxivId ?? ''}
                    onChange={(event) =>
                      setMetaDraft((prev) => (prev ? { ...prev, arxivId: event.target.value } : prev))
                    }
                  />
                </div>
              ) : (
                <p className="mt-2 text-sm text-body">
                  {detail.meta.authors.join(', ') || detail.slug}
                  {detail.meta.venue ? ` · ${detail.meta.venue}` : ''}
                  {detail.meta.year ? ` · ${detail.meta.year}` : ''}
                  {detail.meta.arxiv_id ? ` · ${detail.meta.arxiv_id}` : ''}
                </p>
              )}
              <div className="mt-3 flex items-center gap-2">
                <div className="segmented-control compact" aria-label="Meta view mode">
                  <button className={metaMode === 'preview' ? 'is-selected' : ''} onClick={() => setMetaMode('preview')}>
                    <Eye size={14} />
                    Preview
                  </button>
                  <button className={metaMode === 'edit' ? 'is-selected' : ''} onClick={() => setMetaMode('edit')}>
                    <Edit3 size={14} />
                    Edit
                  </button>
                </div>
                {metaMode === 'edit' ? (
                  <button className="action-button" onClick={() => void runAction(reviewMeta)}>
                    <Check size={16} />
                    Review
                  </button>
                ) : null}
              </div>
            </div>
            <div className="toolbar">
              <div className="segmented-control" aria-label="Summary view mode">
                <button
                  className={summaryMode === 'preview' ? 'is-selected' : ''}
                  onClick={() => setSummaryMode('preview')}
                >
                  <Eye size={16} />
                  Preview
                </button>
                <button
                  className={summaryMode === 'edit' ? 'is-selected' : ''}
                  onClick={() => setSummaryMode('edit')}
                >
                  <Edit3 size={16} />
                  Edit
                </button>
              </div>
              {summaryMode === 'edit' ? (
                <button className="action-button" onClick={() => void runAction(saveSummary)}>
                  <Save size={16} />
                  Save summary
                </button>
              ) : null}
              <button className="action-button" onClick={() => void runAction(regenerateSummary)}>
                <Sparkles size={16} />
                Regenerate
              </button>
            </div>
            {summaryMode === 'edit' ? (
              <textarea
                className="editor mt-3 min-h-[640px]"
                value={summaryDraft}
                onChange={(event) => setSummaryDraft(event.target.value)}
              />
            ) : (
              <MarkdownView markdown={summaryDraft} slug={detail.slug} />
            )}
          </article>
          <aside className="space-y-4 lg:h-full lg:min-h-0 lg:overflow-y-auto">
            <section className="side-panel">
              <h2 className="panel-title">Publish</h2>
              <button
                className="action-button mt-3 w-full justify-center"
                disabled={Boolean(htmlProgress)}
                onClick={confirmAndGenerateBlogHtml}
              >
                {htmlProgress ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                {htmlProgress || '生成 HTML'}
              </button>
              {detail.meta.blog_html_generated_at ? (
                <p className="mt-1 text-xs text-body">
                  上次生成：{new Date(detail.meta.blog_html_generated_at).toLocaleString()}
                </p>
              ) : null}
              <div className="mt-3 flex gap-2">
                <input
                  className="h-10 min-w-0 flex-1 rounded-lg border border-line px-3 text-sm outline-none focus:border-moss"
                  value={publishHtml}
                  onChange={(event) => setPublishHtml(event.target.value)}
                />
                <button
                  className="icon-button"
                  title={detail.meta.blog_html_generated_at ? 'Publish WeChat draft' : '请先生成 HTML'}
                  disabled={!detail.meta.blog_html_generated_at || publishing}
                  onClick={() => void runAction(publish)}
                >
                  {publishing ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                </button>
              </div>
              {publishing ? (
                <p className="mt-1 text-xs text-body">正在发布到微信公众号草稿箱...</p>
              ) : !detail.meta.blog_html_generated_at ? (
                <p className="mt-1 text-xs text-muted">请先点击"生成 HTML"，再发布</p>
              ) : null}
            </section>
            <section className="side-panel">
              <h2 className="panel-title">Pattern</h2>
              <div className="mt-2 inline-flex items-center gap-2 rounded-lg border border-line bg-fog px-2 py-1 text-sm">
                <Radio size={14} className="text-copper" />
                {patternLabel || 'Unclassified'}
              </div>
              <p className="mt-3 text-sm leading-6 text-body">
                {normalizeQuotes(String(detail.sci_pattern?.reasoning ?? ''))}
              </p>
            </section>
            <PriorWorksView
              value={detail.prior_works}
              mode={priorWorksMode}
              reviewed={detail.meta.prior_works_reviewed}
              onModeChange={setPriorWorksMode}
              onSave={(payload) => void runAction(() => reviewPriorWorks(payload))}
            />
          </aside>
        </div>
      )}
    </section>
  )
}
