/**
 * Reveals its children when they scroll into view.
 *
 * One IntersectionObserver per element, disconnected after it fires: the
 * animation is a one-shot, so keeping observers alive for a long marketing page
 * is pure overhead. Children render immediately either way, so the content is
 * present for crawlers and for anyone without IntersectionObserver.
 */
import { useEffect, useRef, useState, type ElementType, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Stagger, in milliseconds, so a row of cards arrives in sequence. */
  delay?: number
  className?: string
  as?: ElementType
}

export function Reveal({ children, delay = 0, className = '', as: Tag = 'div' }: Props) {
  const ref = useRef<HTMLElement>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const node = ref.current
    // Without the API, or before hydration, the content is simply already there.
    if (!node || typeof IntersectionObserver === 'undefined') {
      setShown(true)
      return
    }
    // Anything already on screen at mount should not animate in late.
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        setShown(true)
        observer.disconnect()
      },
      // Fire a little before the element's top edge arrives, so the motion
      // finishes as it reaches a comfortable reading position.
      { rootMargin: '0px 0px -12% 0px', threshold: 0.05 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <Tag
      ref={ref}
      className={`reveal${shown ? ' is-in' : ''}${className ? ` ${className}` : ''}`}
      style={delay ? ({ '--reveal-delay': `${delay}ms` } as React.CSSProperties) : undefined}
    >
      {children}
    </Tag>
  )
}
