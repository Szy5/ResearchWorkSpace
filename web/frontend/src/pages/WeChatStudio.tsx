import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileText,
  ImagePlus,
  Loader2,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Send,
  Sparkles,
  Upload,
  Wand2
} from 'lucide-react'
import {
  JobResponse,
  PaperListItem,
  WeChatConfig,
  WeChatPackage,
  getWeChatConfig,
  getWeChatPackage,
  listJobs,
  listPapers,
  pollJob,
  prepareWeChatPackage,
  publishWeChatPackage,
  resetWeChatCover,
  updateWeChatPackage,
  uploadWeChatCover
} from '../api/client'
import JobSteps from '../components/JobSteps'
import MarkdownPublisher from './MarkdownPublisher'
import {
  useNavigationGuard,
  useUnsavedChanges
} from '../context/NavigationGuard'

type Props = {
  initialSlug?: string | null
  initialDocumentId?: string
}

type Tab = 'papers' | 'upload'

const WECHAT_TARGETS = new Set(['wechat_prepare', 'wechat_publish'])

/** Same counting rule as the WeChat editor: CJK = 1, ASCII = 0.5, astral = 2. */
export function wechatLength(text: string): number {
  let total = 0
  for (const char of text) {
    const code = char.codePointAt(0) ?? 0
    if (code > 0xffff) total += 2
    else if (code < 0x80 || (code >= 0xff61 && code <= 0xff9f)) total += 0.5
    else total += 1
  }
  return total
}

function LengthCounter({ value, limit }: { value: string; limit: number }) {
  const length = wechatLength(value)
  const over = length > limit
  return (
    <span
      className={`text-[11px] tabular-nums ${over ? 'font-medium text-error' : 'text-muted'}`}
    >
      {Number.isInteger(length) ? length : length.toFixed(1)}/{limit}
    </span>
  )
}

function StageHeader({ stage }: { stage: 0 | 1 | 2 | 3 }) {
  const stages = ['生成预览', '检查与修改', '发布到草稿箱']
  return (
    <ol className="flex flex-wrap items-center gap-2 text-xs">
      {stages.map((label, index) => {
        const done = stage > index + 1 || (stage === 3 && index === 2)
        const current = stage === index + 1 && !(stage === 3 && index === 2)
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 ${
                done
                  ? 'bg-moss text-white'
                  : current
                    ? 'bg-moss-soft font-medium text-moss-deep'
                    : 'bg-fog text-muted'
              }`}
            >
              {done ? (
                <CheckCircle2 size={12} />
              ) : (
                <span className="tabular-nums">{index + 1}</span>
              )}
              {label}
            </span>
            {index < stages.length - 1 ? (
              <span className="h-px w-5 bg-line" />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}

export default function WeChatStudio({
  initialSlug = null,
  initialDocumentId
}: Props) {
  const [tab, setTab] = useState<Tab>(initialDocumentId ? 'upload' : 'papers')
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [filter, setFilter] = useState('')
  const [slug, setSlug] = useState<string | null>(initialSlug)
  const [config, setConfig] = useState<WeChatConfig | null>(null)
  const [pkg, setPkg] = useState<WeChatPackage | null>(null)
  const [loadingPkg, setLoadingPkg] = useState(false)
  const [title, setTitle] = useState('')
  const [digest, setDigest] = useState('')
  const [author, setAuthor] = useState('')
  const [job, setJob] = useState<JobResponse | null>(null)
  const [regenerateHeadline, setRegenerateHeadline] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const actionLock = useRef(false)
  const submittedSignature = useRef('')
  const [draftSubmitted, setDraftSubmitted] = useState(false)
  const { request: requestNavigation } = useNavigationGuard()
  const coverInput = useRef<HTMLInputElement>(null)
  const activeSlug = useRef<string | null>(slug)

  const busy =
    submitting ||
    saving ||
    job?.status === 'pending' ||
    job?.status === 'running'
  const titleLimit = config?.title_limit ?? 32
  const digestLimit = config?.digest_limit ?? 120
  const authorLimit = config?.author_limit ?? 8

  function refreshPapers() {
    return listPapers()
      .then((items) => setPapers(items.filter((item) => item.has_summary)))
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err))
      )
  }

  useEffect(() => {
    void refreshPapers()
    void getWeChatConfig()
      .then(setConfig)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (initialSlug) {
      setSlug(initialSlug)
      setTab('papers')
    }
  }, [initialSlug])

  function applyPackage(next: WeChatPackage | null) {
    if (next && next.slug !== activeSlug.current) return
    setPkg(next)
    setTitle(next?.title ?? '')
    setDigest(next?.digest ?? '')
    setAuthor(next?.author ?? '')
  }

  async function watchJob(started: JobResponse) {
    const forSlug = started.slug
    if (activeSlug.current === forSlug) setJob(started)
    const settled = await pollJob(started.job_id, (update) => {
      if (activeSlug.current === forSlug) setJob(update)
    })
    if (activeSlug.current !== forSlug) return
    setJob(settled)
    if (settled.status === 'succeeded') {
      const next = await getWeChatPackage(forSlug)
      if (activeSlug.current !== forSlug) return
      applyPackage(next)
      if (settled.target === 'wechat_publish') {
        void refreshPapers()
      }
      setNotice(
        settled.target === 'wechat_publish'
          ? '已写入公众号草稿箱，可以去公众号后台检查后群发。'
          : '预览已生成，检查标题、封面和正文后即可创建草稿。'
      )
    } else {
      setError(settled.error || '任务失败')
    }
  }

  useEffect(() => {
    activeSlug.current = slug
    setError(null)
    setNotice(null)
    setJob(null)
    applyPackage(null)
    submittedSignature.current = ''
    setDraftSubmitted(false)
    if (!slug) return
    setLoadingPkg(true)
    void getWeChatPackage(slug)
      .then((next) => {
        if (activeSlug.current === slug) applyPackage(next)
      })
      .catch((err) => {
        if (activeSlug.current === slug)
          setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (activeSlug.current === slug) setLoadingPkg(false)
      })
    void listJobs({ slug, limit: 5 })
      .then((jobs) => {
        const running = jobs.find(
          (item) =>
            WECHAT_TARGETS.has(item.target) &&
            (item.status === 'pending' || item.status === 'running')
        )
        if (running && activeSlug.current === slug) void watchJob(running)
      })
      .catch(() => undefined)
  }, [slug])

  const dirty = Boolean(
    pkg &&
    (title !== pkg.title ||
      digest !== pkg.digest ||
      (author || '') !== (pkg.author || ''))
  )
  const tooLong =
    wechatLength(title) > titleLimit ||
    wechatLength(digest) > digestLimit ||
    wechatLength(author) > authorLimit

  const stage: 0 | 1 | 2 | 3 = !slug
    ? 0
    : pkg?.draft_media_id && !dirty && !pkg.stale
      ? 3
      : pkg
        ? 2
        : 1

  const visiblePapers = useMemo(() => {
    const keyword = filter.trim().toLowerCase()
    const filtered = keyword
      ? papers.filter((item) =>
          `${item.title} ${item.slug}`.toLowerCase().includes(keyword)
        )
      : papers
    return [...filtered].sort((a, b) => {
      const aPublished = Boolean(a.wechat_published_at)
      const bPublished = Boolean(b.wechat_published_at)
      if (aPublished !== bPublished) return aPublished ? 1 : -1
      return (b.updated_at || '').localeCompare(a.updated_at || '')
    })
  }, [papers, filter])

  const selectedPaper = papers.find((item) => item.slug === slug)

  async function run(action: () => Promise<void>) {
    if (actionLock.current) return
    actionLock.current = true
    setSubmitting(true)
    setError(null)
    setNotice(null)
    try {
      await action()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      actionLock.current = false
      setSubmitting(false)
    }
  }

  async function saveEdits(): Promise<WeChatPackage | null> {
    if (!slug || !pkg || !dirty) return pkg
    if (tooLong) throw new Error('标题、摘要或作者超过长度限制，请修改后保存')
    setSaving(true)
    try {
      const next = await updateWeChatPackage(slug, { title, digest, author })
      applyPackage(next)
      return next
    } finally {
      setSaving(false)
    }
  }

  useUnsavedChanges({
    dirty,
    save: async () => {
      await saveEdits()
    },
    discard: () => applyPackage(pkg)
  })

  function prepare(publish: boolean) {
    if (!slug) return
    void run(async () => {
      submittedSignature.current = ''
      setDraftSubmitted(false)
      const keepHeadline = Boolean(pkg) && !regenerateHeadline
      const started = await prepareWeChatPackage(slug, {
        title: keepHeadline ? title : undefined,
        digest: keepHeadline ? digest : undefined,
        author: author || undefined,
        regenerate_headline: !keepHeadline,
        publish
      })
      await watchJob(started)
    })
  }

  function publish() {
    if (!slug || !pkg || pkg.stale || actionLock.current) return
    const signature = JSON.stringify([slug, title, digest, author])
    if (submittedSignature.current === signature) return
    submittedSignature.current = signature
    setDraftSubmitted(true)
    void run(async () => {
      await saveEdits()
      const started = await publishWeChatPackage(slug)
      await watchJob(started)
    })
  }

  function onCoverSelected(file: File | undefined) {
    if (!slug || !file) return
    void run(async () => {
      applyPackage(await uploadWeChatCover(slug, file))
      setNotice('已替换为自定义封面')
    })
  }

  const coverUrl =
    slug && pkg
      ? `/api/papers/${encodeURIComponent(slug)}/files/wechat/cover.jpg?v=${encodeURIComponent(pkg.prepared_at + pkg.cover_source + pkg.title)}`
      : ''
  const previewUrl =
    slug && pkg
      ? `/api/papers/${encodeURIComponent(slug)}/wechat/preview?v=${encodeURIComponent(pkg.prepared_at)}`
      : ''

  return (
    <section className="mx-auto max-w-7xl animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="page-kicker">Publish</p>
          <h1 className="page-title mt-1">公众号发布</h1>
          <p className="page-subtitle">
            从精读笔记一键生成标题、摘要、封面和排版，预览确认后写入公众号草稿箱。
          </p>
        </div>
        <div className="segmented-control" role="group" aria-label="发布来源">
          <button
            aria-pressed={tab === 'papers'}
            className={tab === 'papers' ? 'is-selected' : ''}
            onClick={() => requestNavigation(() => setTab('papers'))}
          >
            <FileText size={15} />
            论文精读笔记
          </button>
          <button
            aria-pressed={tab === 'upload'}
            className={tab === 'upload' ? 'is-selected' : ''}
            onClick={() => requestNavigation(() => setTab('upload'))}
          >
            <Upload size={15} />
            上传 Markdown
          </button>
        </div>
      </div>

      {config && !config.configured ? (
        <div className="alert-warn mt-4 flex items-start gap-2">
          <AlertTriangle size={16} className="mt-0.5 flex-none" />
          <span>
            还没有配置公众号凭证：可以生成文章预览，发布前需要在{' '}
            <code>.env</code> 中填写 WECHAT_APPID 和 WECHAT_SECRET，
            并把服务器出口 IP 加入公众号后台的 IP 白名单。
          </span>
        </div>
      ) : null}

      {tab === 'upload' ? (
        <div className="mt-6">
          <MarkdownPublisher embedded initialDocumentId={initialDocumentId} />
        </div>
      ) : (
        <div className="mt-6 grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="side-panel flex max-h-[calc(100vh-220px)] flex-col p-3">
            <label className="relative mb-3 block">
              <Search
                size={14}
                className="pointer-events-none absolute left-3 top-3 text-muted"
              />
              <input
                className="field-input pl-8"
                placeholder="筛选论文"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
            </label>
            <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto">
              {visiblePapers.length === 0 ? (
                <p className="px-2 py-6 text-center text-xs text-muted">
                  没有已生成精读笔记的论文
                </p>
              ) : (
                visiblePapers.map((item) => {
                  const published = Boolean(item.wechat_published_at)
                  return (
                    <button
                      key={item.slug}
                      className={`block w-full rounded-lg border px-3 py-2.5 text-left transition ${
                        item.slug === slug
                          ? 'border-moss/50 bg-moss-soft/60'
                          : 'border-transparent hover:border-line hover:bg-fog/60'
                      }`}
                      onClick={() =>
                        requestNavigation(() => setSlug(item.slug))
                      }
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="line-clamp-2 min-w-0 text-sm font-medium leading-5 text-ink">
                          {item.title || item.slug}
                        </p>
                        <span
                          className={`badge mt-0.5 flex-none ${
                            published
                              ? 'border-moss/25 bg-moss-soft text-moss'
                              : 'border-copper/30 bg-copper-soft text-copper'
                          }`}
                        >
                          {published ? '已发布' : '未发布'}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-muted">{item.slug}</p>
                    </button>
                  )
                })
              )}
            </div>
          </aside>

          {!slug ? (
            <div className="empty-state flex flex-col items-center justify-center">
              <Send size={28} className="mb-3 text-moss" />
              <p className="font-serif text-lg text-ink">选择一篇论文开始</p>
              <p className="mt-2 max-w-sm text-sm text-body">
                左侧列出已经生成精读笔记的论文。也可以在论文详情页点击「发布到公众号」直接跳转到这里。
              </p>
            </div>
          ) : (
            <div className="min-w-0 space-y-4">
              <section className="side-panel space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="panel-title">当前论文</p>
                    <h2 className="mt-1 line-clamp-2 font-serif text-lg font-medium leading-snug text-ink">
                      {selectedPaper?.title || pkg?.source_title || slug}
                    </h2>
                  </div>
                  <StageHeader stage={stage} />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {pkg ? (
                    <>
                      <button
                        className="button-primary h-10"
                        disabled={
                          busy ||
                          tooLong ||
                          pkg.stale ||
                          (draftSubmitted &&
                            submittedSignature.current ===
                              JSON.stringify([slug, title, digest, author])) ||
                          !config?.configured
                        }
                        onClick={publish}
                        title={
                          !config?.configured ? '请先配置公众号凭证' : undefined
                        }
                      >
                        <Send size={16} />
                        {draftSubmitted
                          ? '本次草稿已提交'
                          : pkg.draft_media_id
                            ? '再次创建公众号草稿'
                            : '创建公众号草稿'}
                      </button>
                      <button
                        className="action-button h-10"
                        disabled={busy}
                        onClick={() => prepare(false)}
                      >
                        <RefreshCw size={15} />
                        重新生成预览
                      </button>
                      <label className="check-row text-xs">
                        <input
                          type="checkbox"
                          className="check"
                          checked={regenerateHeadline}
                          onChange={(event) =>
                            setRegenerateHeadline(event.target.checked)
                          }
                        />
                        同时重新生成标题和摘要
                      </label>
                    </>
                  ) : (
                    <>
                      <button
                        className="button-primary h-10"
                        disabled={busy || loadingPkg}
                        onClick={() => prepare(false)}
                      >
                        <Wand2 size={15} />
                        生成文章预览
                      </button>
                    </>
                  )}
                </div>

                {job && job.steps && job.steps.length > 0 ? (
                  <div className="rounded-lg border border-line bg-fog/50 p-3.5">
                    <div className="mb-2.5 flex items-center justify-between">
                      <p className="panel-title">
                        {busy
                          ? '正在执行'
                          : job.status === 'failed'
                            ? '执行失败'
                            : '执行完成'}
                      </p>
                      {busy ? (
                        <Loader2 size={14} className="animate-spin text-moss" />
                      ) : null}
                    </div>
                    <JobSteps steps={job.steps} />
                  </div>
                ) : null}

                {error ? (
                  <div role="alert" className="alert-error">
                    {error}
                    {draftSubmitted && (
                      <p className="mt-2 text-xs">
                        请先在任务中心和公众号后台核对本次结果，避免重复创建草稿。
                      </p>
                    )}
                  </div>
                ) : null}
                {notice ? <div className="alert-success">{notice}</div> : null}
                {pkg?.stale ? (
                  <div className="alert-warn flex items-center gap-2">
                    <AlertTriangle size={15} />
                    精读笔记在生成预览之后被修改过，请重新生成预览后再创建草稿。
                  </div>
                ) : null}
                {pkg && pkg.warnings.length > 0 ? (
                  <details className="alert-warn">
                    <summary className="cursor-pointer">
                      有 {pkg.warnings.length} 条处理提示
                    </summary>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
                      {pkg.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </details>
                ) : null}
                {pkg?.draft_media_id ? (
                  <div className="flex flex-wrap items-center gap-2 text-xs text-body">
                    <CheckCircle2 size={14} className="text-moss" />
                    上次创建草稿：
                    {pkg.published_at
                      ? new Date(pkg.published_at).toLocaleString()
                      : ''}
                    <a
                      className="inline-flex items-center gap-1 text-moss underline underline-offset-2"
                      href="https://mp.weixin.qq.com"
                      target="_blank"
                      rel="noreferrer"
                    >
                      打开公众号后台草稿箱
                      <ExternalLink size={12} />
                    </a>
                  </div>
                ) : null}
              </section>

              {pkg ? (
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
                  <fieldset
                    disabled={busy}
                    className="side-panel min-w-0 space-y-4"
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="panel-title">标题 · 摘要 · 封面</h3>
                      <button
                        className="action-button h-8 text-xs"
                        disabled={!dirty || saving || tooLong || busy}
                        onClick={() =>
                          void run(async () => {
                            await saveEdits()
                            setNotice('修改已保存')
                          })
                        }
                      >
                        {saving ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <Save size={13} />
                        )}
                        保存修改
                      </button>
                    </div>
                    <label className="field">
                      <span className="field-label flex items-center justify-between">
                        公众号标题
                        <LengthCounter value={title} limit={titleLimit} />
                      </span>
                      <input
                        className="field-input"
                        value={title}
                        onChange={(event) => setTitle(event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span className="field-label flex items-center justify-between">
                        摘要（消息列表导语）
                        <LengthCounter value={digest} limit={digestLimit} />
                      </span>
                      <textarea
                        className="field-textarea min-h-[84px]"
                        value={digest}
                        onChange={(event) => setDigest(event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span className="field-label flex items-center justify-between">
                        作者
                        <LengthCounter value={author} limit={authorLimit} />
                      </span>
                      <input
                        className="field-input"
                        placeholder={
                          config?.default_author
                            ? `默认：${config.default_author}`
                            : '可选'
                        }
                        value={author}
                        onChange={(event) => setAuthor(event.target.value)}
                      />
                    </label>

                    <div>
                      <div className="mb-1.5 flex items-center justify-between">
                        <span className="field-label mb-0">
                          封面{' '}
                          {pkg.cover_source === 'uploaded'
                            ? '（自定义）'
                            : '（自动生成）'}
                        </span>
                        <div className="flex gap-1.5">
                          <button
                            className="action-button h-8 text-xs"
                            disabled={busy}
                            onClick={() => coverInput.current?.click()}
                          >
                            <ImagePlus size={13} />
                            上传封面
                          </button>
                          {pkg.cover_source === 'uploaded' ? (
                            <button
                              className="action-button h-8 text-xs"
                              disabled={busy}
                              onClick={() =>
                                void run(async () =>
                                  applyPackage(await resetWeChatCover(slug))
                                )
                              }
                            >
                              <RotateCcw size={13} />
                              恢复自动封面
                            </button>
                          ) : null}
                        </div>
                      </div>
                      <input
                        ref={coverInput}
                        type="file"
                        accept="image/png,image/jpeg"
                        className="hidden"
                        onChange={(event) => {
                          onCoverSelected(event.target.files?.[0])
                          event.target.value = ''
                        }}
                      />
                      <img
                        src={coverUrl}
                        alt="公众号封面"
                        className="w-full rounded-lg border border-line"
                      />
                      <p className="field-hint">
                        自动封面使用公众号标题和论文方法框架图；标题修改保存后会自动重绘。
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div className="metric">
                        <strong>{pkg.image_count}</strong>
                        <span>张论文配图</span>
                      </div>
                      <div className="metric">
                        <strong>{pkg.formula_count}</strong>
                        <span>个公式转为图片</span>
                      </div>
                    </div>
                  </fieldset>

                  <section className="flex flex-col items-center">
                    <p className="panel-title mb-2 self-start">手机预览</p>
                    <div className="w-full max-w-[400px] rounded-[28px] border-[6px] border-rail bg-white p-0 shadow-lift">
                      <div className="border-b border-line px-4 py-3">
                        <p className="line-clamp-2 text-[17px] font-semibold leading-snug text-ink">
                          {title || '（无标题）'}
                        </p>
                        <p className="mt-1 text-xs text-muted">
                          {author || config?.default_author || 'Paper-Wiki'}
                        </p>
                      </div>
                      <iframe
                        title="公众号文章预览"
                        src={previewUrl}
                        className="h-[640px] w-full rounded-b-[22px] border-0"
                      />
                    </div>
                    <a
                      className="action-button mt-3 h-8 text-xs"
                      href={previewUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink size={13} />
                      新窗口打开预览
                    </a>
                  </section>
                </div>
              ) : !busy && !loadingPkg ? (
                <div className="empty-state">
                  <Sparkles size={24} className="mx-auto mb-3 text-moss" />
                  <p className="font-serif text-lg text-ink">
                    还没有生成公众号版本
                  </p>
                  <p className="mx-auto mt-2 max-w-md text-sm text-body">
                    先生成标题、摘要、封面和文章排版。检查预览后，点击「创建公众号草稿」写入草稿箱。
                  </p>
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
