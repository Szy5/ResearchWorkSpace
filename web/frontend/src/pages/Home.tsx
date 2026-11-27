import { FormEvent, useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  ExternalLink,
  Loader2,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Sparkles
} from 'lucide-react'
import {
  PaperListItem,
  RecommendationSnapshot,
  SearchCandidate,
  fetchPaper,
  getRecommendationsToday,
  listJobs,
  pollJob,
  refreshRecommendations,
  searchPapers
} from '../api/client'
import CandidateCard from '../components/CandidateCard'
import Dialog from '../components/Dialog'
import { JobState, StagedCandidate } from '../hooks/useBatchGeneration'
import { readStored, writeStored } from '../utils/storage'

type Props = {
  stagedKeys: Set<string>
  onStage: (items: StagedCandidate[]) => void
  onIngested: (slug: string) => void
  onUnstage?: (key: string) => void
  jobStatus?: Record<string, JobState>
  papers?: PaperListItem[]
  onOpenPaper?: (slug: string) => void
  recentSlug?: string | null
}
type SearchSnapshot = {
  query: string
  startYear: number
  endYear: number
  results: SearchCandidate[]
  completedQuery: string
  searched: boolean
}
const SEARCH_KEY = 'paper-wiki.discovery.v2'
export function arxivIdFromInput(value: string): string | null {
  const trimmed = value
    .trim()
    .replace(/^arxiv:/i, '')
    .replace(/\.pdf(?:\?.*)?$/i, '')
  const match = trimmed.match(
    /^(?:https?:\/\/(?:www\.)?arxiv\.org\/(?:abs|pdf)\/)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?\/\d{7}(?:v\d+)?)(?:[?#].*)?$/i
  )
  return match?.[1] || null
}
export default function Home({
  stagedKeys,
  onStage,
  onIngested,
  onUnstage,
  jobStatus = {},
  papers = [],
  onOpenPaper,
  recentSlug
}: Props) {
  const [search, setSearch] = useState<SearchSnapshot>(() =>
    readStored(
      SEARCH_KEY,
      {
        query: '',
        startYear: 2020,
        endYear: new Date().getFullYear(),
        results: [],
        completedQuery: '',
        searched: false
      },
      true
    )
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [andIngest, setAndIngest] = useState(false)
  const [preview, setPreview] = useState<SearchCandidate | null>(null)
  const sequence = useRef(0)
  const importing = useRef(false)
  useEffect(() => {
    writeStored(SEARCH_KEY, search, true)
  }, [search])
  const inputId = arxivIdFromInput(search.query)
  const recent = papers.find((paper) => paper.slug === recentSlug)
  const findKnown = (candidate: SearchCandidate) =>
    papers.find(
      (paper) =>
        (paper.arxiv_id || paper.slug)
          .replace(/^arXiv-/i, '')
          .replace(/v\d+$/, '') === candidate.arxiv_id.replace(/v\d+$/, '')
    )
  function toggle(candidate: SearchCandidate) {
    if (stagedKeys.has(candidate.arxiv_id)) onUnstage?.(candidate.arxiv_id)
    else onStage([{ key: candidate.arxiv_id, candidate, slug: undefined }])
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    const query = search.query.trim()
    if (!query || importing.current) return
    const requestId = ++sequence.current
    setError('')
    setNotice('')
    const id = arxivIdFromInput(query)
    if (!id && /arxiv\.org|^arxiv:/i.test(query)) {
      setError('这个 arXiv 链接无法识别，请输入完整链接或论文 ID。')
      return
    }
    if (
      !id &&
      (!Number.isInteger(search.startYear) ||
        !Number.isInteger(search.endYear) ||
        search.startYear < 1991 ||
        search.startYear > search.endYear ||
        search.endYear > new Date().getFullYear())
    ) {
      setFiltersOpen(true)
      setError(
        '请输入有效年份：起始年份不得晚于结束年份，结束年份不得超过今年。'
      )
      return
    }
    setLoading(true)
    try {
      if (id) {
        const known = findKnown({ arxiv_id: id } as SearchCandidate)
        if (known && onOpenPaper) {
          onOpenPaper(known.slug)
          return
        }
        importing.current = true
        setNotice('正在添加论文，可在任务面板查看后台进度…')
        const job = await fetchPaper(id, { andIngest })
        const settled = await pollJob(job.job_id, (update) => {
          if (requestId === sequence.current)
            setNotice(update.progress || '正在处理论文…')
        })
        if (settled.status === 'failed')
          throw new Error(settled.error || '添加失败，请在任务面板查看原因')
        const slug = String(settled.result?.slug || id)
        if (andIngest) {
          setNotice('精读已生成')
          onIngested(slug)
        } else {
          onStage([
            {
              key: id,
              slug,
              candidate: {
                title: id,
                arxiv_id: id,
                authors: [],
                year: null,
                abstract: '',
                venue: '',
                url: `https://arxiv.org/abs/${id}`,
                citation_count: null,
                publication_date: null,
                source: 'arxiv',
                score: null
              }
            }
          ])
          setNotice('论文已添加并选中，点击“生成精读”继续。')
        }
      } else {
        const results = await searchPapers({
          q: query,
          start_year: search.startYear,
          end_year: search.endYear
        })
        if (requestId === sequence.current)
          setSearch((prev) => ({
            ...prev,
            results,
            completedQuery: query,
            searched: true
          }))
      }
    } catch (err) {
      if (requestId === sequence.current)
        setError(err instanceof Error ? err.message : '请求失败，请重试')
    } finally {
      importing.current = false
      if (requestId === sequence.current) setLoading(false)
    }
  }
  const renderCandidate = (candidate: SearchCandidate) => {
    const known = findKnown(candidate)
    return (
      <CandidateCard
        key={candidate.arxiv_id}
        candidate={candidate}
        selected={stagedKeys.has(candidate.arxiv_id)}
        status={jobStatus[candidate.arxiv_id]?.status}
        onToggleSelect={() => toggle(candidate)}
        onPreview={() => setPreview(candidate)}
        onOpenPaper={
          known && onOpenPaper ? () => onOpenPaper(known.slug) : undefined
        }
      />
    )
  }
  return (
    <section className="discovery-page">
      <header className="discovery-heading">
        <p className="eyebrow">
          <span className="status-dot" /> YOUR RESEARCH, IN FOCUS
        </p>
        <h1>从一篇好论文开始。</h1>
        <p>发现值得读的工作，让每一次阅读留下积累。</p>
      </header>
      <form onSubmit={submit} className="discovery-search">
        <div className="search-shell">
          <Search size={19} className="text-muted" />
          <input
            aria-label="搜索 arXiv 或添加论文"
            value={search.query}
            onChange={(event) =>
              setSearch((prev) => ({ ...prev, query: event.target.value }))
            }
            placeholder="搜索 arXiv，或粘贴论文链接 / ID"
          />
          <button
            className="button-primary h-10"
            disabled={loading || !search.query.trim()}
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <ArrowRight size={16} />
            )}
            {inputId ? '添加论文' : '搜索'}
          </button>
        </div>
        <div className="search-options">
          <span>搜索范围：arXiv</span>
          <button
            type="button"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen(!filtersOpen)}
          >
            <SlidersHorizontal size={13} />
            年份 {search.startYear}–{search.endYear}
          </button>
        </div>
        {filtersOpen && (
          <div className="flex flex-wrap items-center gap-3 pb-3 text-xs">
            <label>
              起始年份{' '}
              <input
                className="year-input"
                aria-label="起始年份"
                type="number"
                min={1991}
                value={search.startYear || ''}
                onChange={(e) =>
                  setSearch((prev) => ({
                    ...prev,
                    startYear: Number(e.target.value)
                  }))
                }
              />
            </label>
            <label>
              结束年份{' '}
              <input
                className="year-input"
                aria-label="结束年份"
                type="number"
                max={new Date().getFullYear()}
                value={search.endYear || ''}
                onChange={(e) =>
                  setSearch((prev) => ({
                    ...prev,
                    endYear: Number(e.target.value)
                  }))
                }
              />
            </label>
          </div>
        )}
        {inputId && (
          <label className="check-row pb-3 text-xs">
            <input
              type="checkbox"
              className="check"
              checked={andIngest}
              onChange={(e) => setAndIngest(e.target.checked)}
            />
            下载后立即生成精读笔记、前作分析与创新范式
          </label>
        )}
      </form>
      {error && (
        <div role="alert" className="alert-error mb-5">
          {error}
          {search.searched && (
            <p className="mt-1 text-xs">
              下方仍显示上次成功检索“{search.completedQuery}”的结果。
            </p>
          )}
        </div>
      )}
      {notice && (
        <p role="status" className="alert-success mb-5">
          {notice}
        </p>
      )}
      {recent && onOpenPaper && (
        <button
          className="continue-reading"
          onClick={() => onOpenPaper(recent.slug)}
        >
          <BookOpen size={20} />
          <span>
            <small>继续上次阅读</small>
            <strong>{recent.title}</strong>
          </span>
          <ArrowRight size={17} />
        </button>
      )}
      {search.searched && (
        <section className="feed-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">SEARCH RESULTS</p>
              <h2>
                检索结果 <span>{search.results.length}</span>
              </h2>
              <p>
                “{search.completedQuery}” · 点击标题预览，勾选后批量生成精读
              </p>
            </div>
            <button
              className="text-link text-xs"
              onClick={() =>
                setSearch((prev) => ({
                  ...prev,
                  searched: false,
                  results: [],
                  completedQuery: ''
                }))
              }
            >
              收起结果
            </button>
          </div>
          {search.results.length ? (
            <div className="candidate-list">
              {search.results.map(renderCandidate)}
            </div>
          ) : (
            <div className="empty-state">
              <h3>没有找到匹配的论文</h3>
              <p className="mt-2 text-sm text-body">
                尝试更短的关键词，或扩大年份范围。
              </p>
            </div>
          )}
        </section>
      )}
      <RecommendedFeed renderCandidate={renderCandidate} />
      {preview && (
        <Dialog
          title="论文预览"
          className="candidate-preview"
          onClose={() => setPreview(null)}
        >
          <div className="p-6">
            <p className="eyebrow">ARXIV · {preview.arxiv_id}</p>
            <h3 className="mt-3 font-serif text-2xl leading-snug">
              {preview.title}
            </h3>
            <p className="mt-3 text-sm text-body">
              {preview.authors.join(', ')}
              {preview.year ? ` · ${preview.year}` : ''}
            </p>
            <p className="my-6 whitespace-pre-wrap text-sm leading-7 text-ink-soft">
              {preview.abstract ||
                preview.display_summary ||
                '暂无摘要，请查看原文。'}
            </p>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <a
                className="action-button"
                href={`https://arxiv.org/abs/${preview.arxiv_id}`}
                target="_blank"
                rel="noreferrer"
              >
                查看原文 <ExternalLink size={13} />
              </a>
              {findKnown(preview) && onOpenPaper ? (
                <button
                  className="button-primary h-9"
                  onClick={() => {
                    setPreview(null)
                    onOpenPaper(findKnown(preview)!.slug)
                  }}
                >
                  打开论文
                </button>
              ) : (
                <button
                  className="button-primary h-9"
                  disabled={['pending', 'running', 'succeeded'].includes(
                    jobStatus[preview.arxiv_id]?.status
                  )}
                  onClick={() => toggle(preview)}
                >
                  {stagedKeys.has(preview.arxiv_id)
                    ? '取消选择'
                    : '选择这篇论文'}
                </button>
              )}
            </div>
          </div>
        </Dialog>
      )}
    </section>
  )
}
function RecommendedFeed({
  renderCandidate
}: {
  renderCandidate: (candidate: SearchCandidate) => React.ReactNode
}) {
  const [snapshot, setSnapshot] = useState<RecommendationSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState('')
  const locked = useRef(false)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    void getRecommendationsToday()
      .then((next) => {
        if (mounted.current) setSnapshot(next)
      })
      .catch((err) => {
        if (mounted.current) setError(String(err.message))
      })
      .finally(() => {
        if (mounted.current) setLoading(false)
      })
    void listJobs({ target: 'recommend_refresh', limit: 1 })
      .then(async (jobs) => {
        if (!mounted.current || locked.current) return
        const active = jobs.find((job) =>
          ['pending', 'running'].includes(job.status)
        )
        if (active) await watch(active.job_id)
      })
      .catch(() => undefined)
    return () => {
      mounted.current = false
    }
  }, [])
  async function watch(jobId: string) {
    locked.current = true
    setRefreshing(true)
    try {
      const settled = await pollJob(jobId, (update) => {
        if (mounted.current) setProgress(update.progress || '正在更新…')
      })
      if (settled.status === 'failed')
        throw new Error(settled.error || '更新推荐失败')
      const next = await getRecommendationsToday()
      if (mounted.current) setSnapshot(next)
    } catch (err) {
      if (mounted.current)
        setError(
          err instanceof Error ? err.message : '同步失败，请稍后查看任务面板'
        )
    } finally {
      locked.current = false
      if (mounted.current) {
        setRefreshing(false)
        setProgress('')
      }
    }
  }
  async function refresh() {
    if (locked.current) return
    locked.current = true
    setRefreshing(true)
    setError('')
    try {
      const jobs = await listJobs({ target: 'recommend_refresh', limit: 5 })
      const running = jobs.find((job) =>
        ['pending', 'running'].includes(job.status)
      )
      const job = running || (await refreshRecommendations())
      await watch(job.job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败')
      locked.current = false
      setRefreshing(false)
    }
  }
  const today = new Date().toLocaleDateString('sv-SE')
  const fresh = snapshot?.date === today
  return (
    <section className="feed-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">A LITTLE DISCOVERY, EVERY DAY</p>
          <h2>
            {snapshot && !fresh ? '最近推荐' : '今日推荐'}{' '}
            <Sparkles size={17} />
          </h2>
          <p>
            {snapshot
              ? `${snapshot.date} · ${snapshot.candidates.length} 篇论文 · 基于 ${snapshot.corpus_size} 篇阅读偏好语料`
              : '从你的研究兴趣出发，发现下一篇值得读的工作。'}
          </p>
        </div>
        <button
          className="action-button"
          disabled={refreshing}
          onClick={() => void refresh()}
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? '更新中…' : '更新推荐'}
        </button>
      </div>
      {snapshot && !fresh && (
        <p className="feed-notice">
          这是最新可用的推荐，尚未更新到今天。你可以继续浏览或更新推荐。
        </p>
      )}
      {snapshot?.degraded && (
        <p className="feed-notice">
          个性化排序暂不可用，当前按候选原始顺序展示；以下论文未经兴趣相似度排序。
        </p>
      )}
      {error && (
        <div role="alert" className="alert-error mb-4">
          {error}
          <button className="ml-3 underline" onClick={() => void refresh()}>
            重试更新
          </button>
        </div>
      )}
      {progress && (
        <p role="status" className="mb-4 text-sm text-body">
          {progress}
        </p>
      )}
      {loading ? (
        <div className="space-y-3" aria-label="加载推荐中">
          <div className="loading-skeleton h-28" />
          <div className="loading-skeleton h-28" />
        </div>
      ) : snapshot?.candidates.length ? (
        <div className="candidate-list">
          {snapshot.candidates.map(renderCandidate)}
        </div>
      ) : (
        <div className="empty-state">
          <Sparkles size={24} className="mx-auto mb-4 text-muted" />
          <h3>{snapshot ? '这次没有匹配的推荐' : '还没有推荐，开始发现吧'}</h3>
          <p className="mt-2 text-sm text-body">
            更新推荐后，可在这里挑选论文并生成精读。
          </p>
          <button
            className="action-button mt-5"
            disabled={refreshing}
            onClick={() => void refresh()}
          >
            生成推荐 <ArrowRight size={14} />
          </button>
        </div>
      )}
    </section>
  )
}
