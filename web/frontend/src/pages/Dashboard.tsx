import { useRef } from 'react'
import { CheckCircle2, FileText, Search } from 'lucide-react'
import { PaperListItem } from '../api/client'
import useScrollMemory from '../hooks/useScrollMemory'
type Props = {
  papers: PaperListItem[]
  selectedSlug: string | null
  loading: boolean
  error: string | null
  reviewedFilter: boolean | undefined
  onSelect: (slug: string) => void
  onReviewedFilter: (reviewed: boolean | undefined) => void
  query?: string
  onQuery?: (query: string) => void
  onRetry?: () => void
}
export default function Dashboard({
  papers,
  selectedSlug,
  loading,
  error,
  reviewedFilter,
  onSelect,
  onReviewedFilter,
  query = '',
  onQuery,
  onRetry
}: Props) {
  const list = useRef<HTMLDivElement>(null)
  useScrollMemory(
    list,
    `paper-wiki.library-scroll.${query}.${reviewedFilter}`,
    !loading
  )
  return (
    <section className="library-panel" aria-label="论文库">
      <header className="library-header">
        <p className="eyebrow">YOUR LIBRARY</p>
        <h1>
          论文库 <span>{papers.length}</span>
        </h1>
        <label className="library-search">
          <Search size={15} />
          <input
            aria-label="搜索我的论文"
            placeholder="搜索标题、作者或 ID"
            value={query}
            onChange={(e) => onQuery?.(e.target.value)}
          />
        </label>
        <div className="library-filters" aria-label="核验筛选">
          {[
            { label: '全部', value: undefined },
            { label: '待核验', value: false },
            { label: '已核验', value: true }
          ].map((item) => (
            <button
              key={item.label}
              aria-pressed={reviewedFilter === item.value}
              className={reviewedFilter === item.value ? 'is-selected' : ''}
              onClick={() => onReviewedFilter(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </header>
      {error && (
        <div role="alert" className="alert-error m-3">
          {error}
          <button className="ml-2 underline" onClick={onRetry}>
            重试
          </button>
        </div>
      )}
      <div ref={list} className="library-list" aria-busy={loading}>
        {loading && !papers.length ? (
          <div className="p-4 text-sm text-body">加载论文中…</div>
        ) : !papers.length ? (
          <div className="px-5 py-12 text-center">
            <FileText size={25} className="mx-auto mb-4 text-muted" />
            <p className="text-sm">
              {query || reviewedFilter !== undefined
                ? '没有符合条件的论文'
                : '从第一篇论文开始'}
            </p>
            <p className="mt-2 text-xs leading-6 text-body">
              {query || reviewedFilter !== undefined
                ? '调整搜索词或核验筛选后再试。'
                : '去发现页搜索或添加 arXiv 论文。'}
            </p>
          </div>
        ) : (
          papers.map((paper) => (
            <button
              key={paper.slug}
              className={`library-item ${selectedSlug === paper.slug ? 'is-selected' : ''}`}
              aria-current={selectedSlug === paper.slug ? 'true' : undefined}
              onClick={() => onSelect(paper.slug)}
            >
              <div className="flex items-start gap-2">
                <h2>{paper.title}</h2>
                {paper.reviewed && (
                  <CheckCircle2
                    className="mt-1 flex-none text-moss"
                    size={13}
                    aria-label="已核验"
                  />
                )}
              </div>
              <p className="mt-2 truncate text-xs text-muted">
                {paper.authors.slice(0, 2).join(', ') || paper.slug}
                {paper.year ? ` · ${paper.year}` : ''}
              </p>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-body">
                {paper.abstract || '打开查看精读笔记'}
              </p>
              <div className="mt-3 flex items-center gap-2 text-[10px] text-muted">
                {paper.venue && <span>{paper.venue}</span>}
                <span>{paper.reviewed ? '已核验' : '待核验'}</span>
                {paper.primary_pattern && (
                  <span className="ml-auto">{paper.primary_pattern}</span>
                )}
              </div>
            </button>
          ))
        )}
      </div>
    </section>
  )
}
