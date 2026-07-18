import { describe, expect, test } from 'vitest'
import { normalizeQuotes } from './textFormat'

describe('normalizeQuotes', () => {
  test('replaces Chinese book-title marks with straight quotes', () => {
    expect(normalizeQuotes('相比《BERT》，本文提出了新的方法。')).toBe('相比"BERT"，本文提出了新的方法。')
  })

  test('replaces multiple occurrences', () => {
    expect(normalizeQuotes('参考《A》和《B》两项工作。')).toBe('参考"A"和"B"两项工作。')
  })

  test('leaves text without book-title marks unchanged', () => {
    expect(normalizeQuotes('与 "Deep Learning" 相似度92%')).toBe('与 "Deep Learning" 相似度92%')
  })

  test('handles empty string', () => {
    expect(normalizeQuotes('')).toBe('')
  })
})
