import { ReactNode, useEffect, useId, useRef } from 'react'
import { X } from 'lucide-react'

type Props = {
  title: string
  children: ReactNode
  onClose: () => void
  className?: string
  closeDisabled?: boolean
}
export default function Dialog({
  title,
  children,
  onClose,
  className = '',
  closeDisabled = false
}: Props) {
  const id = useId()
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const focusable = () => [
      ...(panel.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex="0"]'
      ) ?? [])
    ]
    ;(focusable()[0] ?? panel.current)?.focus()
    function handle(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        if (!closeDisabled) close.current()
      }
      if (event.key === 'Tab') {
        const elements = focusable()
        const first = elements[0],
          last = elements[elements.length - 1]
        if (!first) {
          event.preventDefault()
          panel.current?.focus()
          return
        }
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === panel.current)
        ) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handle)
    return () => {
      document.removeEventListener('keydown', handle)
      if (previous?.isConnected) previous.focus()
    }
  }, [closeDisabled])
  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !closeDisabled) onClose()
      }}
    >
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        className={`dialog-panel ${className}`}
      >
        <header className="dialog-header">
          <h2 id={id}>{title}</h2>
          <button
            className="icon-button"
            aria-label="关闭面板"
            disabled={closeDisabled}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {children}
      </div>
    </div>
  )
}
