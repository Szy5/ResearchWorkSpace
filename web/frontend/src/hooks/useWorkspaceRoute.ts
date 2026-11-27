import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigationGuard } from '../context/NavigationGuard'
export type WorkspaceRoute = {
  view: 'home' | 'papers' | 'manage' | 'publish'
  slug?: string
  q?: string
  document?: string
  reviewed?: boolean
}
export function parseRoute(hash = window.location.hash): WorkspaceRoute {
  try {
    const [path, search = ''] = hash.replace(/^#\/?/, '').split('?')
    const parts = path.split('/')
    const params = new URLSearchParams(search)
    const view = ['papers', 'manage', 'publish'].includes(parts[0])
      ? (parts[0] as WorkspaceRoute['view'])
      : 'home'
    return {
      view,
      slug: parts[1] ? decodeURIComponent(parts[1]) : undefined,
      q: params.get('q') || undefined,
      document: params.get('document') || undefined,
      reviewed: params.has('reviewed')
        ? params.get('reviewed') === 'true'
        : undefined
    }
  } catch {
    return { view: 'home' }
  }
}
export function routeHash(route: WorkspaceRoute) {
  const params = new URLSearchParams()
  if (route.q) params.set('q', route.q)
  if (route.document) params.set('document', route.document)
  if (route.reviewed !== undefined)
    params.set('reviewed', String(route.reviewed))
  const search = params.toString()
  return `#/${route.view}${route.slug ? `/${encodeURIComponent(route.slug)}` : ''}${search ? `?${search}` : ''}`
}
const historyState = (index: number) => ({
  ...window.history.state,
  paperWikiIndex: index
})
export default function useWorkspaceRoute() {
  const [route, setRoute] = useState(parseRoute)
  const current = useRef({
    hash: routeHash(route),
    index: Number(window.history.state?.paperWikiIndex) || 0
  })
  const restoring = useRef<{ delta: number } | null>(null)
  const { request, hasUnsavedChanges } = useNavigationGuard()
  const navigate = useCallback(
    (next: WorkspaceRoute, replace = false) => {
      const apply = () => {
        const hash = routeHash(next)
        if (hash !== current.current.hash) {
          const index = current.current.index + (replace ? 0 : 1)
          window.history[replace ? 'replaceState' : 'pushState'](
            historyState(index),
            '',
            hash
          )
          current.current = { hash, index }
        }
        setRoute(next)
      }
      const previous = parseRoute(current.current.hash)
      if (
        previous.view === next.view &&
        previous.slug === next.slug &&
        previous.document === next.document
      )
        apply()
      else request(apply)
    },
    [request]
  )
  useEffect(() => {
    window.history.replaceState(
      historyState(current.current.index),
      '',
      current.current.hash
    )
    function onPopState() {
      if (restoring.current) {
        const { delta } = restoring.current
        restoring.current = null
        // Restore the original history entry before asking. Cancelling preserves the back stack.
        request(() => window.history.go(delta))
        return
      }
      const next = parseRoute()
      const hash = routeHash(next)
      if (hash === current.current.hash) {
        if (typeof window.history.state?.paperWikiIndex === 'number')
          current.current.index = window.history.state.paperWikiIndex
        return
      }
      const stateIndex = window.history.state?.paperWikiIndex
      const index =
        typeof stateIndex === 'number' ? stateIndex : current.current.index + 1
      if (typeof stateIndex !== 'number')
        window.history.replaceState(historyState(index), '', hash)
      const delta = index - current.current.index
      if (hasUnsavedChanges() && delta !== 0) {
        restoring.current = { delta }
        window.history.go(-delta)
        return
      }
      current.current = { hash, index }
      setRoute(next)
    }
    function onHashChange() {
      if (!restoring.current) onPopState()
    }
    window.addEventListener('popstate', onPopState)
    window.addEventListener('hashchange', onHashChange)
    return () => {
      window.removeEventListener('popstate', onPopState)
      window.removeEventListener('hashchange', onHashChange)
    }
  }, [request, hasUnsavedChanges])
  return { route, navigate }
}
