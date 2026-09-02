import { ReactElement, useEffect, useRef, useState } from 'react'
import { CheckCircle2, FileSearch, RefreshCw, Search, Send, Settings, Sparkles } from 'lucide-react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { listPapers, PaperListItem } from './api/client'
import Dashboard from './pages/Dashboard'
import PaperDetail from './pages/PaperDetail'
import Home from './pages/Home'
import Management from './pages/Management'
import MarkdownPublisher from './pages/MarkdownPublisher'
import SideNav from './components/SideNav'
import ActivityDrawer from './components/ActivityDrawer'
import { useBatchGeneration } from './hooks/useBatchGeneration'
import { useActivityJobs } from './hooks/useActivityJobs'
import useMediaQuery from './hooks/useMediaQuery'

type View = 'home' | 'papers' | 'manage' | 'publish'

export default function App() {
  const [view, setView] = useState<View>('home')
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [toReviewCount, setToReviewCount] = useState(0)
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [libraryFilter, setLibraryFilter] = useState<boolean | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activityOpen, setActivityOpen] = useState(false)
  const isDesktop = useMediaQuery('(min-width: 1024px)')
  const { staged, stagedKeys, jobStatus, generating, stage, unstage, generate } = useBatchGeneration()
  const { activeJobs, recentJobs, dismissJob, dismissAllRecent, refresh: refreshJobs } = useActivityJobs()
  const prevStagedCount = useRef(staged.length)

  useEffect(() => {
    if (generating) void refreshJobs()
  }, [generating, refreshJobs])

  // Only auto-open when the user adds to the staging list — never keep/reopen the drawer
  // just because staged items still exist after a page switch.
  useEffect(() => {
    if (staged.length > prevStagedCount.current) setActivityOpen(true)
    prevStagedCount.current = staged.length
  }, [staged.length])

  function goHome() {
    setActivityOpen(false)
    setView('home')
  }

  function goView(next: View) {
    setActivityOpen(false)
    setView(next)
  }

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
    setActivityOpen(false)
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

  const activityCount = activeJobs.length + staged.length
  const navItems: Array<{ key: string; label: string; icon: ReactElement; active: boolean; onClick: () => void }> = [
    { key: 'home', label: '首页', icon: <Sparkles size={16} />, active: view === 'home', onClick: goHome },
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
    },
    { key: 'publish', label: '公众号发布', icon: <Send size={16} />, active: view === 'publish', onClick: () => goView('publish') },
    { key: 'manage', label: '管理', icon: <Settings size={16} />, active: view === 'manage', onClick: () => goView('manage') }
  ]

  return (
    <div className="app-shell flex h-screen text-ink">
      <SideNav
        items={navItems}
        onBrandClick={goHome}
        activityCount={activityCount}
        activityActive={activeJobs.length > 0 || generating}
        onOpenActivity={() => setActivityOpen(true)}
      />
      <div className="flex h-full min-w-0 flex-1 flex-col">
        {view === 'papers' ? (
          <div className="flex-none border-b border-line bg-canvas/90 px-5 py-3.5 backdrop-blur-md">
            <form className="flex w-full max-w-lg items-center gap-2" onSubmit={submitSearch}>
              <label className="relative flex-1">
                <Search size={16} className="pointer-events-none absolute left-3.5 top-3 text-muted" />
                <input
                  className="h-11 w-full rounded-lg border border-line bg-canvas pl-10 pr-3 text-sm outline-none transition focus:border-moss/55 focus:shadow-soft"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索标题、作者或 slug"
                />
              </label>
              <button className="icon-button" title="Refresh papers" type="submit">
                <RefreshCw size={17} />
              </button>
            </form>
          </div>
        ) : null}
        <main
          className={`min-h-0 flex-1 px-5 py-6 lg:px-7 ${view === 'papers' ? 'overflow-y-auto lg:overflow-hidden' : 'overflow-y-auto'}`}
        >
          {view === 'home' ? (
            <Home
              stagedKeys={stagedKeys}
              onStage={stage}
              onIngested={(slug) => {
                void onBatchComplete()
                setActivityOpen(false)
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
          {view === 'publish' ? <MarkdownPublisher /> : null}
          {view === 'manage' ? (
            <Management
              onChanged={() => void loadReviewCount()}
              onOpenPaper={(slug) => {
                setActivityOpen(false)
                setLibraryFilter(undefined)
                setSelectedSlug(slug)
                setView('papers')
              }}
            />
          ) : null}
        </main>
      </div>
      <ActivityDrawer
        open={activityOpen}
        onClose={() => setActivityOpen(false)}
        staged={staged}
        jobStatus={jobStatus}
        generating={generating}
        activeJobs={activeJobs}
        recentJobs={recentJobs}
        onUnstage={unstage}
        onGenerate={() => void generate(onBatchComplete)}
        onDismissJob={dismissJob}
        onDismissAllRecent={dismissAllRecent}
        onOpenManage={() => goView('manage')}
      />
    </div>
  )
}
