import { useEffect, useState } from 'react'
import { Check, Edit3, ExternalLink, Plus, Trash2 } from 'lucide-react'
import { PriorWorksPayload } from '../api/client'
import { normalizeQuotes } from '../utils/textFormat'
import ReviewBadge from './ReviewBadge'

type EntryDraft = {
  title: string
  authorsText: string
  year: string
  arxivId: string
  role: string
  relationshipSentence: string
}

type Props = {
  value: PriorWorksPayload | null
  mode: 'preview' | 'edit'
  reviewed: boolean
  onModeChange: (mode: 'preview' | 'edit') => void
  onSave: (payload: PriorWorksPayload) => void
}

function draftsFromValue(value: PriorWorksPayload | null): EntryDraft[] {
  return (value?.prior_works ?? []).map((work) => ({
    title: work.title,
    authorsText: work.authors,
    year: work.year ? String(work.year) : '',
    arxivId: work.arxiv_id,
    role: work.role,
    relationshipSentence: work.relationship_sentence
  }))
}

export default function PriorWorksView({ value, mode, reviewed, onModeChange, onSave }: Props) {
  const works = value?.prior_works ?? []
  const [entries, setEntries] = useState<EntryDraft[]>(() => draftsFromValue(value))

  useEffect(() => {
    if (mode === 'edit') setEntries(draftsFromValue(value))
  }, [mode, value])

  function updateEntry(index: number, patch: Partial<EntryDraft>) {
    setEntries((prev) => prev.map((entry, entryIndex) => (entryIndex === index ? { ...entry, ...patch } : entry)))
  }

  function removeEntry(index: number) {
    setEntries((prev) => prev.filter((_, entryIndex) => entryIndex !== index))
  }

  function addEntry() {
    setEntries((prev) => [
      ...prev,
      { title: '', authorsText: '', year: '', arxivId: '', role: 'Baseline', relationshipSentence: '' }
    ])
  }

  function review() {
    onSave({
      prior_works: entries.map((entry) => ({
        title: entry.title,
        authors: entry.authorsText,
        year: entry.year.trim() ? Number(entry.year) : null,
        arxiv_id: entry.arxivId,
        role: entry.role,
        relationship_sentence: entry.relationshipSentence
      })),
      synthesis_narrative: value?.synthesis_narrative ?? ''
    })
  }

  return (
    <section className="side-panel">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="panel-title">Prior Works</h2>
          <p className="mt-1 text-xs text-body">{works.length} entries</p>
        </div>
        <div className="flex items-center gap-2">
          <ReviewBadge reviewed={reviewed} label="前作" />
          <div className="segmented-control compact" aria-label="Prior works view mode">
            <button className={mode === 'preview' ? 'is-selected' : ''} onClick={() => onModeChange('preview')}>
              Preview
            </button>
            <button className={mode === 'edit' ? 'is-selected' : ''} onClick={() => onModeChange('edit')}>
              <Edit3 size={14} />
              Edit
            </button>
          </div>
        </div>
      </div>
      {mode === 'edit' ? (
        <div className="prior-list">
          {entries.length === 0 ? <div className="text-sm text-body">No prior works yet.</div> : null}
          {entries.map((entry, index) => (
            <article className="prior-card" key={index}>
              <div className="flex items-start justify-between gap-3">
                <input
                  className="w-full rounded-lg border border-line bg-canvas px-2 py-1 text-sm outline-none focus:border-moss"
                  placeholder="Title"
                  value={entry.title}
                  onChange={(event) => updateEntry(index, { title: event.target.value })}
                />
                <button className="icon-button flex-none" title="Remove" onClick={() => removeEntry(index)}>
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2">
                <input
                  className="col-span-2 rounded-lg border border-line bg-canvas px-2 py-1 text-xs outline-none focus:border-moss"
                  placeholder="Authors"
                  value={entry.authorsText}
                  onChange={(event) => updateEntry(index, { authorsText: event.target.value })}
                />
                <input
                  className="rounded-lg border border-line bg-canvas px-2 py-1 text-xs outline-none focus:border-moss"
                  placeholder="Year"
                  type="number"
                  value={entry.year}
                  onChange={(event) => updateEntry(index, { year: event.target.value })}
                />
              </div>
              <input
                className="mt-2 w-full rounded-lg border border-line bg-canvas px-2 py-1 text-xs outline-none focus:border-moss"
                placeholder="arXiv ID"
                value={entry.arxivId}
                onChange={(event) => updateEntry(index, { arxivId: event.target.value })}
              />
              <p className="prior-relationship">
                <span className="role-badge">{entry.role}</span> {normalizeQuotes(entry.relationshipSentence)}
              </p>
            </article>
          ))}
          <button className="action-button w-full justify-center" onClick={addEntry}>
            <Plus size={16} />
            添加新前作
          </button>
          <button className="action-button w-full justify-center" onClick={review}>
            <Check size={16} />
            Review
          </button>
        </div>
      ) : (
        <div className="prior-list">
          {value?.synthesis_narrative ? (
            <div className="prior-synthesis">{normalizeQuotes(value.synthesis_narrative)}</div>
          ) : null}
          {works.length === 0 ? <div className="text-sm text-body">No prior works yet.</div> : null}
          {works.map((work, index) => (
            <article className="prior-card" key={`${work.title}-${index}`}>
              <div className="flex items-start justify-between gap-3">
                <h3>{work.title}</h3>
                <span className="role-badge">{work.role}</span>
              </div>
              <p className="prior-meta">
                {work.authors}
                {work.year ? ` · ${work.year}` : ''}
              </p>
              {work.arxiv_id ? (
                <a
                  className="prior-link"
                  href={`https://arxiv.org/abs/${work.arxiv_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink size={13} />
                  {work.arxiv_id}
                </a>
              ) : null}
              <p className="prior-relationship">{normalizeQuotes(work.relationship_sentence)}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
