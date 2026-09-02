import { FormEvent, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Download, Loader2, RefreshCw, Search, Sparkles } from 'lucide-react'
import {
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
import { StagedCandidate } from '../hooks/useBatchGeneration'

type Props = {
  stagedKeys: Set<string>
  onStage: (items: StagedCandidate[]) => void
  onIngested: (slug: string) => void
}

export default function Home({ stagedKeys, onStage, onIngested }: Props) {
  const [results, setResults] = useState<SearchCandidate[]>([])
  const [searched, setSearched] = useState(false)

  return (
    <section className="mx-auto max-w-3xl animate-fade-up">
      <header className="pb-2 pt-4">
        <p className="page-kicker">Discover</p>
        <h1 className="page-title mt-2">找到下一篇值得读的论文</h1>
        <p className="page-subtitle max-w-xl">
          搜索 arXiv、按 ID 拉取，或从今日推荐里挑选；勾选后进入暂存区批量生成精读产物。
        </p>
      </header>
      <SearchBar onResults={(next) => { setResults(next); setSearched(true) }} onStage={onStage} onIngested={onIngested} />
      {searched ? (
        <SearchResultsFeed results={results} stagedKeys={stagedKeys} onStage={onStage} />
      ) : null}
      <RecommendedFeed stagedKeys={stagedKeys} onStage={onStage} />
    </section>
  )
}

function stageOne(candidate: SearchCandidate, onStage: Props['onStage'], slug?: string) {
  onStage([{ key: candidate.arxiv_id, candidate, slug }])
}

function SearchBar({
  onResults,
  onStage,
  onIngested
}: {
  onResults: (results: SearchCandidate[]) => void
  onStage: Props['onStage']
  onIngested: Props['onIngested']
}) {
  const [query, setQuery] = useState('')
  const [startYear, setStartYear] = useState(2020)
  const [endYear, setEndYear] = useState(2026)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showIdInput, setShowIdInput] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const candidates = await searchPapers({ q: query, start_year: startYear, end_year: endYear })
      onResults(candidates)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="pb-6 pt-6">
      <form className="search-shell" onSubmit={submit}>
        <Search size={18} className="flex-none text-muted" />
        <input
          className="h-14 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索 arXiv 论文，比如 transformer attention mechanism"
        />
        <button className="button-primary h-11 flex-none" type="submit" disabled={loading}>
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          搜索
        </button>
      </form>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-body">
        <span className="font-medium text-ink-soft">年份</span>
        <input
          className="h-8 w-20 rounded-md border border-line bg-canvas px-2 text-xs outline-none transition focus:border-moss/50 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          type="number"
          value={startYear}
          onChange={(event) => setStartYear(Number(event.target.value))}
        />
        <span className="text-muted">–</span>
        <input
          className="h-8 w-20 rounded-md border border-line bg-canvas px-2 text-xs outline-none transition focus:border-moss/50 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          type="number"
          value={endYear}
          onChange={(event) => setEndYear(Number(event.target.value))}
        />
        <span className="h-3 w-px bg-line" />
        <button className="font-medium text-moss underline-offset-4 hover:underline" onClick={() => setShowIdInput((prev) => !prev)}>
          或按 arXiv ID 直接添加
        </button>
      </div>

      {error ? <div className="alert-error mt-3">{error}</div> : null}
      {showIdInput ? <FetchByIdTab onStage={onStage} onIngested={onIngested} /> : null}
    </div>
  )
}

function SearchResultsFeed({
  results,
  stagedKeys,
  onStage
}: {
  results: SearchCandidate[]
  stagedKeys: Set<string>
  onStage: Props['onStage']
}) {
  const visibleResults = useMemo(
    () => results.filter((candidate) => !stagedKeys.has(candidate.arxiv_id)),
    [results, stagedKeys]
  )

  return (
    <section className="mt-2">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="page-kicker">Search</p>
          <h2 className="mt-1 font-serif text-[22px] tracking-tight">检索结果</h2>
        </div>
        <p className="text-xs text-muted">{visibleResults.length} 篇可添加</p>
      </div>
      {visibleResults.length === 0 ? (
        <div className="empty-state">
          <p className="text-sm text-body">
            {results.length > 0 ? '搜索结果都已加入生成暂存区。' : '没有找到匹配的论文，换个关键词试试。'}
          </p>
        </div>
      ) : (
        <div className="mt-3 grid grid-cols-1 gap-3">
          {visibleResults.map((candidate) => (
            <CandidateCard
              key={candidate.arxiv_id}
              candidate={candidate}
              onToggleSelect={() => stageOne(candidate, onStage)}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function RecommendedFeed({ stagedKeys, onStage }: Pick<Props, 'stagedKeys' | 'onStage'>) {
  const [snapshot, setSnapshot] = useState<RecommendationSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshProgress, setRefreshProgress] = useState<string | null>(null)

  useEffect(() => {
    void loadSnapshot()
    void resumeRefresh()
  }, [])

  async function resumeRefresh() {
    try {
      const jobs = await listJobs({ target: 'recommend_refresh', limit: 1 })
      const latest = jobs[0]
      if (!latest || (latest.status !== 'pending' && latest.status !== 'running')) return
      setRefreshing(true)
      setRefreshProgress(latest.progress || '后台生成中...')
      const settled = await pollJob(latest.job_id, (update) => setRefreshProgress(update.progress))
      if (settled.status === 'succeeded') {
        await loadSnapshot()
      } else {
        setError(settled.error ?? 'Refresh failed')
      }
    } catch {
      // Task recovery is best-effort; the current snapshot remains usable.
    } finally {
      setRefreshing(false)
      setRefreshProgress(null)
    }
  }

  async function loadSnapshot() {
    setLoading(true)
    setError(null)
    try {
      setSnapshot(await getRecommendationsToday())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function refresh() {
    setRefreshing(true)
    setError(null)
    setRefreshProgress(null)
    try {
      const job = await refreshRecommendations()
      window.localStorage.setItem('paper-wiki.recommendation-job', job.job_id)
      const settled = await pollJob(job.job_id, (update) => setRefreshProgress(update.progress))
      if (settled.status === 'succeeded') {
        setSnapshot(settled.result as unknown as RecommendationSnapshot)
      } else {
        setError(settled.error ?? 'Refresh failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      window.localStorage.removeItem('paper-wiki.recommendation-job')
      setRefreshing(false)
      setRefreshProgress(null)
    }
  }

  const pool = useMemo(
    () => (snapshot?.candidates ?? []).filter((candidate) => !stagedKeys.has(candidate.arxiv_id)),
    [snapshot, stagedKeys]
  )

  return (
    <section className="mt-10">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="page-kicker">Today</p>
          <h2 className="mt-1 font-serif text-[24px] tracking-tight">今日推荐</h2>
          <p className="mt-1 text-sm text-body">
            {snapshot
              ? `${snapshot.date} · 候选池 ${snapshot.candidate_pool_size} 篇 · 口味语料 ${snapshot.corpus_size} 篇`
              : '基于你的 Zotero 口味语料，每天从 arXiv 新增里挑出最相关的一批论文'}
          </p>
        </div>
        <button className="action-button" disabled={refreshing} onClick={() => void refresh()}>
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? refreshProgress || '生成中...' : '刷新推荐'}
        </button>
      </div>

      {snapshot?.degraded ? (
        <div className="alert-warn mb-4 flex items-center gap-2">
          <AlertTriangle size={16} />
          Embedding 模型不可用，本次推荐按原始候选顺序展示，未做相似度排序。
        </div>
      ) : null}
      {error ? <div className="alert-error mb-4">{error}</div> : null}
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-body">
          <Loader2 size={16} className="animate-spin" />
          加载推荐中...
        </div>
      ) : null}

      {!loading && pool.length === 0 ? (
        <div className="empty-state">
          <Sparkles className="mx-auto mb-3 text-moss" size={28} />
          <p className="font-serif text-lg tracking-tight text-ink">
            {snapshot ? '今日候选都已加入生成暂存区。' : '还没有今日推荐快照。'}
          </p>
          <p className="mt-2 text-sm text-body">
            {snapshot ? '去暂存区批量生成，或稍后再回来看新的推荐。' : '点一下，按你的口味生成今天的候选池。'}
          </p>
          {!snapshot ? (
            <button className="button-primary mt-5 h-10 inline-flex" disabled={refreshing} onClick={() => void refresh()}>
              <RefreshCw size={16} />
              立即生成推荐
            </button>
          ) : null}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {pool.map((candidate) => (
            <CandidateCard
              key={candidate.arxiv_id}
              candidate={candidate}
              onToggleSelect={() => stageOne(candidate, onStage)}
              showThumbnail
            />
          ))}
        </div>
      )}
    </section>
  )
}

function FetchByIdTab({ onStage, onIngested }: Pick<Props, 'onStage' | 'onIngested'>) {
  const [arxivId, setArxivId] = useState('')
  const [andIngest, setAndIngest] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const id = arxivId.trim()
    if (!id) return
    setFetching(true)
    setError(null)
    setStatus('正在下载 PDF / LaTeX 源码...')
    try {
      const job = await fetchPaper(id, { andIngest })
      const settled = await pollJob(job.job_id, (update) => {
        if (update.progress) setStatus(update.progress)
      })
      if (settled.status !== 'succeeded') {
        setError(settled.error ?? 'Fetch failed')
        return
      }
      const slug = String(settled.result?.slug ?? id)
      if (andIngest) {
        setStatus(`已生成三件套，进入待审查队列：${slug}`)
        onIngested(slug)
      } else {
        setStatus(`已拉取源文件到 raw/${slug}/，已加入生成暂存区`)
        onStage([{ key: id, slug, candidate: { title: slug, authors: [], year: null, abstract: '', url: '', venue: '', arxiv_id: id, citation_count: null, publication_date: null, source: 'arxiv', score: null } }])
      }
      setArxivId('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setFetching(false)
    }
  }

  return (
    <div className="surface-card mt-4 max-w-xl p-4">
      <p className="panel-title">按 arXiv ID 添加</p>
      <form className="mt-3 flex items-center gap-2" onSubmit={submit}>
        <input
          className="field-input flex-1"
          value={arxivId}
          onChange={(event) => setArxivId(event.target.value)}
          placeholder="2401.12345"
        />
        <button className="action-button" type="submit" disabled={fetching}>
          {fetching ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
          拉取
        </button>
      </form>
      <label className="check-row mt-3">
        <input
          type="checkbox"
          className="check"
          checked={andIngest}
          onChange={(event) => setAndIngest(event.target.checked)}
        />
        拉取后立即生成 Summary / Prior Works / Pattern
      </label>
      {error ? <div className="alert-error mt-4">{error}</div> : null}
      {status && !error ? <div className="alert-success mt-4">{status}</div> : null}
    </div>
  )
}
