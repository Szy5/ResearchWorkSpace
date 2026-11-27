import { ExternalLink, Plus, Trash2 } from 'lucide-react'
import { PriorWorksPayload } from '../api/client'
import { normalizeQuotes } from '../utils/textFormat'
type Props = {
  value: PriorWorksPayload | null
  editing?: boolean
  onChange?: (value: PriorWorksPayload) => void
}
export default function PriorWorksView({ value, editing, onChange }: Props) {
  const doc = value || { prior_works: [], synthesis_narrative: '' }
  function change(
    index: number,
    patch: Partial<PriorWorksPayload['prior_works'][number]>
  ) {
    onChange?.({
      ...doc,
      prior_works: doc.prior_works.map((work, i) =>
        i === index ? { ...work, ...patch } : work
      )
    })
  }
  return (
    <div className="prior-list">
      {editing ? (
        <label className="field">
          <span className="field-label">前作综合分析</span>
          <textarea
            className="field-textarea min-h-28"
            aria-label="前作综合分析"
            value={doc.synthesis_narrative}
            onChange={(e) =>
              onChange?.({ ...doc, synthesis_narrative: e.target.value })
            }
          />
        </label>
      ) : (
        doc.synthesis_narrative && (
          <p className="prior-synthesis">
            {normalizeQuotes(doc.synthesis_narrative)}
          </p>
        )
      )}
      {!doc.prior_works.length && (
        <p className="py-4 text-sm text-body">暂无前作分析。</p>
      )}
      {doc.prior_works.map((work, index) => (
        <article className="prior-card" key={index}>
          {editing ? (
            <>
              <div className="flex items-start gap-2">
                <label className="field flex-1">
                  <span className="field-label">论文标题</span>
                  <input
                    className="field-input"
                    aria-label={`前作 ${index + 1} 标题`}
                    value={work.title}
                    onChange={(e) => change(index, { title: e.target.value })}
                  />
                </label>
                <button
                  className="icon-button mt-6"
                  aria-label={`移除前作 ${index + 1}`}
                  onClick={() =>
                    onChange?.({
                      ...doc,
                      prior_works: doc.prior_works.filter((_, i) => i !== index)
                    })
                  }
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <label className="field mt-3">
                <span className="field-label">作者</span>
                <input
                  className="field-input"
                  value={work.authors}
                  onChange={(e) => change(index, { authors: e.target.value })}
                />
              </label>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <label className="field">
                  <span className="field-label">年份</span>
                  <input
                    className="field-input"
                    type="number"
                    value={work.year || ''}
                    onChange={(e) =>
                      change(index, {
                        year: e.target.value ? Number(e.target.value) : null
                      })
                    }
                  />
                </label>
                <label className="field">
                  <span className="field-label">arXiv ID</span>
                  <input
                    className="field-input"
                    value={work.arxiv_id}
                    onChange={(e) =>
                      change(index, { arxiv_id: e.target.value })
                    }
                  />
                </label>
              </div>
              <label className="field mt-3">
                <span className="field-label">前作角色</span>
                <select
                  className="field-select"
                  value={work.role}
                  onChange={(e) => change(index, { role: e.target.value })}
                >
                  {[
                    'Baseline',
                    'Inspiration',
                    'Gap Identification',
                    'Foundation',
                    'Extension',
                    'Related Problem'
                  ].map((role) => (
                    <option key={role}>{role}</option>
                  ))}
                </select>
              </label>
              <label className="field mt-3">
                <span className="field-label">与当前论文的关系</span>
                <textarea
                  className="field-textarea"
                  value={work.relationship_sentence}
                  onChange={(e) =>
                    change(index, { relationship_sentence: e.target.value })
                  }
                />
              </label>
            </>
          ) : (
            <>
              <div className="flex items-start gap-3">
                <h3 className="flex-1">{work.title}</h3>
                <span className="role-badge">{work.role}</span>
              </div>
              <p className="prior-meta">
                {work.authors}
                {work.year ? ` · ${work.year}` : ''}
              </p>
              <p className="prior-relationship">
                {normalizeQuotes(work.relationship_sentence)}
              </p>
              {work.arxiv_id && (
                <a
                  className="prior-link"
                  href={`https://arxiv.org/abs/${work.arxiv_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看原文 <ExternalLink size={12} />
                </a>
              )}
            </>
          )}
        </article>
      ))}
      {editing && (
        <button
          className="action-button w-full justify-center"
          onClick={() =>
            onChange?.({
              ...doc,
              prior_works: [
                ...doc.prior_works,
                {
                  title: '',
                  authors: '',
                  year: null,
                  arxiv_id: '',
                  role: 'Baseline',
                  relationship_sentence: ''
                }
              ]
            })
          }
        >
          <Plus size={14} />
          添加前作
        </button>
      )}
    </div>
  )
}
