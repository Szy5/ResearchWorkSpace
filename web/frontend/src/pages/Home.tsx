import { FormEvent, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Download, Loader2, RefreshCw, Search, Sparkles } from 'lucide-react'
import {
  RecommendationSnapshot,
  SearchCandidate,
  fetchPaper,
  getRecommendationsToday,
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
    <section className="mx-auto max-w-3xl">
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
    <div className="pb-6 pt-2">
      <form
        className="flex items-center gap-3 rounded-xl border border-line bg-canvas pl-4 pr-1.5 focus-within:border-moss"
        onSubmit={submit}
      >
        <Search size={18} className="flex-none text-muted" />
        <input
          className="h-14 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索 arXiv 论文，比如 transformer attention mechanism"
        />
        <button className="button-primary h-10 flex-none" type="submit" disabled={loading}>
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          搜索
        </button>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-body">
        <span>年份</span>
        <input
          className="h-8 w-20 rounded-lg border border-line bg-canvas px-2 text-xs outline-none focus:border-moss [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          type="number"
          value={startYear}
          onChange={(event) => setStartYear(Number(event.target.value))}
        />
        <span className="text-muted">–</span>
        <input
          className="h-8 w-20 rounded-lg border border-line bg-canvas px-2 text-xs outline-none focus:border-moss [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          type="number"
          value={endYear}
          onChange={(event) => setEndYear(Number(event.target.value))}
        />
        <span className="text-line">|</span>
        <button className="underline underline-offset-2 hover:text-ink" onClick={() => setShowIdInput((prev) => !prev)}>
          或按 arXiv ID 直接添加
        </button>
      </div>

      {error ? <div className="mt-3 rounded-lg border border-error-line bg-error-soft p-3 text-sm text-error">{error}</div> : null}
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
    <section className="mt-6">
      <h2 className="font-serif text-lg font-semibold">检索结果</h2>
      {visibleResults.length === 0 ? (
        <p className="mt-3 text-sm text-body">
          {results.length > 0 ? '搜索结果都已加入生成暂存区。' : '没有找到匹配的论文，换个关键词试试。'}
        </p>
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
  }, [])

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
      const settled = await pollJob(job.job_id, (update) => setRefreshProgress(update.progress))
      if (settled.status === 'succeeded') {
        setSnapshot(settled.result as unknown as RecommendationSnapshot)
      } else {
        setError(settled.error ?? 'Refresh failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefreshing(false)
      setRefreshProgress(null)
    }
  }

  const pool = useMemo(
    () => (snapshot?.candidates ?? []).filter((candidate) => !stagedKeys.has(candidate.arxiv_id)),
    [snapshot, stagedKeys]
  )

  return (
    <section className="mt-8">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-serif text-[22px] font-semibold">今日推荐</h1>
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
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-copper/40 bg-canvas p-3 text-sm text-copper">
          <AlertTriangle size={16} />
          Embedding 模型不可用，本次推荐按原始候选顺序展示，未做相似度排序。
        </div>
      ) : null}
      {error ? <div className="mb-4 rounded-lg border border-error-line bg-error-soft p-3 text-sm text-error">{error}</div> : null}
      {loading ? <div className="text-sm text-body">Loading...</div> : null}

      {!loading && pool.length === 0 ? (
        <div className="border border-dashed border-line bg-canvas p-10 text-center">
          <Sparkles className="mx-auto mb-3 text-moss" size={28} />
          <p className="text-sm text-body">
            {snapshot ? '今日候选都已加入生成暂存区。' : '还没有今日推荐快照。'}
          </p>
          {!snapshot ? (
            <button className="action-button mt-3 inline-flex" disabled={refreshing} onClick={() => void refresh()}>
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
    <div className="mt-3 max-w-xl">
      <form className="flex items-center gap-2" onSubmit={submit}>
        <input
          className="h-10 flex-1 rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-moss"
          value={arxivId}
          onChange={(event) => setArxivId(event.target.value)}
          placeholder="2401.12345"
        />
        <button className="action-button" type="submit" disabled={fetching}>
          {fetching ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
          拉取
        </button>
      </form>
      <label className="mt-3 flex items-center gap-2 text-sm text-body">
        <input type="checkbox" className="h-4 w-4 accent-moss" checked={andIngest} onChange={(event) => setAndIngest(event.target.checked)} />
        拉取后立即生成 Summary / Prior Works / Pattern
      </label>
      {error ? <div className="mt-4 rounded-lg border border-error-line bg-error-soft p-3 text-sm text-error">{error}</div> : null}
      {status && !error ? <div className="mt-4 rounded-lg border border-line bg-canvas p-3 text-sm text-moss">{status}</div> : null}
    </div>
  )
}
