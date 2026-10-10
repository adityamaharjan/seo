import { describe, expect, it } from 'vitest'
import { pollDelay } from './SiteAuditReport'

describe('site audit polling', () => {
  it('backs off from 1.5 s to 5 s as a crawl runs long', () => {
    expect(pollDelay(0)).toBe(1500)
    expect(pollDelay(4)).toBe(3000)
    expect(pollDelay(20)).toBe(5000)
  })
})
