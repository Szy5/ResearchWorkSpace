import { ReactElement, useEffect, useState } from 'react'
import { CheckCircle2, FileSearch, RefreshCw, Search, Sparkles } from 'lucide-react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { listPapers, PaperListItem } from './api/client'
import Dashboard from './pages/Dashboard'
import PaperDetail from './pages/PaperDetail'
import Home from './pages/Home'
import SideNav from './components/SideNav'
import GenerationTray from './components/GenerationTray'
import { useBatchGeneration } from './hooks/useBatchGeneration'
import useMediaQuery from './hooks/useMediaQuery'

type View = 'home' | 'papers'

export default function App() {
  const [view, setView] = useState<View>('home')
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [toReviewCount, setToReviewCount] = useState(0)
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [libraryFilter, setLibraryFilter] = useState<boolean | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isDesktop = useMediaQuery('(min-width: 1024px)')
  const { staged, stagedKeys, jobStatus, generating, stage, unstage, generate } = useBatchGeneration()

  async function loadPapers() {
    setLoading(true)
    setError(null)
    try {
      const next = await listPapers({ q: query, reviewed: libraryFilter })
      setPapers(next)
      if (selectedSlug && !next.some((paper) => paper.slug === selectedSlug)) {
        setSelectedSlug(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function loadReviewCount() {
    try {
      const pending = await listPapers({ reviewed: false })
      setToReviewCount(pending.length)
    } catch {
      // Non-critical: leave the previous count in place if this fails.
    }
  }

  useEffect(() => {
    void loadReviewCount()
  }, [])

  useEffect(() => {
    if (view === 'papers') void loadPapers()
  }, [view, libraryFilter])

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void loadPapers()
  }

  function openPapersView(filter: boolean | undefined) {
    setLibraryFilter(filter)
    setView('papers')
  }

  async function onLibraryChanged() {
    await loadPapers()
    await loadReviewCount()
  }

  async function onBatchComplete() {
    await loadReviewCount()
    if (view === 'papers') void loadPapers()
  }

  const navItems: Array<{ key: string; label: string; icon: ReactElement; active: boolean; onClick: () => void }> = [
    { key: 'home', label: '首页', icon: <Sparkles size={16} />, active: view === 'home', onClick: () => setView('home') },
    {
      key: 'papers',
      label: '全部论文',
      icon: <FileSearch size={16} />,
      active: view === 'papers' && libraryFilter === undefined,
      onClick: () => openPapersView(undefined)
    },
    {
      key: 'review',
      label: `待审查 (${toReviewCount})`,
      icon: <CheckCircle2 size={16} />,
      active: view === 'papers' && libraryFilter === false,
      onClick: () => openPapersView(false)
    }
  ]

  return (
    <div className="flex h-screen bg-fog text-ink">
      <SideNav items={navItems} onBrandClick={() => setView('home')} />
      <div className="flex h-full min-w-0 flex-1 flex-col">
        {view === 'papers' ? (
          <div className="flex-none border-b border-line bg-canvas px-5 py-3">
            <form className="flex w-full max-w-md items-center gap-2" onSubmit={submitSearch}>
              <label className="relative flex-1">
                <Search size={16} className="pointer-events-none absolute left-3 top-2.5 text-muted" />
                <input
                  className="h-10 w-full rounded-lg border border-line bg-canvas pl-9 pr-3 text-sm outline-none focus:border-moss"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search papers"
                />
              </label>
              <button className="icon-button" title="Refresh papers" type="submit">
                <RefreshCw size={17} />
              </button>
            </form>
          </div>
        ) : null}
        <main
          className={`min-h-0 flex-1 px-5 py-5 ${view === 'home' ? 'overflow-y-auto' : 'overflow-y-auto lg:overflow-hidden'}`}
        >
          {view === 'home' ? (
            <Home
              stagedKeys={stagedKeys}
              onStage={stage}
              onIngested={(slug) => {
                void onBatchComplete()
                setLibraryFilter(false)
                setView('papers')
                setSelectedSlug(slug)
              }}
            />
          ) : null}
          {view === 'papers' ? (
            isDesktop ? (
              <Group
                className="workbench-panels overflow-hidden"
                defaultLayout={{ 'paper-list': 400, 'paper-detail': 1200 }}
                orientation="horizontal"
              >
                <Panel id="paper-list" className="h-full overflow-hidden" defaultSize={400} minSize={320} maxSize={560}>
                  <Dashboard
                    error={error}
                    loading={loading}
                    papers={papers}
                    selectedSlug={selectedSlug}
                    onSelect={setSelectedSlug}
                    reviewedFilter={libraryFilter}
                    onReviewedFilter={setLibraryFilter}
                  />
                </Panel>
                <Separator className="resize-handle" />
                <Panel id="paper-detail" className="h-full overflow-hidden" minSize={640}>
                  <PaperDetail slug={selectedSlug} onChanged={onLibraryChanged} />
                </Panel>
              </Group>
            ) : (
              <div className="workbench-stack">
                <Dashboard
                  error={error}
                  loading={loading}
                  papers={papers}
                  selectedSlug={selectedSlug}
                  onSelect={setSelectedSlug}
                  reviewedFilter={libraryFilter}
                  onReviewedFilter={setLibraryFilter}
                />
                <PaperDetail slug={selectedSlug} onChanged={onLibraryChanged} />
              </div>
            )
          ) : null}
        </main>
      </div>
      <GenerationTray
        staged={staged}
        jobStatus={jobStatus}
        generating={generating}
        onUnstage={unstage}
        onGenerate={() => void generate(onBatchComplete)}
      />
    </div>
  )
}
