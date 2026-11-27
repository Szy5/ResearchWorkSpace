export function normalizeMathDelimiters(markdown: string) {
  return markdown
    .replace(
      /\\\[([\s\S]*?)\\\]/g,
      (_match, expression: string) => `\n\n$$\n${expression.trim()}\n$$\n\n`
    )
    .replace(
      /\\\(([\s\S]*?)\\\)/g,
      (_match, expression: string) => `$${expression.trim()}$`
    )
    .replace(
      /\\begin\{equation\*?\}([\s\S]*?)\\end\{equation\*?\}/g,
      (_match, expression: string) => `\n\n$$\n${expression.trim()}\n$$\n\n`
    )
}

export function readingMarkdown(markdown: string, title: string) {
  const lines = markdown.split('\n')
  const first = lines.findIndex((line) => line.trim())
  const plain = (s: string) =>
    s.replace(/[*_`]/g, '').replace(/\s+/g, ' ').trim().toLowerCase()
  if (
    first >= 0 &&
    /^#\s/.test(lines[first]) &&
    plain(lines[first].replace(/^#\s+/, '')) === plain(title)
  )
    lines.splice(first, 1)
  return lines.join('\n')
}
export function readingHeadings(markdown: string) {
  let fence: string | null = null
  return normalizeMathDelimiters(markdown)
    .split('\n')
    .flatMap((line, index) => {
      const marker = line.match(/^\s*(`{3,}|~{3,})/)
      if (marker) {
        if (!fence) fence = marker[1][0]
        else if (marker[1][0] === fence) fence = null
        return []
      }
      if (fence) return []
      const match = line.match(/^(#{1,3})\s+(.+?)(?:\s+#+)?$/)
      return match
        ? [
            {
              id: `section-${index + 1}`,
              title: match[2].replace(/[*_`]/g, ''),
              level: match[1].length
            }
          ]
        : []
    })
}
export function contentFingerprint(value: string) {
  let hash = 0
  for (let i = 0; i < value.length; i++)
    hash = (hash * 31 + value.charCodeAt(i)) | 0
  return hash.toString(36)
}
