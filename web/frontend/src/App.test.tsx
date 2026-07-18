import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import App from './App'

const paper = {
  slug: 'demo-paper',
  title: 'Demo Paper',
  authors: ['Ada Lovelace'],
  abstract: 'A compact demo artifact.',
  year: 2026,
  venue: 'DemoConf',
  reviewed: false,
  updated_at: '2026-07-14T00:00:00+00:00',
  has_summary: true,
  has_prior_works: true,
  has_sci_pattern: true,
  primary_pattern: 'P05',
  primary_pattern_name: 'Data & Evaluation Engineering'
}

describe('App', () => {
  let failSummarySave = false

  beforeEach(() => {
    vi.restoreAllMocks()
    failSummarySave = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([paper])
        }
        if (path === '/api/papers/demo-paper/summary' && init?.method === 'PATCH') {
          if (failSummarySave) {
            return Response.json({ detail: 'manifest was updated by another writer' }, { status: 409 })
          }
          return Response.json({
            slug: paper.slug,
            updated_at: '2026-07-14T00:00:01+00:00',
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nSaved.',
            prior_works: null,
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        if (path === '/api/papers/demo-paper/meta' && init?.method === 'PATCH') {
          const body = JSON.parse(String(init.body))
          return Response.json({
            slug: paper.slug,
            updated_at: '2026-07-14T00:00:02+00:00',
            meta: {
              title: body.title ?? paper.title,
              authors: body.authors ?? paper.authors,
              abstract: body.abstract ?? paper.abstract,
              year: body.year ?? paper.year,
              venue: body.venue ?? paper.venue,
              arxiv_id: body.arxiv_id ?? '',
              tags: [],
              reviewed: Boolean(body.meta_reviewed) && Boolean(body.prior_works_reviewed),
              meta_reviewed: body.meta_reviewed ?? false,
              prior_works_reviewed: body.prior_works_reviewed ?? false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nUseful notes with $E=mc^2$.\n\n![Figure one](assets/figures/demo.png)',
            prior_works: {
              prior_works: [
                {
                  title: 'Prior Demo',
                  authors: 'Turing',
                  year: 2024,
                  arxiv_id: '',
                  role: 'Foundation',
                  relationship_sentence: 'It frames the demo.'
                }
              ],
              synthesis_narrative: 'Prior Demo frames the demo.'
            },
            sci_pattern: {
              primary_pattern: 'P05',
              primary_pattern_name: 'Data & Evaluation Engineering',
              reasoning: 'The work constructs data.'
            },
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        if (path === '/api/papers/demo-paper/prior-works' && init?.method === 'PATCH') {
          const body = JSON.parse(String(init.body))
          return Response.json({
            slug: paper.slug,
            updated_at: '2026-07-14T00:00:01+00:00',
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nUseful notes with $E=mc^2$.\n\n![Figure one](assets/figures/demo.png)',
            prior_works: { prior_works: body.prior_works, synthesis_narrative: body.synthesis_narrative },
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        if (path === '/api/papers/demo-paper') {
          return Response.json({
            slug: paper.slug,
            updated_at: paper.updated_at,
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14'
            },
            summary: '# Demo Paper\n\nUseful notes with $E=mc^2$.\n\n![Figure one](assets/figures/demo.png)',
            prior_works: {
              prior_works: [
                {
                  title: 'Prior Demo',
                  authors: 'Turing',
                  year: 2024,
                  arxiv_id: '',
                  role: 'Foundation',
                  relationship_sentence: 'It frames the demo.'
                }
              ],
              synthesis_narrative: 'Prior Demo frames the demo.'
            },
            sci_pattern: {
              primary_pattern: 'P05',
              primary_pattern_name: 'Data & Evaluation Engineering',
              reasoning: 'The work constructs data.'
            },
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
  })

  test('home page shows today feed by default', async () => {
    render(<App />)
    expect(await screen.findByText('还没有今日推荐快照。')).toBeInTheDocument()
    expect(screen.getAllByText('今日推荐').length).toBeGreaterThan(0)
  })

  test('renders dashboard papers under All Papers', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    expect(await screen.findByText('Demo Paper')).toBeInTheDocument()
    expect(screen.getByText('DemoConf')).toBeInTheDocument()
  })

  test('loads paper detail after selection', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    const card = await screen.findByText('Demo Paper')
    card.click()
    await waitFor(() => expect(screen.getByText(/Useful notes with/)).toBeInTheDocument())
    expect(screen.getByText('P05 Data & Evaluation Engineering')).toBeInTheDocument()
    expect(screen.getByText('Prior Demo')).toBeInTheDocument()
    expect(document.querySelector('.katex')).toBeTruthy()
    const figure = screen.getByRole('img', { name: 'Figure one' })
    expect(figure).toHaveAttribute('src', '/api/papers/demo-paper/files/assets/figures/demo.png')

    expect(document.querySelector('.image-lightbox-backdrop')).toBeNull()
    await user.click(figure)
    expect(document.querySelector('.image-lightbox-backdrop')).not.toBeNull()
  })

  test('generating blog HTML fills the publish path and enables the send button', async () => {
    let jobPolls = 0
    let rendered = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([paper])
        }
        if (path === '/api/papers/demo-paper/blog/render-html' && init?.method === 'POST') {
          return Response.json({
            job_id: 'job-html-1',
            slug: 'demo-paper',
            target: 'render_blog_html',
            status: 'pending',
            created_at: '2026-07-15T00:00:00+00:00',
            started_at: null,
            finished_at: null,
            error: null,
            result: null,
            progress: null
          })
        }
        if (path === '/api/jobs/job-html-1') {
          jobPolls += 1
          if (jobPolls < 2) {
            return Response.json({
              job_id: 'job-html-1',
              slug: 'demo-paper',
              target: 'render_blog_html',
              status: 'running',
              created_at: '2026-07-15T00:00:00+00:00',
              started_at: '2026-07-15T00:00:01+00:00',
              finished_at: null,
              error: null,
              result: null,
              progress: '🎨 正在排版博客 HTML...'
            })
          }
          rendered = true
          return Response.json({
            job_id: 'job-html-1',
            slug: 'demo-paper',
            target: 'render_blog_html',
            status: 'succeeded',
            created_at: '2026-07-15T00:00:00+00:00',
            started_at: '2026-07-15T00:00:01+00:00',
            finished_at: '2026-07-15T00:00:02+00:00',
            error: null,
            result: { slug: 'demo-paper', html_path: 'summary.html' },
            progress: null
          })
        }
        if (path === '/api/papers/demo-paper') {
          return Response.json({
            slug: paper.slug,
            updated_at: paper.updated_at,
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14',
              blog_html_path: rendered ? 'summary.html' : null,
              blog_html_generated_at: rendered ? '2026-07-15T00:00:02+00:00' : null
            },
            summary: '# Demo Paper\n\nUseful notes.',
            prior_works: null,
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes/)

    expect(screen.getByTitle('请先生成 HTML')).toBeDisabled()

    await user.click(screen.getByText('生成 HTML'))
    await screen.findByText('🎨 正在排版博客 HTML...')

    await waitFor(() => expect(screen.getByDisplayValue('summary.html')).toBeInTheDocument(), { timeout: 5000 })
    await waitFor(() => expect(screen.getByTitle('Publish WeChat draft')).not.toBeDisabled(), { timeout: 5000 })
  }, 10000)

  function stubDemoPaperWithBlogHtml(blogHtmlPath: string | null, onPost?: (path: string) => void) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (init?.method === 'POST') onPost?.(path)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([paper])
        }
        if (path === '/api/papers/demo-paper') {
          return Response.json({
            slug: paper.slug,
            updated_at: paper.updated_at,
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14',
              blog_html_path: blogHtmlPath,
              blog_html_generated_at: blogHtmlPath ? '2026-07-15T00:00:00+00:00' : null
            },
            summary: '# Demo Paper\n\nUseful notes.',
            prior_works: null,
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
  }

  test('loading a paper that already has a rendered blog HTML shows its real path, not the blog.html default', async () => {
    stubDemoPaperWithBlogHtml('existing_summary.html')

    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes/)

    expect(screen.getByDisplayValue('existing_summary.html')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('blog.html')).not.toBeInTheDocument()
    expect(screen.getByTitle('Publish WeChat draft')).not.toBeDisabled()
  })

  test('publishing sends the generated html path without exposing a cover-path field', async () => {
    let publishBody: string | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([paper])
        }
        if (path === '/api/papers/demo-paper/publish/wechat' && init?.method === 'POST') {
          publishBody = String(init.body)
          return Response.json({
            slug: 'demo-paper',
            title: 'Demo Paper',
            media_id: 'media-1',
            html_path: 'existing_summary.html',
            thumb_media_id: 'thumb-1',
            uploaded_image_count: 0,
            rendered_html_path: null
          })
        }
        if (path === '/api/papers/demo-paper') {
          return Response.json({
            slug: paper.slug,
            updated_at: paper.updated_at,
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14',
              blog_html_path: 'existing_summary.html',
              blog_html_generated_at: '2026-07-15T00:00:00+00:00'
            },
            summary: '# Demo Paper\n\nUseful notes.',
            prior_works: null,
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )

    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes/)

    expect(screen.queryByPlaceholderText(/封面图路径/)).not.toBeInTheDocument()

    await user.click(screen.getByTitle('Publish WeChat draft'))

    await waitFor(() => expect(publishBody).toBeDefined())
    const parsed = JSON.parse(publishBody as string)
    expect(parsed.html_path).toBe('existing_summary.html')
    expect(parsed.cover_path).toBeUndefined()
    expect(parsed.title).toBe('Demo Paper')
  })

  test('regenerating an already-generated blog HTML asks for confirmation and respects cancel', async () => {
    const postPaths: string[] = []
    stubDemoPaperWithBlogHtml('existing_summary.html', (path) => postPaths.push(path))
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes/)

    await user.click(screen.getByText('生成 HTML'))

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('existing_summary.html'))
    expect(postPaths).not.toContain('/api/papers/demo-paper/blog/render-html')

    confirmSpy.mockRestore()
  })

  test('regenerating an already-generated blog HTML proceeds once confirmed', async () => {
    let jobPolls = 0
    const postPaths: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (init?.method === 'POST') postPaths.push(path)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json(null)
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([paper])
        }
        if (path === '/api/papers/demo-paper/blog/render-html' && init?.method === 'POST') {
          return Response.json({
            job_id: 'job-html-2',
            slug: 'demo-paper',
            target: 'render_blog_html',
            status: 'pending',
            created_at: '2026-07-15T00:00:00+00:00',
            started_at: null,
            finished_at: null,
            error: null,
            result: null,
            progress: null
          })
        }
        if (path === '/api/jobs/job-html-2') {
          jobPolls += 1
          if (jobPolls < 2) {
            return Response.json({
              job_id: 'job-html-2',
              slug: 'demo-paper',
              target: 'render_blog_html',
              status: 'running',
              created_at: '2026-07-15T00:00:00+00:00',
              started_at: '2026-07-15T00:00:01+00:00',
              finished_at: null,
              error: null,
              result: null,
              progress: '🎨 正在排版博客 HTML...'
            })
          }
          return Response.json({
            job_id: 'job-html-2',
            slug: 'demo-paper',
            target: 'render_blog_html',
            status: 'succeeded',
            created_at: '2026-07-15T00:00:00+00:00',
            started_at: '2026-07-15T00:00:01+00:00',
            finished_at: '2026-07-15T00:00:02+00:00',
            error: null,
            result: { slug: 'demo-paper', html_path: 'existing_summary_v2.html' },
            progress: null
          })
        }
        if (path === '/api/papers/demo-paper') {
          return Response.json({
            slug: paper.slug,
            updated_at: paper.updated_at,
            meta: {
              title: paper.title,
              authors: paper.authors,
              abstract: paper.abstract,
              year: paper.year,
              venue: paper.venue,
              arxiv_id: '',
              tags: [],
              reviewed: false,
              meta_reviewed: false,
              prior_works_reviewed: false,
              added_date: '2026-07-14',
              blog_html_path: 'existing_summary.html',
              blog_html_generated_at: '2026-07-15T00:00:00+00:00'
            },
            summary: '# Demo Paper\n\nUseful notes.',
            prior_works: null,
            sci_pattern: null,
            references_count: 1,
            figures_count: 0,
            sections_count: 3
          })
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes/)

    await user.click(screen.getByText('生成 HTML'))

    expect(confirmSpy).toHaveBeenCalled()
    expect(postPaths).toContain('/api/papers/demo-paper/blog/render-html')
    await waitFor(() => expect(screen.getByDisplayValue('existing_summary_v2.html')).toBeInTheDocument(), {
      timeout: 5000
    })

    confirmSpy.mockRestore()
  }, 10000)

  test('shows API errors from review actions', async () => {
    failSummarySave = true
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes with/)

    await user.click(screen.getAllByText('Edit')[1])
    await screen.findByDisplayValue(/Useful notes with/)
    await user.click(screen.getByText('Save summary'))

    expect(await screen.findByText('manifest was updated by another writer')).toBeInTheDocument()
  })

  test('editing and reviewing meta fields marks meta_reviewed and shows a success toast', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes with/)

    await user.click(screen.getAllByText('Edit')[0])
    const titleInput = await screen.findByDisplayValue('Demo Paper')
    await user.clear(titleInput)
    await user.type(titleInput, 'Demo Paper Corrected')
    await user.click(screen.getByText('Review'))

    expect(await screen.findByText('元信息已更新')).toBeInTheDocument()
  })

  test('editing and reviewing prior works marks prior_works_reviewed and shows a success toast', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('全部论文'))
    await user.click(await screen.findByText('Demo Paper'))
    await screen.findByText(/Useful notes with/)

    await user.click(screen.getAllByText('Edit')[2])
    const priorTitleInput = await screen.findByDisplayValue('Prior Demo')
    await user.clear(priorTitleInput)
    await user.type(priorTitleInput, 'Prior Demo Corrected')
    await user.click(screen.getByText('Review'))

    expect(await screen.findByText('前作信息已更新')).toBeInTheDocument()
  })
})

const stagingCandidate = {
  title: 'Attention Is All You Need',
  authors: ['Vaswani'],
  year: 2017,
  abstract: 'A new simple network architecture.',
  url: 'https://arxiv.org/abs/1706.03762',
  venue: '',
  arxiv_id: '1706.03762',
  citation_count: null,
  publication_date: null,
  source: 'arxiv',
  score: 9.1,
  reason: ''
}

function jobResponse(overrides: Record<string, unknown>) {
  return {
    job_id: 'job-1',
    slug: '1706.03762',
    target: 'fetch_and_ingest',
    status: 'pending',
    created_at: '2026-07-14T00:00:00+00:00',
    started_at: null,
    finished_at: null,
    error: null,
    result: null,
    progress: null,
    ...overrides
  }
}

describe('App / generation tray', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  function stubFetch(onJobPoll?: () => Response | Promise<Response>) {
    let jobPolls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const path = String(url)
        if (path.startsWith('/api/recommendations/today')) {
          return Response.json({
            date: '2026-07-14',
            generated_at: '2026-07-14T00:00:00+00:00',
            corpus_size: 1,
            candidate_pool_size: 1,
            candidates: [stagingCandidate],
            degraded: false
          })
        }
        if (path.startsWith('/api/papers?') || path === '/api/papers') {
          return Response.json([])
        }
        if (path === '/api/papers/batch-ingest' && init?.method === 'POST') {
          return Response.json([jobResponse({ status: 'pending' })])
        }
        if (path === '/api/jobs/job-1' && onJobPoll) {
          jobPolls += 1
          return onJobPoll()
        }
        return Response.json({ detail: 'not found' }, { status: 404 })
      })
    )
    return () => jobPolls
  }

  test('staging a candidate and batch-generating it shows progress in the tray', async () => {
    let polls = 0
    stubFetch(() => {
      polls += 1
      if (polls < 2) {
        return Response.json(
          jobResponse({ status: 'running', started_at: '2026-07-14T00:00:01+00:00', progress: '📥 正在下载论文源码...' })
        )
      }
      return Response.json(
        jobResponse({
          status: 'succeeded',
          started_at: '2026-07-14T00:00:01+00:00',
          finished_at: '2026-07-14T00:00:02+00:00',
          result: { slug: '1706.03762' }
        })
      )
    })

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Attention Is All You Need')
    await user.click(screen.getAllByRole('checkbox')[0])

    await waitFor(() => expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0))
    await user.click(screen.getByText('批量生成'))

    await screen.findByText('📥 正在下载论文源码...')
    await waitFor(() => expect(screen.getByText('Done')).toBeInTheDocument(), { timeout: 5000 })
  }, 10000)

  test('staged candidates survive navigating away to another view', async () => {
    stubFetch()

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Attention Is All You Need')
    await user.click(screen.getAllByRole('checkbox')[0])
    await waitFor(() => expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0))

    await user.click(await screen.findByText('全部论文'))
    expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0)

    await user.click(await screen.findByText('首页'))
    expect(screen.getAllByText(/已暂存 1 篇/).length).toBeGreaterThan(0)
  })
})
