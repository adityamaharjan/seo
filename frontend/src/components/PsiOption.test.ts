import { describe, expect, it } from 'vitest'
import { estimate } from './PsiOption'

describe('PageSpeed time estimate', () => {
  it('counts two runs per page, six at a time', () => {
    // homepage: 2 runs fit in one parallel round
    expect(estimate('homepage', 50)).toBe('about 25 seconds')
    // sample: 5 pages, 10 runs, two rounds
    expect(estimate('sample', 50)).toBe('about 50 seconds')
    // all on 50 pages: 100 runs, 17 rounds, 425 s
    expect(estimate('all', 50)).toBe('about 7 minutes')
  })

  it('never samples more pages than the crawl has', () => {
    expect(estimate('sample', 2)).toBe(estimate('all', 2))
  })
})
