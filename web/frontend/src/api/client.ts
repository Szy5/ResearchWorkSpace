export type PaperListItem = {
  slug: string
  title: string
  authors: string[]
  abstract: string
  year: number | null
  venue: string
  reviewed: boolean
  updated_at: string
  has_summary: boolean
  has_prior_works: boolean
  has_sci_pattern: boolean
  primary_pattern: string
  primary_pattern_name: string
}

export type PaperMetaDTO = {
  title: string
  authors: string[]
  abstract: string
  year: number | null
  venue: string
  arxiv_id: string
  tags: string[]
  reviewed: boolean
  meta_reviewed: boolean
  prior_works_reviewed: boolean
  added_date: string
  blog_html_path: string | null
  blog_html_generated_at: string | null
}

export type PaperDetail = {
  slug: string
  updated_at: string
  meta: PaperMetaDTO
  summary: string
  prior_works: PriorWorksPayload | null
  sci_pattern: Record<string, unknown> | null
  references_count: number
  figures_count: number
  sections_count: number
}

export type PriorWorksPayload = {
  prior_works: Array<{
    title: string
    authors: string
    year: number | null
    arxiv_id: string
    role: string
    relationship_sentence: string
  }>
  synthesis_narrative: string
}

export type JobResponse = {
  job_id: string
  slug: string
  target: string
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  created_at: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  result: Record<string, unknown> | null
  progress: string | null
}

export type SearchCandidate = {
  title: string
  authors: string[]
  year: number | null
  abstract: string
  url: string
  venue: string
  arxiv_id: string
  citation_count: number | null
  publication_date: string | null
  source: string
  score: number | null
  display_summary?: string
}

export type RankedCandidate = SearchCandidate & { reason: string }

export type RecommendationSnapshot = {
  date: string
  generated_at: string
  corpus_size: number
  candidate_pool_size: number
  candidates: RankedCandidate[]
  degraded: boolean
}

export type FetchResult = {
  slug: string
  raw_dir: string
  entry_file: string
  has_pdf: boolean
  source_file_count: number
}

export type BatchIngestItem = { arxiv_id: string; slug?: undefined } | { slug: string; arxiv_id?: undefined }

export type PublishWeChatPayload = {
  html_path: string
  title?: string
  author?: string
  digest?: string
  cover_path?: string
  thumb_media_id?: string
  save_rendered?: boolean
}

type RequestOptions = {
  method?: string
  body?: unknown
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? 'GET',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(payload.detail ?? response.statusText)
  }
  return response.json() as Promise<T>
}

export function listPapers(params: { reviewed?: boolean; q?: string } = {}) {
  const search = new URLSearchParams()
  if (params.reviewed !== undefined) search.set('reviewed', String(params.reviewed))
  if (params.q) search.set('q', params.q)
  const suffix = search.toString() ? `?${search.toString()}` : ''
  return request<PaperListItem[]>(`/api/papers${suffix}`)
}

export function getPaper(slug: string) {
  return request<PaperDetail>(`/api/papers/${encodeURIComponent(slug)}`)
}

export type PaperMetaEdits = {
  title: string
  authors: string[]
  abstract: string
  year: number | null
  venue: string
  arxiv_id: string
  tags: string[]
}

/** Saves edited meta fields and marks the "meta + summary" review switch as done. */
export function updateMeta(slug: string, expectedUpdatedAt: string, edits: PaperMetaEdits) {
  return request<PaperDetail>(`/api/papers/${encodeURIComponent(slug)}/meta`, {
    method: 'PATCH',
    body: { expected_updated_at: expectedUpdatedAt, ...edits, meta_reviewed: true }
  })
}

/** Marks the "prior works" review switch as done, independent of the meta switch. */
export function markPriorWorksReviewed(slug: string, expectedUpdatedAt: string) {
  return request<PaperDetail>(`/api/papers/${encodeURIComponent(slug)}/meta`, {
    method: 'PATCH',
    body: { expected_updated_at: expectedUpdatedAt, prior_works_reviewed: true }
  })
}

export function updateSummary(slug: string, expectedUpdatedAt: string, summary: string) {
  return request<PaperDetail>(`/api/papers/${encodeURIComponent(slug)}/summary`, {
    method: 'PATCH',
    body: { expected_updated_at: expectedUpdatedAt, summary }
  })
}

export function updatePriorWorks(slug: string, expectedUpdatedAt: string, priorWorks: PriorWorksPayload) {
  return request<PaperDetail>(`/api/papers/${encodeURIComponent(slug)}/prior-works`, {
    method: 'PATCH',
    body: { expected_updated_at: expectedUpdatedAt, ...priorWorks }
  })
}

export function startIngest(slug: string, only: string[] = ['summary'], overwrite = true) {
  return request<JobResponse>(`/api/papers/${encodeURIComponent(slug)}/ingest`, {
    method: 'POST',
    body: { only, overwrite }
  })
}

export function getJob(jobId: string) {
  return request<JobResponse>(`/api/jobs/${encodeURIComponent(jobId)}`)
}

export function publishWeChat(slug: string, payload: PublishWeChatPayload) {
  return request(`/api/papers/${encodeURIComponent(slug)}/publish/wechat`, {
    method: 'POST',
    body: payload
  })
}

export function renderBlogHtml(slug: string, theme?: string) {
  return request<JobResponse>(`/api/papers/${encodeURIComponent(slug)}/blog/render-html`, {
    method: 'POST',
    body: { theme: theme ?? null }
  })
}

export function getRecommendationsToday(date?: string) {
  const suffix = date ? `?date=${encodeURIComponent(date)}` : ''
  return request<RecommendationSnapshot | null>(`/api/recommendations/today${suffix}`)
}

export function refreshRecommendations(params: { max_papers?: number; arxiv_query?: string } = {}) {
  return request<JobResponse>('/api/recommendations/refresh', { method: 'POST', body: params })
}

export function searchPapers(params: { q: string; start_year?: number; end_year?: number; max_results?: number }) {
  const search = new URLSearchParams()
  search.set('q', params.q)
  if (params.start_year) search.set('start_year', String(params.start_year))
  if (params.end_year) search.set('end_year', String(params.end_year))
  if (params.max_results) search.set('max_results', String(params.max_results))
  return request<SearchCandidate[]>(`/api/search?${search.toString()}`)
}

export function fetchPaper(arxivId: string, options: { andIngest?: boolean; overwrite?: boolean } = {}) {
  return request<JobResponse>('/api/papers/fetch', {
    method: 'POST',
    body: { arxiv_id: arxivId, and_ingest: options.andIngest ?? false, overwrite: options.overwrite ?? false }
  })
}

export function batchIngest(items: BatchIngestItem[], overwrite = false) {
  return request<JobResponse[]>('/api/papers/batch-ingest', {
    method: 'POST',
    body: { items, overwrite }
  })
}

/** Poll a job until it reaches a terminal state, calling onUpdate on every tick. */
export function pollJob(jobId: string, onUpdate?: (job: JobResponse) => void, intervalMs = 900): Promise<JobResponse> {
  return new Promise((resolve, reject) => {
    const timer = window.setInterval(() => {
      getJob(jobId)
        .then((job) => {
          onUpdate?.(job)
          if (job.status === 'succeeded' || job.status === 'failed') {
            window.clearInterval(timer)
            resolve(job)
          }
        })
        .catch((err) => {
          window.clearInterval(timer)
          reject(err instanceof Error ? err : new Error(String(err)))
        })
    }, intervalMs)
  })
}
