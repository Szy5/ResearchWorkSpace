import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Circle, ExternalLink, History, Loader2, RefreshCw } from 'lucide-react'
import { JobResponse, PaperListItem, batchReview, listJobs, listPapers } from '../api/client'
import SelectField from '../components/SelectField'

type Props = {
  onOpenPaper: (slug: string) => void
  onChanged: () => void
}

export default function Management({ onOpenPaper, onChanged }: Props) {
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [jobs, setJobs] = useState<JobResponse[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [patternFilter, setPatternFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [nextPapers, nextJobs] = await Promise.all([listPapers(), listJobs({ limit: 100 })])
      setPapers(nextPapers)
      setJobs(nextJobs)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const patterns = useMemo(
    () => Array.from(new Set(papers.map((paper) => paper.primary_pattern).filter(Boolean))).sort(),
    [papers]
  )
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return papers.filter((paper) => {
      const matchesQuery = !needle || `${paper.title} ${paper.slug} ${paper.authors.join(' ')}`.toLowerCase().includes(needle)
      const matchesStatus = statusFilter === 'all' || String(paper.reviewed) === statusFilter
      const matchesPattern = patternFilter === 'all' || paper.primary_pattern === patternFilter
      return matchesQuery && matchesStatus && matchesPattern
    })
  }, [papers, patternFilter, query, statusFilter])

  async function setBatchReviewed(reviewed: boolean) {
    if (selected.size === 0) return
    setSaving(true)
    setError(null)
    try {
      await batchReview(Array.from(selected), reviewed)
      setSelected(new Set())
      await load()
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  function toggleAll() {
    const allSelected = visible.length > 0 && visible.every((paper) => selected.has(paper.slug))
    setSelected(allSelected ? new Set() : new Set(visible.map((paper) => paper.slug)))
  }

  return (
    <section className="mx-auto max-w-7xl space-y-6 animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="page-kicker">Manage</p>
          <h1 className="page-title mt-1">Paper 管理</h1>
          <p className="page-subtitle">集中筛选、批量审查论文，并查看所有后台任务。</p>
        </div>
        <button className="action-button" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      {error ? <div className="alert-error">{error}</div> : null}

      <section className="surface-card overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-line/80 p-4">
          <input
            className="field-input min-w-56 flex-1"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索标题、作者或 slug"
          />
          <SelectField
            className="w-auto min-w-[8.5rem]"
            ariaLabel="按审查状态筛选"
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'all', label: '全部状态' },
              { value: 'false', label: '待审查' },
              { value: 'true', label: '已审查' }
            ]}
          />
          <SelectField
            className="w-auto min-w-[9rem]"
            ariaLabel="按 Pattern 筛选"
            value={patternFilter}
            onChange={setPatternFilter}
            options={[
              { value: 'all', label: '全部 Pattern' },
              ...patterns.map((pattern) => ({ value: pattern, label: pattern }))
            ]}
          />
          <button className="button-primary h-10" disabled={saving || selected.size === 0} onClick={() => void setBatchReviewed(true)}>
            标记已审查
          </button>
          <button className="action-button h-10" disabled={saving || selected.size === 0} onClick={() => void setBatchReviewed(false)}>
            退回待审查
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    className="check"
                    aria-label="选择全部论文"
                    checked={visible.length > 0 && visible.every((paper) => selected.has(paper.slug))}
                    onChange={toggleAll}
                  />
                </th>
                <th>论文</th>
                <th>年份/会议</th>
                <th>Pattern</th>
                <th>产物</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((paper) => (
                <tr key={paper.slug}>
                  <td>
                    <input
                      type="checkbox"
                      className="check"
                      aria-label={`选择 ${paper.title}`}
                      checked={selected.has(paper.slug)}
                      onChange={() =>
                        setSelected((prev) => {
                          const next = new Set(prev)
                          next.has(paper.slug) ? next.delete(paper.slug) : next.add(paper.slug)
                          return next
                        })
                      }
                    />
                  </td>
                  <td className="max-w-md">
                    <p className="font-serif text-[15px] font-medium tracking-tight">{paper.title}</p>
                    <p className="mt-1 truncate text-xs text-body">{paper.authors.join(', ') || paper.slug}</p>
                  </td>
                  <td className="text-body">{[paper.year, paper.venue].filter(Boolean).join(' · ') || '—'}</td>
                  <td>{paper.primary_pattern || '—'}</td>
                  <td className="text-xs text-body">
                    {[paper.has_summary && 'Summary', paper.has_prior_works && 'Prior Works', paper.has_sci_pattern && 'Pattern']
                      .filter(Boolean)
                      .join(' · ') || '—'}
                  </td>
                  <td>
                    {paper.reviewed ? (
                      <span className="inline-flex items-center gap-1 text-moss">
                        <CheckCircle2 size={14} />
                        已审查
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-copper">
                        <Circle size={14} />
                        待审查
                      </span>
                    )}
                  </td>
                  <td>
                    <button className="action-button" onClick={() => onOpenPaper(paper.slug)}>
                      <ExternalLink size={14} />
                      打开
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading ? (
          <div className="flex items-center gap-2 border-t border-line/80 p-4 text-sm text-body">
            <Loader2 size={16} className="animate-spin" />
            加载中
          </div>
        ) : null}
        {!loading && visible.length === 0 ? (
          <div className="border-t border-line/80 px-4 py-10 text-center text-sm text-body">没有匹配的论文。</div>
        ) : null}
      </section>

      <section className="surface-card overflow-hidden">
        <div className="flex items-center gap-2 border-b border-line/80 px-4 py-4">
          <History size={17} className="text-moss" />
          <div>
            <p className="panel-title">History</p>
            <h2 className="font-serif text-xl font-medium tracking-tight">任务历史</h2>
          </div>
        </div>
        <div className="max-h-96 overflow-auto">
          <table className="data-table min-w-[760px]">
            <thead className="sticky top-0">
              <tr>
                <th>时间</th>
                <th>对象</th>
                <th>任务</th>
                <th>状态</th>
                <th>进度/错误</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td className="whitespace-nowrap text-xs text-body">{new Date(job.created_at).toLocaleString()}</td>
                  <td>{job.slug}</td>
                  <td>{job.target}</td>
                  <td>
                    <span
                      className={`badge ${job.status === 'failed' ? 'border-error-line bg-error-soft text-error' : job.status === 'succeeded' ? 'border-moss/20 bg-moss-soft text-moss' : 'border-copper/30 bg-copper-soft text-copper'}`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="max-w-xl text-xs text-body">{job.error || job.progress || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && jobs.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-body">还没有任务记录。</div>
          ) : null}
        </div>
      </section>
    </section>
  )
}
