import { ChevronDown, Circle, Filter, Layers3 } from 'lucide-react'
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
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-[22px] font-semibold">My Papers</h1>
          <p className="text-sm text-body">{papers.length} artifacts</p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-body" />
          <div className="relative">
            <select
              className="h-9 appearance-none rounded-lg border border-line bg-canvas py-1 pl-3 pr-8 text-sm outline-none focus:border-moss"
              value={reviewedFilter === undefined ? 'all' : String(reviewedFilter)}
              onChange={(event) => {
                const value = event.target.value
                onReviewedFilter(value === 'all' ? undefined : value === 'true')
              }}
            >
              <option value="all">All</option>
              <option value="false">To review</option>
              <option value="true">Reviewed</option>
            </select>
            <ChevronDown
              size={14}
              className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted"
            />
          </div>
        </div>
      </div>
      {error ? <div className="mb-3 rounded-lg border border-error-line bg-error-soft p-3 text-sm text-error">{error}</div> : null}
      {loading ? <div className="text-sm text-body">Loading...</div> : null}
      <div className="space-y-3">
        {papers.map((paper) => (
          <button
            key={paper.slug}
            className={`paper-card ${selectedSlug === paper.slug ? 'paper-card-active' : ''}`}
            onClick={() => onSelect(paper.slug)}
          >
            <div className="flex items-start gap-3">
              <Circle
                size={13}
                className={paper.reviewed ? 'mt-1 fill-moss text-moss' : 'mt-1 fill-copper text-copper'}
              />
              <div className="min-w-0 flex-1">
                <h2 className="line-clamp-2 text-left font-serif text-[15px] font-semibold">{paper.title}</h2>
                <p className="mt-1 truncate text-left text-xs text-body">{paper.authors.join(', ') || paper.slug}</p>
              </div>
            </div>
            <p className="mt-3 line-clamp-3 text-left text-sm leading-6 text-body">{paper.abstract || 'No abstract'}</p>
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
