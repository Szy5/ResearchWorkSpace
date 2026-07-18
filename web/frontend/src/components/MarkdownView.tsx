import { useState } from 'react'
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

function normalizeMathDelimiters(markdown: string) {
  return markdown
    .replace(/\\\[([\s\S]*?)\\\]/g, (_match, expression: string) => `\n\n$$\n${expression.trim()}\n$$\n\n`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_match, expression: string) => `$${expression.trim()}$`)
    .replace(
      /\\begin\{equation\*?\}([\s\S]*?)\\end\{equation\*?\}/g,
      (_match, expression: string) => `\n\n$$\n${expression.trim()}\n$$\n\n`
    )
}

export default function MarkdownView({ markdown, slug }: Props) {
  const [expandedSrc, setExpandedSrc] = useState<string | null>(null)

  if (!markdown.trim()) {
    return <div className="markdown-empty">No summary yet.</div>
  }

  const normalizedMarkdown = normalizeQuotes(normalizeMathDelimiters(markdown))

  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={{
          img: ({ src, alt }) => {
            const resolved = artifactImageUrl(slug, src)
            return (
              <img
                src={resolved}
                alt={alt ?? ''}
                loading="lazy"
                onClick={() => setExpandedSrc(resolved)}
              />
            )
          }
        }}
      >
        {normalizedMarkdown}
      </ReactMarkdown>
      {expandedSrc ? (
        <div className="image-lightbox-backdrop" onClick={() => setExpandedSrc(null)}>
          <img src={expandedSrc} alt="" />
        </div>
      ) : null}
    </div>
  )
}
