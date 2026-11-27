import { useState } from 'react'
import Dialog from './Dialog'
import { normalizeMathDelimiters } from '../utils/reading'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import 'katex/dist/katex.min.css'
import { normalizeQuotes } from '../utils/textFormat'

type Props = {
  markdown: string
  slug?: string
}

function isExternalUrl(src: string) {
  return /^(https?:|data:|blob:|mailto:|#)/i.test(src)
}

function artifactImageUrl(slug: string | undefined, src: string | undefined) {
  if (!src || !slug || isExternalUrl(src) || src.startsWith('/api/')) {
    return src ?? ''
  }

  let path = src.replace(/\\/g, '/').trim()
  const artifactMarker = `/artifacts/${slug}/`
  const artifactIndex = path.indexOf(artifactMarker)
  if (artifactIndex >= 0) {
    path = path.slice(artifactIndex + artifactMarker.length)
  }
  path = path.replace(/^\.?\//, '')

  const encoded = path
    .split('/')
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join('/')
  return `/api/papers/${encodeURIComponent(slug)}/files/${encoded}`
}

export default function MarkdownView({ markdown, slug }: Props) {
  const [expandedSrc, setExpandedSrc] = useState<string | null>(null)

  if (!markdown.trim()) {
    return <div className="markdown-empty">还没有精读笔记，请先生成精读。</div>
  }

  const normalizedMarkdown = normalizeQuotes(normalizeMathDelimiters(markdown))

  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={{
          h1: ({ node, children }) => (
            <h1 id={`section-${node?.position?.start.line}`}>{children}</h1>
          ),
          h2: ({ node, children }) => (
            <h2 id={`section-${node?.position?.start.line}`}>{children}</h2>
          ),
          h3: ({ node, children }) => (
            <h3 id={`section-${node?.position?.start.line}`}>{children}</h3>
          ),
          table: ({ children }) => (
            <div className="table-scroll">
              <table>{children}</table>
            </div>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target={href?.startsWith('http') ? '_blank' : undefined}
              rel="noreferrer"
            >
              {children}
            </a>
          ),
          img: ({ src, alt }) => {
            const resolved = artifactImageUrl(slug, src)
            return (
              <button
                type="button"
                className="figure-button"
                aria-label={`放大图片：${alt || '论文配图'}`}
                onClick={() => setExpandedSrc(resolved)}
              >
                <img src={resolved} alt={alt ?? ''} loading="lazy" />
              </button>
            )
          }
        }}
      >
        {normalizedMarkdown}
      </ReactMarkdown>
      {expandedSrc ? (
        <Dialog
          title="论文配图"
          className="image-lightbox-backdrop"
          onClose={() => setExpandedSrc(null)}
        >
          <img src={expandedSrc} alt="放大的论文配图" />
        </Dialog>
      ) : null}
    </div>
  )
}
