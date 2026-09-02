import { Circle, Filter, Layers3 } from 'lucide-react'
import { PaperListItem } from '../api/client'

type Props = {
  papers: PaperListItem[]
  selectedSlug: string | null
  loading: boolean
  error: string | null
  reviewedFilter: boolean | undefined
  onSelect: (slug: string) => void
  onReviewedFilter: (reviewed: boolean | undefined) => void
}

export default function Dashboard({
  papers,
  selectedSlug,
  loading,
  error,
  reviewedFilter,
  onSelect,
  onReviewedFilter
}: Props) {
  return (
    <section className="min-h-[calc(100vh-112px)] border-r border-line pr-0 lg:h-full lg:min-h-0 lg:overflow-y-auto lg:pr-5">
      <div className="mb-5 flex items-end justify-between gap-3">
        <div>
          <p className="page-kicker">Library</p>
          <h1 className="mt-1 font-serif text-[24px] font-medium tracking-tight">我的论文</h1>
          <p className="mt-1 text-sm text-body">{papers.length} 篇产物</p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-muted" />
          <div className="relative">
            <select
              className="field-select h-9 w-auto min-w-[7.5rem]"
              value={reviewedFilter === undefined ? 'all' : String(reviewedFilter)}
              onChange={(event) => {
                const value = event.target.value
                onReviewedFilter(value === 'all' ? undefined : value === 'true')
              }}
            >
              <option value="all">全部</option>
              <option value="false">待审查</option>
              <option value="true">已审查</option>
            </select>
          </div>
        </div>
      </div>
      {error ? <div className="alert-error mb-3">{error}</div> : null}
      {loading ? <div className="text-sm text-body">加载中...</div> : null}
      {!loading && papers.length === 0 ? (
        <div className="empty-state">
          <p className="font-serif text-lg font-medium tracking-tight">书架还是空的</p>
          <p className="mt-2 text-sm text-body">去首页搜索或添加 arXiv 论文，开始积累。</p>
        </div>
      ) : null}
      <div className="space-y-3">
        {papers.map((paper) => (
          <button
            key={paper.slug}
            className={`paper-card ${selectedSlug === paper.slug ? 'paper-card-active' : ''}`}
            onClick={() => onSelect(paper.slug)}
          >
            <div className="flex items-start gap-3">
              <Circle
                size={11}
                className={paper.reviewed ? 'mt-1.5 fill-moss text-moss' : 'mt-1.5 fill-copper text-copper'}
              />
              <div className="min-w-0 flex-1">
                <h2 className="line-clamp-2 text-left font-serif text-[16px] font-medium tracking-tight">{paper.title}</h2>
                <p className="mt-1 truncate text-left text-xs text-body">{paper.authors.join(', ') || paper.slug}</p>
              </div>
            </div>
            <p className="mt-3 line-clamp-3 text-left text-sm leading-6 text-body">{paper.abstract || '暂无摘要'}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              {paper.venue ? <span className="badge">{paper.venue}</span> : null}
              {paper.year ? <span className="badge">{paper.year}</span> : null}
              {paper.primary_pattern ? (
                <span className="badge badge-pattern">
                  <Layers3 size={12} />
                  {paper.primary_pattern}
                </span>
              ) : null}
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}
