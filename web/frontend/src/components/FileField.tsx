import { ChangeEvent, DragEvent, ReactNode, useId, useRef, useState } from 'react'
import { FileText, Image as ImageIcon, Upload, X } from 'lucide-react'

type Props = {
  label: string
  hint?: string
  accept?: string
  multiple?: boolean
  required?: boolean
  files: File[]
  onChange: (files: File[]) => void
  emptyLabel?: string
  icon?: 'file' | 'image'
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileField({
  label,
  hint,
  accept,
  multiple = false,
  required = false,
  files,
  onChange,
  emptyLabel = '点击选择文件，或拖拽到此处',
  icon = 'file'
}: Props) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const Icon = icon === 'image' ? ImageIcon : FileText

  function applyFiles(list: FileList | File[] | null) {
    const next = list ? Array.from(list) : []
    onChange(multiple ? next : next.slice(0, 1))
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    applyFiles(event.target.files)
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    applyFiles(event.dataTransfer.files)
  }

  function clearFile(index: number) {
    const next = files.filter((_, i) => i !== index)
    onChange(next)
    if (inputRef.current) inputRef.current.value = ''
  }

  function clearAll() {
    onChange([])
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="field">
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <label className="field-label mb-0" htmlFor={inputId}>
          {label}
          {required ? <span className="text-moss"> *</span> : null}
        </label>
        {files.length > 0 ? (
          <button type="button" className="text-[11px] font-medium text-muted hover:text-ink" onClick={clearAll}>
            清除
          </button>
        ) : null}
      </div>
      <label
        htmlFor={inputId}
        className={`file-drop ${dragging ? 'is-dragging' : ''} ${files.length > 0 ? 'has-files' : ''}`}
        onDragEnter={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={(event) => {
          event.preventDefault()
          setDragging(false)
        }}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          id={inputId}
          className="sr-only"
          type="file"
          accept={accept}
          multiple={multiple}
          required={required && files.length === 0}
          onChange={onInputChange}
        />
        <div className="flex items-start gap-3">
          <span className="file-drop-icon">
            <Icon size={18} />
          </span>
          <span className="min-w-0 flex-1">
            {files.length === 0 ? (
              <>
                <span className="block text-sm font-medium leading-5 text-ink">{emptyLabel}</span>
                <span className="mt-1 block text-xs leading-5 text-muted">
                  点击选择{multiple ? '多个文件' : '文件'}，或拖放到此处
                </span>
              </>
            ) : (
              <span className="block space-y-2">
                {files.map((file, index) => (
                  <span key={`${file.name}-${index}`} className="flex items-center gap-2 text-sm text-ink">
                    <span className="min-w-0 flex-1 truncate font-medium">{file.name}</span>
                    <span className="flex-none whitespace-nowrap text-xs text-muted">{formatBytes(file.size)}</span>
                    <button
                      type="button"
                      className="inline-flex h-6 w-6 flex-none items-center justify-center rounded-md text-muted hover:bg-fog hover:text-ink"
                      title="移除"
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        clearFile(index)
                      }}
                    >
                      <X size={13} />
                    </button>
                  </span>
                ))}
              </span>
            )}
          </span>
        </div>
        <span className="file-drop-action">
          <Upload size={14} />
          <span>{files.length > 0 ? '更换文件' : '选择文件'}</span>
        </span>
      </label>
      {hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  )
}

export function Field({
  label,
  hint,
  children
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  )
}
