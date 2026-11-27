import { render } from '@testing-library/react'
import { expect, test } from 'vitest'
import { createElement } from 'react'
import MarkdownView from '../components/MarkdownView'
import { readingHeadings, readingMarkdown } from './reading'
test('outline targets match rendered headings even after expanded math blocks', () => {
  const markdown =
    '# Demo\n\n\\[x^2\\]\n\n## Results\n\n```python\n# not a heading\n```\n\n### Details'
  const source = readingMarkdown(markdown, 'Demo')
  const headings = readingHeadings(source)
  const { container } = render(
    createElement(MarkdownView, { markdown: source })
  )
  expect(headings.map((h) => h.title)).toEqual(['Results', 'Details'])
  for (const heading of headings)
    expect(container.querySelector(`#${heading.id}`)?.textContent).toBe(
      heading.title
    )
  expect(container.querySelector('h1')).toBeNull()
})
