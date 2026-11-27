import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpen,
  Check,
  ChevronRight,
  Edit3,
  ExternalLink,
  List,
  Maximize2,
  Minimize2,
  RefreshCw,
  Save,
  Send,
  ShieldCheck,
  Sparkles,
  X
} from 'lucide-react'
import {
  getPaper,
  listJobs,
  markMetaReviewed,
  markPriorWorksReviewed,
  PaperDetail as Detail,
  PaperMetaEdits,
  pollJob,
  PriorWorksPayload,
  startIngest,
  updateMeta,
  updatePriorWorks,
  updateSummary
} from '../api/client'
import MarkdownView from '../components/MarkdownView'
import PriorWorksView from '../components/PriorWorksView'
import Dialog from '../components/Dialog'
import {
  useNavigationGuard,
  useUnsavedChanges
} from '../context/NavigationGuard'
import useScrollMemory from '../hooks/useScrollMemory'
import {
  contentFingerprint,
  readingHeadings,
  readingMarkdown
} from '../utils/reading'
import { readStored, writeStored } from '../utils/storage'
type Props = {
  slug: string | null
  refreshKey?: number
  onChanged: () => void
  onOpenPublish?: (slug: string) => void
}
type Drafts = {
  summary: string
  meta: PaperMetaEdits
  prior: PriorWorksPayload | null
}
const initialDrafts = (paper: Detail): Drafts => ({
  summary: paper.summary,
  meta: {
    title: paper.meta.title,
    authors: paper.meta.authors,
    abstract: paper.meta.abstract,
    year: paper.meta.year,
    venue: paper.meta.venue,
    arxiv_id: paper.meta.arxiv_id,
    tags: paper.meta.tags
  },
  prior: paper.prior_works
})
export default function PaperDetail(props: Props) {
  if (!props.slug)
    return (
      <div className="reader-welcome">
        <div className="reader-welcome-icon">
          <BookOpen size={30} strokeWidth={1.2} />
        </div>
        <p className="eyebrow">A SPACE TO THINK</p>
        <h2>留一点时间，认真读。</h2>
        <p>选择一篇论文，开始阅读、整理与核验。</p>
        <span>精读笔记 · 前作分析 · 创新范式</span>
      </div>
    )
  return (
    <PaperReader
      key={`${props.slug}.${props.refreshKey || 0}`}
      {...props}
      slug={props.slug}
    />
  )
}
function PaperReader({
  slug,
  onChanged,
  onOpenPublish
}: Props & { slug: string }) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [drafts, setDrafts] = useState<Drafts | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [summaryEditing, setSummaryEditing] = useState(false)
  const [metaEditing, setMetaEditing] = useState(false)
  const [priorEditing, setPriorEditing] = useState(false)
  const [inspector, setInspector] = useState<
    'outline' | 'analysis' | 'review' | null
  >(null)
  const [focused, setFocused] = useState(false)
  const [regenerateConfirm, setRegenerateConfirm] = useState(false)
  const [loadVersion, setLoadVersion] = useState(0)
  const reader = useRef<HTMLDivElement>(null)
  const mounted = useRef(true)
  const actionLock = useRef(false)
  const state = useRef({ detail, drafts })
  state.current = { detail, drafts }
  const { request } = useNavigationGuard()
  const dirty = Boolean(
    detail &&
    drafts &&
    JSON.stringify(initialDrafts(detail)) !== JSON.stringify(drafts)
  )
  useEffect(() => {
    let cancelled = false
    mounted.current = true
    setLoading(true)
    setError('')
    void getPaper(slug)
      .then((paper) => {
        if (cancelled) return
        setDetail(paper)
        const recovered = readStored<{
          version: string
          drafts: Drafts
        } | null>(`paper-wiki.draft.${slug}`, null, true)
        if (recovered && recovered.version === paper.updated_at) {
          setDrafts(recovered.drafts)
          setSummaryEditing(recovered.drafts.summary !== paper.summary)
          if (
            JSON.stringify(recovered.drafts.prior) !==
            JSON.stringify(paper.prior_works)
          ) {
            setInspector('analysis')
            setPriorEditing(true)
          } else if (
            JSON.stringify(recovered.drafts.meta) !==
            JSON.stringify(initialDrafts(paper).meta)
          ) {
            setInspector('review')
            setMetaEditing(true)
          }
          setNotice('已恢复这篇论文的未保存草稿。')
        } else {
          setDrafts(initialDrafts(paper))
          if (recovered)
            setNotice('检测到旧版草稿。可先下载草稿备份，再根据最新内容编辑。')
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      mounted.current = false
    }
  }, [slug, loadVersion])
  useEffect(() => {
    if (dirty && detail && drafts)
      writeStored(
        `paper-wiki.draft.${slug}`,
        { version: detail.updated_at, drafts },
        true
      )
  }, [slug, dirty, detail, drafts])
  const accept = useCallback((next: Detail) => {
    if (mounted.current) setDetail(next)
    state.current.detail = next
  }, [])
  const discard = useCallback(() => {
    const current = state.current.detail
    if (current) {
      const next = initialDrafts(current)
      setDrafts(next)
      state.current.drafts = next
    }
    try {
      sessionStorage.removeItem(`paper-wiki.draft.${slug}`)
    } catch {
      /* optional storage */
    }
    setSummaryEditing(false)
    setMetaEditing(false)
    setPriorEditing(false)
  }, [slug])
  const save = useCallback(async () => {
    if (actionLock.current) throw new Error('操作进行中，请稍后再保存')
    let { detail: paper, drafts: current } = state.current
    if (!paper || !current) throw new Error('论文尚未加载')
    if (!current.meta.title.trim()) throw new Error('论文标题不能为空')
    if (
      current.meta.year !== null &&
      (!Number.isInteger(current.meta.year) ||
        current.meta.year < 1900 ||
        current.meta.year > new Date().getFullYear() + 1)
    )
      throw new Error('请输入有效的论文年份')
    actionLock.current = true
    setBusy(true)
    setError('')
    try {
      if (
        JSON.stringify(initialDrafts(paper).meta) !==
        JSON.stringify(current.meta)
      ) {
        paper = await updateMeta(slug, paper.updated_at, current.meta)
        accept(paper)
      }
      if (current.summary !== paper.summary) {
        paper = await updateSummary(slug, paper.updated_at, current.summary)
        accept(paper)
      }
      if (
        JSON.stringify(current.prior) !== JSON.stringify(paper.prior_works) &&
        current.prior
      ) {
        paper = await updatePriorWorks(slug, paper.updated_at, current.prior)
        accept(paper)
      }
      const next = initialDrafts(paper)
      state.current.drafts = next
      if (mounted.current) {
        setDrafts(next)
        setSummaryEditing(false)
        setMetaEditing(false)
        setPriorEditing(false)
        setNotice('修改已保存。人工核验状态保持不变。')
      }
      try {
        sessionStorage.removeItem(`paper-wiki.draft.${slug}`)
      } catch {
        /* optional storage */
      }
      onChanged()
    } finally {
      actionLock.current = false
      if (mounted.current) setBusy(false)
    }
  }, [slug, onChanged, accept])
  useUnsavedChanges({ dirty, save, discard })
  async function run(action: () => Promise<void>) {
    setError('')
    setNotice('')
    try {
      await action()
    } catch (err) {
      if (mounted.current)
        setError(err instanceof Error ? err.message : '操作失败，草稿已保留')
    }
  }
  const markdown = useMemo(
    () => (detail ? readingMarkdown(detail.summary, detail.meta.title) : ''),
    [detail?.summary, detail?.meta.title]
  )
  const headings = useMemo(() => readingHeadings(markdown), [markdown])
  useScrollMemory(
    reader,
    `paper-wiki.reading.${slug}.${contentFingerprint(markdown)}`,
    Boolean(detail) && !loading && !summaryEditing
  )
  function downloadDraft(recovered = false) {
    const saved = readStored<{ drafts: Drafts } | null>(
      `paper-wiki.draft.${slug}`,
      null,
      true
    )
    const blob = new Blob(
      [JSON.stringify(recovered ? saved?.drafts || drafts : drafts, null, 2)],
      { type: 'application/json' }
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${slug}-draft.json`
    link.click()
    URL.revokeObjectURL(url)
  }
  async function verify(prior: boolean) {
    if (!detail || dirty || actionLock.current) return
    actionLock.current = true
    setBusy(true)
    try {
      const next = await (prior ? markPriorWorksReviewed : markMetaReviewed)(
        slug,
        detail.updated_at
      )
      accept(next)
      setNotice(
        prior
          ? '前作分析已标记为人工核验通过。'
          : '元信息与精读笔记已标记为人工核验通过。'
      )
      onChanged()
    } finally {
      actionLock.current = false
      if (mounted.current) setBusy(false)
    }
  }
  async function regenerate() {
    if (actionLock.current) return
    actionLock.current = true
    setBusy(true)
    setRegenerateConfirm(false)
    try {
      const jobs = await listJobs({ slug, limit: 20 })
      const running = jobs.find(
        (job) =>
          ['pending', 'running'].includes(job.status) &&
          job.target
            .split(',')
            .some((target) =>
              ['summary', 'ingest', 'fetch_and_ingest'].includes(target)
            )
      )
      const job =
        running ||
        (await startIngest(slug, ['summary'], true, detail?.updated_at))
      setNotice('精读正在后台重新生成，可在任务中心继续查看。')
      const settled = await pollJob(job.job_id, (update) => {
        if (mounted.current) setNotice(update.progress || '正在重新生成…')
      })
      if (settled.status === 'failed')
        throw new Error(settled.error || '生成失败，原笔记仍可阅读')
      const next = await getPaper(slug)
      if (mounted.current) {
        accept(next)
        setDrafts(initialDrafts(next))
        setNotice('精读笔记已更新，新内容需要重新核验。')
      }
      onChanged()
    } finally {
      actionLock.current = false
      if (mounted.current) setBusy(false)
    }
  }
  if (loading)
    return (
      <div className="p-8" aria-label="加载论文中">
        <div className="loading-skeleton mb-5 h-12" />
        <div className="loading-skeleton h-72" />
      </div>
    )
  if (!detail || !drafts)
    return (
      <div className="m-6">
        <p role="alert" className="alert-error">
          {error || '没有找到这篇论文。'}
        </p>
        <button
          className="action-button mt-4"
          onClick={() => setLoadVersion((v) => v + 1)}
        >
          重新加载
        </button>
      </div>
    )
  function setMeta(patch: Partial<PaperMetaEdits>) {
    setDrafts((prev) => prev && { ...prev, meta: { ...prev.meta, ...patch } })
  }
  return (
    <section
      className={`paper-reader ${focused ? 'is-focused' : ''}`}
      aria-label="论文阅读区"
    >
      <header className="reader-header">
        <div className="reader-meta">
          <span>
            {detail.meta.venue || 'arXiv'}
            {detail.meta.year ? ` · ${detail.meta.year}` : ''}
          </span>
          <span className={detail.meta.reviewed ? 'text-moss' : 'text-muted'}>
            {detail.meta.reviewed ? '已人工核验' : '待人工核验'}
          </span>
        </div>
        <h1>{detail.meta.title}</h1>
        <p className="reader-authors">
          {detail.meta.authors.join(', ') || slug}
        </p>
      </header>
      <div className="reader-toolbar">
        <div className="flex items-center gap-1">
          <button
            className={inspector === 'outline' ? 'is-active' : ''}
            aria-pressed={inspector === 'outline'}
            aria-label="目录"
            onClick={() =>
              setInspector(inspector === 'outline' ? null : 'outline')
            }
          >
            <List size={15} />
            <span>目录</span>
          </button>
          <button
            className={inspector === 'analysis' ? 'is-active' : ''}
            aria-label="前作与范式"
            onClick={() =>
              setInspector(inspector === 'analysis' ? null : 'analysis')
            }
          >
            <Sparkles size={15} />
            <span>前作与范式</span>
          </button>
          <button
            className={inspector === 'review' ? 'is-active' : ''}
            aria-label="核验"
            onClick={() =>
              setInspector(inspector === 'review' ? null : 'review')
            }
          >
            <ShieldCheck size={15} />
            <span>核验</span>
          </button>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <button
            aria-label={summaryEditing ? '预览笔记' : '编辑笔记'}
            disabled={busy}
            onClick={() => setSummaryEditing(!summaryEditing)}
            aria-pressed={summaryEditing}
          >
            <Edit3 size={14} />
            <span>{summaryEditing ? '预览' : '编辑笔记'}</span>
          </button>
          <button
            aria-label={focused ? '退出专注阅读' : '专注阅读'}
            title={focused ? '退出专注阅读' : '专注阅读'}
            onClick={() => setFocused(!focused)}
          >
            {focused ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
          <button
            disabled={!detail.summary.trim() || busy}
            onClick={() => onOpenPublish?.(slug)}
            title="整理为公众号文章"
            aria-label="生成文章"
          >
            <Send size={14} />
            <span>生成文章</span>
          </button>
        </div>
      </div>
      {(dirty || summaryEditing) && (
        <div className="draft-toolbar">
          <span>{dirty ? '有未保存的修改' : '编辑模式'}</span>
          <div className="flex gap-2">
            <button
              className="action-button h-8 text-xs"
              disabled={busy}
              onClick={() => request(discard)}
            >
              取消编辑
            </button>
            <button
              className="button-primary h-8 text-xs"
              disabled={busy || !dirty}
              onClick={() => void run(save)}
            >
              <Save size={13} />
              {busy ? '保存中…' : '保存修改'}
            </button>
          </div>
        </div>
      )}
      {error && (
        <div role="alert" className="reader-alert alert-error">
          {error}
          <div className="mt-3 flex flex-wrap gap-3">
            <button className="underline" onClick={() => downloadDraft()}>
              下载草稿备份
            </button>
            <button
              className="underline"
              onClick={() =>
                request(() => {
                  discard()
                  setLoadVersion((v) => v + 1)
                })
              }
            >
              重新加载最新版本
            </button>
          </div>
        </div>
      )}
      {notice && (
        <div role="status" className="reader-alert alert-success">
          {notice}
          {notice.includes('旧版草稿') && (
            <button
              className="ml-3 underline"
              onClick={() => downloadDraft(true)}
            >
              下载草稿备份
            </button>
          )}
        </div>
      )}
      <div className={`reading-layout ${inspector ? 'inspector-open' : ''}`}>
        <div
          ref={reader}
          className="reading-scroll"
          tabIndex={0}
          aria-label="精读正文"
        >
          {summaryEditing ? (
            <div className="reading-document">
              <label className="field-label" htmlFor="summary-editor">
                精读笔记 Markdown
              </label>
              <textarea
                id="summary-editor"
                className="editor min-h-[65vh]"
                disabled={busy}
                value={drafts.summary}
                onChange={(e) =>
                  setDrafts({ ...drafts, summary: e.target.value })
                }
              />
            </div>
          ) : (
            <div className="reading-document">
              <MarkdownView
                markdown={readingMarkdown(drafts.summary, detail.meta.title)}
                slug={slug}
              />
              <footer className="reading-footer">
                <span>读完之后，留下自己的判断。</span>
                <button
                  className="text-link"
                  onClick={() => request(() => setRegenerateConfirm(true))}
                  disabled={busy}
                >
                  <RefreshCw size={13} />
                  重新生成精读
                </button>
                {detail.meta.arxiv_id && (
                  <a
                    className="text-link"
                    href={`https://arxiv.org/abs/${detail.meta.arxiv_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看原文 <ExternalLink size={12} />
                  </a>
                )}
              </footer>
            </div>
          )}
        </div>
        {inspector && (
          <aside className="reader-inspector">
            <header>
              <h2>
                {inspector === 'outline'
                  ? '文章目录'
                  : inspector === 'analysis'
                    ? '前作与创新范式'
                    : '人工核验'}
              </h2>
              <button
                className="icon-button h-7 w-7"
                aria-label="关闭辅助面板"
                onClick={() => setInspector(null)}
              >
                <X size={14} />
              </button>
            </header>
            <fieldset disabled={busy} className="inspector-content min-w-0">
              {inspector === 'outline' && (
                <nav aria-label="文章目录">
                  {headings.length ? (
                    headings.map((heading) => (
                      <button
                        key={heading.id}
                        className={`outline-link level-${heading.level}`}
                        onClick={() => {
                          reader.current
                            ?.querySelector(`#${heading.id}`)
                            ?.scrollIntoView({
                              block: 'start',
                              behavior: window.matchMedia(
                                '(prefers-reduced-motion: reduce)'
                              ).matches
                                ? 'auto'
                                : 'smooth'
                            })
                          if (window.innerWidth < 1500) setInspector(null)
                        }}
                      >
                        <ChevronRight size={11} />
                        {heading.title}
                      </button>
                    ))
                  ) : (
                    <p className="text-sm text-body">这篇笔记暂无章节目录。</p>
                  )}
                </nav>
              )}
              {inspector === 'analysis' && (
                <>
                  <p className="eyebrow">创新范式</p>
                  <h3 className="my-3 text-sm font-medium">
                    {String(
                      detail.sci_pattern?.primary_pattern_name ||
                        detail.sci_pattern?.primary_pattern ||
                        '尚未分类'
                    )}
                  </h3>
                  <p className="mb-6 text-sm leading-7 text-body">
                    {String(
                      detail.sci_pattern?.reasoning ||
                        '生成分析后可在这里查看。'
                    )}
                  </p>
                  <div className="flex justify-between">
                    <h3 className="text-sm font-medium">前作分析</h3>
                    <button
                      className="text-link text-xs"
                      onClick={() => setPriorEditing(!priorEditing)}
                    >
                      {priorEditing ? '查看预览' : '编辑前作'}
                    </button>
                  </div>
                  <PriorWorksView
                    value={drafts.prior}
                    editing={priorEditing}
                    onChange={(prior) => setDrafts({ ...drafts, prior })}
                  />
                  {priorEditing && (
                    <button
                      className="button-primary mt-4 h-9 w-full justify-center"
                      disabled={!dirty || busy}
                      onClick={() => void run(save)}
                    >
                      保存修改
                    </button>
                  )}
                </>
              )}
              {inspector === 'review' && (
                <>
                  <p className="mb-5 text-xs leading-6 text-body">
                    核验表示你已检查内容与依据。保存修改后，再分别确认以下两项。
                  </p>
                  <section className="verification-card">
                    <h3>元信息与精读笔记</h3>
                    <p>{detail.meta.meta_reviewed ? '已核验通过' : '待核验'}</p>
                    <div className="flex gap-2">
                      <button
                        className="action-button text-xs"
                        onClick={() => setMetaEditing(!metaEditing)}
                      >
                        {metaEditing ? '收起元信息' : '编辑元信息'}
                      </button>
                      <button
                        className="action-button text-xs"
                        disabled={busy || dirty || detail.meta.meta_reviewed}
                        onClick={() => void run(() => verify(false))}
                      >
                        <Check size={12} />
                        确认核验
                      </button>
                    </div>
                  </section>
                  {metaEditing && (
                    <div className="my-4 space-y-3">
                      <label className="field">
                        <span className="field-label">论文标题</span>
                        <input
                          className="field-input"
                          value={drafts.meta.title}
                          onChange={(e) => setMeta({ title: e.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">作者（逗号分隔）</span>
                        <input
                          className="field-input"
                          value={drafts.meta.authors.join(', ')}
                          onChange={(e) =>
                            setMeta({
                              authors: e.target.value
                                .split(',')
                                .map((s) => s.trim())
                            })
                          }
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">年份</span>
                        <input
                          className="field-input"
                          type="number"
                          value={drafts.meta.year || ''}
                          onChange={(e) =>
                            setMeta({
                              year: e.target.value
                                ? Number(e.target.value)
                                : null
                            })
                          }
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">会议 / 期刊</span>
                        <input
                          className="field-input"
                          value={drafts.meta.venue}
                          onChange={(e) => setMeta({ venue: e.target.value })}
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">arXiv ID</span>
                        <input
                          className="field-input"
                          value={drafts.meta.arxiv_id}
                          onChange={(e) =>
                            setMeta({ arxiv_id: e.target.value })
                          }
                        />
                      </label>
                      <button
                        className="button-primary h-9"
                        disabled={!dirty || busy}
                        onClick={() => void run(save)}
                      >
                        保存元信息
                      </button>
                    </div>
                  )}
                  <section className="verification-card">
                    <h3>前作分析</h3>
                    <p>
                      {detail.meta.prior_works_reviewed
                        ? '已核验通过'
                        : '待核验'}
                    </p>
                    <div className="flex gap-2">
                      <button
                        className="action-button text-xs"
                        onClick={() => setInspector('analysis')}
                      >
                        查看前作
                      </button>
                      <button
                        className="action-button text-xs"
                        disabled={
                          busy ||
                          dirty ||
                          detail.meta.prior_works_reviewed ||
                          !detail.prior_works
                        }
                        onClick={() => void run(() => verify(true))}
                      >
                        <Check size={12} />
                        确认核验
                      </button>
                    </div>
                  </section>
                  {dirty && (
                    <p className="mt-4 text-xs text-copper">
                      请先保存修改，再确认核验。
                    </p>
                  )}
                </>
              )}
            </fieldset>
          </aside>
        )}
      </div>
      {regenerateConfirm && (
        <Dialog
          title="重新生成精读笔记"
          onClose={() => setRegenerateConfirm(false)}
        >
          <div className="p-6">
            <p className="text-sm leading-7 text-body">
              本次会调用模型并覆盖已保存的精读笔记，包括你手动修改过的正文。前作分析和创新范式不在本次生成范围内。建议先下载当前笔记备份。
            </p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button className="action-button" onClick={() => downloadDraft()}>
                下载备份
              </button>
              <button
                className="action-button"
                onClick={() => setRegenerateConfirm(false)}
              >
                保留当前笔记
              </button>
              <button
                className="button-primary h-9"
                onClick={() => void run(regenerate)}
              >
                确认重新生成
              </button>
            </div>
          </div>
        </Dialog>
      )}
    </section>
  )
}
