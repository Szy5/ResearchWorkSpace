import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState
} from 'react'
import Dialog from '../components/Dialog'

type Blocker = {
  dirty: boolean
  save: () => Promise<void>
  discard: () => void
}
type Guard = {
  register: (id: string, blocker: Blocker | null) => void
  request: (action: () => void) => void
  hasUnsavedChanges: () => boolean
}
const Context = createContext<Guard>({
  register: () => undefined,
  request: (action) => action(),
  hasUnsavedChanges: () => false
})
export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  const blockers = useRef(new Map<string, Blocker>())
  const dirtyBlockers = () =>
    [...blockers.current.values()].filter((blocker) => blocker.dirty)
  const [pending, setPending] = useState<(() => void) | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const hasUnsavedChanges = useCallback(
    () => [...blockers.current.values()].some((blocker) => blocker.dirty),
    []
  )
  const register = useCallback((id: string, next: Blocker | null) => {
    if (next) blockers.current.set(id, next)
    else blockers.current.delete(id)
  }, [])
  const request = useCallback((action: () => void) => {
    if (!dirtyBlockers().length) {
      action()
      return
    }
    setError('')
    setPending(() => action)
  }, [])
  useEffect(() => {
    function beforeUnload(event: BeforeUnloadEvent) {
      if (dirtyBlockers().length) {
        event.preventDefault()
        event.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => window.removeEventListener('beforeunload', beforeUnload)
  }, [])
  async function leave(save: boolean) {
    if (saving) return
    setSaving(true)
    setError('')
    try {
      for (const blocker of dirtyBlockers()) {
        if (save) await blocker.save()
        else blocker.discard()
        blocker.dirty = false
      }
      const action = pending
      setPending(null)
      action?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败，草稿已保留')
    } finally {
      setSaving(false)
    }
  }
  return (
    <Context.Provider value={{ register, request, hasUnsavedChanges }}>
      {children}
      {pending && (
        <Dialog
          title="还有未保存的修改"
          onClose={() => setPending(null)}
          closeDisabled={saving}
        >
          <div className="p-6">
            <p className="text-sm leading-6 text-body">
              保存后继续，或放弃这次修改。保存失败时会保留当前草稿。
            </p>
            {error && (
              <p role="alert" className="alert-error mt-4">
                {error}
              </p>
            )}
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button
                className="action-button"
                disabled={saving}
                onClick={() => setPending(null)}
              >
                继续编辑
              </button>
              <button
                className="action-button"
                disabled={saving}
                onClick={() => void leave(false)}
              >
                放弃修改
              </button>
              <button
                className="button-primary h-9"
                disabled={saving}
                onClick={() => void leave(true)}
              >
                {saving ? '保存中…' : '保存并离开'}
              </button>
            </div>
          </div>
        </Dialog>
      )}
    </Context.Provider>
  )
}
export function useNavigationGuard() {
  return useContext(Context)
}
export function useUnsavedChanges(blocker: Blocker) {
  const { register } = useNavigationGuard()
  const id = useId()
  useLayoutEffect(() => {
    register(id, blocker)
    return () => register(id, null)
  }, [register, id, blocker.dirty, blocker.save, blocker.discard])
}
