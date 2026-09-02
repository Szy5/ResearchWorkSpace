import { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

export type SelectOption = {
  value: string
  label: string
}

type Props = {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  className?: string
  ariaLabel?: string
  disabled?: boolean
}

export default function SelectField({ value, onChange, options, className = '', ariaLabel, disabled }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const listId = useId()
  const selected = options.find((option) => option.value === value) ?? options[0]

  useEffect(() => {
    if (!open) return
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        className="field-select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="truncate">{selected?.label ?? value}</span>
        <ChevronDown size={15} className={`flex-none text-muted transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? (
        <ul
          id={listId}
          role="listbox"
          className="field-select-menu"
          aria-activedescendant={`opt-${selected?.value}`}
        >
          {options.map((option) => {
            const active = option.value === value
            return (
              <li key={option.value} role="option" aria-selected={active} id={`opt-${option.value}`}>
                <button
                  type="button"
                  className={`field-select-option ${active ? 'is-active' : ''}`}
                  onClick={() => {
                    onChange(option.value)
                    setOpen(false)
                  }}
                >
                  <span className="truncate">{option.label}</span>
                  {active ? <Check size={14} className="flex-none text-moss" /> : null}
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
