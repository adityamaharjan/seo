import { describe, expect, it } from 'vitest'
import { formatKb, formatMs, renderValue, shortUrl } from './format'

describe('formatMs', () => {
  it('switches to seconds at 1000 ms', () => {
    expect(formatMs(999.6)).toBe('1000 ms')
    expect(formatMs(1000)).toBe('1.00 s')
    expect(formatMs(null)).toBe('—')
  })
})

describe('formatKb', () => {
  it('switches to MB at 1024 KB', () => {
    expect(formatKb(12.34)).toBe('12.3 KB')
    expect(formatKb(2048)).toBe('2.00 MB')
  })
})

describe('shortUrl', () => {
  it('drops the scheme and trailing slash, and truncates', () => {
    expect(shortUrl('https://example.com/')).toBe('example.com')
    expect(shortUrl('https://example.com/a-long-path', 12)).toBe('example.com…')
  })
})

describe('renderValue', () => {
  it('summarises arrays past eight items', () => {
    expect(renderValue(Array.from({ length: 10 }, (_, i) => i))).toBe(
      '0, 1, 2, 3, 4, 5, 6, 7 (+2 more)',
    )
  })

  it('drops empty fields from objects and returns null when nothing is left', () => {
    expect(renderValue({ lcp_ms: 1200, note: '' })).toBe('lcp ms: 1200')
    expect(renderValue({ note: null })).toBeNull()
  })
})
