import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Circle, ExternalLink, History, Loader2, RefreshCw } from 'lucide-react'
import { JobResponse, PaperListItem, batchReview, listJobs, listPapers } from '../api/client'

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
    <section className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-serif text-[26px] font-semibold">Paper 管理</h1>
          <p className="mt-1 text-sm text-body">集中筛选、批量审查论文，并查看所有后台任务。</p>
        </div>
        <button className="action-button" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />刷新
        </button>
      </div>

      {error ? <div className="rounded-lg border border-error-line bg-error-soft p-3 text-sm text-error">{error}</div> : null}

      <section className="rounded-xl border border-line bg-canvas">
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-4">
          <input className="h-9 min-w-56 flex-1 rounded-lg border border-line px-3 text-sm outline-none focus:border-moss" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索标题、作者或 slug" />
          <select className="h-9 rounded-lg border border-line bg-canvas px-3 text-sm" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部状态</option><option value="false">待审查</option><option value="true">已审查</option>
          </select>
          <select className="h-9 rounded-lg border border-line bg-canvas px-3 text-sm" value={patternFilter} onChange={(event) => setPatternFilter(event.target.value)}>
            <option value="all">全部 Pattern</option>
            {patterns.map((pattern) => <option key={pattern} value={pattern}>{pattern}</option>)}
          </select>
          <button className="action-button" disabled={saving || selected.size === 0} onClick={() => void setBatchReviewed(true)}>标记已审查</button>
          <button className="action-button" disabled={saving || selected.size === 0} onClick={() => void setBatchReviewed(false)}>退回待审查</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-fog text-xs text-body">
              <tr><th className="p-3"><input type="checkbox" aria-label="选择全部论文" checked={visible.length > 0 && visible.every((paper) => selected.has(paper.slug))} onChange={toggleAll} /></th><th className="p-3">论文</th><th className="p-3">年份/会议</th><th className="p-3">Pattern</th><th className="p-3">产物</th><th className="p-3">状态</th><th className="p-3">操作</th></tr>
            </thead>
            <tbody>
              {visible.map((paper) => (
                <tr key={paper.slug} className="border-t border-line align-top">
                  <td className="p-3"><input type="checkbox" aria-label={`选择 ${paper.title}`} checked={selected.has(paper.slug)} onChange={() => setSelected((prev) => { const next = new Set(prev); next.has(paper.slug) ? next.delete(paper.slug) : next.add(paper.slug); return next })} /></td>
                  <td className="max-w-md p-3"><p className="font-serif font-semibold">{paper.title}</p><p className="mt-1 truncate text-xs text-body">{paper.authors.join(', ') || paper.slug}</p></td>
                  <td className="p-3 text-body">{[paper.year, paper.venue].filter(Boolean).join(' · ') || '—'}</td>
                  <td className="p-3">{paper.primary_pattern || '—'}</td>
                  <td className="p-3 text-xs text-body">{[paper.has_summary && 'Summary', paper.has_prior_works && 'Prior Works', paper.has_sci_pattern && 'Pattern'].filter(Boolean).join(' · ') || '—'}</td>
                  <td className="p-3">{paper.reviewed ? <span className="inline-flex items-center gap-1 text-moss"><CheckCircle2 size={14} />已审查</span> : <span className="inline-flex items-center gap-1 text-copper"><Circle size={14} />待审查</span>}</td>
                  <td className="p-3"><button className="action-button" onClick={() => onOpenPaper(paper.slug)}><ExternalLink size={14} />打开</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading ? <div className="flex items-center gap-2 p-4 text-sm text-body"><Loader2 size={16} className="animate-spin" />加载中</div> : null}
      </section>

      <section className="rounded-xl border border-line bg-canvas">
        <div className="flex items-center gap-2 border-b border-line p-4"><History size={17} className="text-moss" /><h2 className="font-serif text-lg font-semibold">任务历史</h2></div>
        <div className="max-h-96 overflow-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="sticky top-0 bg-fog text-xs text-body"><tr><th className="p-3">时间</th><th className="p-3">对象</th><th className="p-3">任务</th><th className="p-3">状态</th><th className="p-3">进度/错误</th></tr></thead>
            <tbody>{jobs.map((job) => <tr key={job.job_id} className="border-t border-line"><td className="whitespace-nowrap p-3 text-xs text-body">{new Date(job.created_at).toLocaleString()}</td><td className="p-3">{job.slug}</td><td className="p-3">{job.target}</td><td className="p-3"><span className={`badge ${job.status === 'failed' ? 'text-error' : job.status === 'succeeded' ? 'text-moss' : 'text-copper'}`}>{job.status}</span></td><td className="max-w-xl p-3 text-xs text-body">{job.error || job.progress || '—'}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </section>
  )
}
