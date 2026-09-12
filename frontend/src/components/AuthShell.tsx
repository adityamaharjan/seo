/**
 * The frame around signing in and signing up.
 *
 * Both screens are one short form and nothing else, so they get the viewport to
 * themselves rather than the app shell: there is no navigation worth showing to
 * someone who is not signed in yet, and the header's account menu would have
 * nothing to put in it.
 */
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Panel } from './Page'

export function AuthShell({
  title,
  lede,
  children,
  footer,
}: {
  title: ReactNode
  lede: ReactNode
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <div className="grid min-h-dvh place-items-center px-5 py-12">
      <div className="w-full max-w-[390px]">
        <div className="text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-2.5 font-semibold tracking-tight"
          >
            <span className="size-2.5 rounded-full bg-primary ring-4 ring-accent-soft" />
            SEO Analysis
          </Link>
          <h1 className="mt-6 text-[22px] font-semibold tracking-[-0.025em]">
            {title}
          </h1>
          <p className="mt-1.5 text-[14px] text-muted-foreground">{lede}</p>
        </div>

        <Panel className="mt-7">{children}</Panel>

        <p className="mt-5 text-center text-[13.5px] text-muted-foreground">
          {footer}
        </p>
      </div>
    </div>
  )
}
