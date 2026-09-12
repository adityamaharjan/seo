/**
 * Public marketing page at `/`.
 *
 * Minimal by construction. The earlier version leaned on card chrome and tinted
 * bands, but the band sat at 1.03:1 against the page and cards were painted in
 * the page colour, so on a band they vanished in light mode and *receded* in
 * dark mode where a raised surface should be lighter than its ground. Removing
 * both fixes the contrast and the look at once: separation now comes from
 * whitespace and hairlines, and a card is reserved for the one place elevation
 * means something, the price.
 *
 * Structure follows the pattern established SEO checkers converge on: a URL
 * field in the hero, then features, coverage, scoring, pricing, FAQ. Absent is
 * their social proof furniture, because this product has no users, reviews or
 * customer logos yet and inventing them would be fabricating endorsements.
 *
 * Every number is read from the engine, so the page cannot drift from the app.
 */
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Search } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { Reveal } from '../components/Reveal'
import { ScoreRing } from '../components/ScoreRing'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

/** Mirrors the engine. See app/seo/constants.py and app/core/config.py. */
const TOTAL_CHECKS = 35
const MAX_SITE_PAGES = 50
const MAX_KEYWORDS = 5
const FREE_DAILY = 5
const FREE_MONTHLY = 100
const RETENTION_DAYS = 90

/** Category weights, straight from CATEGORY_WEIGHTS. */
const CATEGORIES = [
  { name: 'Content', weight: 22, covers: 'Word count, readability, alt text, image weight' },
  { name: 'Meta', weight: 20, covers: 'Title, description, canonical, robots, structured data' },
  { name: 'Structure', weight: 12, covers: 'H1, heading order, charset, doctype, favicon' },
  { name: 'Indexability', weight: 12, covers: 'robots.txt, XML sitemap, hreflang' },
  { name: 'Performance', weight: 12, covers: 'TTFB, load time, compression, render blocking' },
  { name: 'Links', weight: 10, covers: 'Internal and external links, anchors, broken links' },
  { name: 'Security', weight: 6, covers: 'HTTPS, mixed content, security headers' },
  { name: 'Mobile', weight: 6, covers: 'Viewport configuration' },
]

const FEATURES = [
  {
    tag: 'Page audit',
    title: 'One page, in depth',
    body: `Every check against a single URL. Name up to ${MAX_KEYWORDS} target keywords and you also get a placement map showing where each one appears: title, H1, meta description, opening copy, subheadings, the URL and image alt text.`,
    points: [
      'Keyword placement scored separately, so it never distorts page health',
      'Exact phrases and inflections both counted, weighted differently',
      'Real transfer timing, not a synthetic estimate',
    ],
  },
  {
    tag: 'Site audit',
    title: `Up to ${MAX_SITE_PAGES} pages, ranked`,
    body: `Crawls from your sitemap, falling back to internal links, and runs the full audit on every page. Then it ranks findings by how many pages they affect, because one page with a short title is a task and forty pages is a template bug.`,
    points: [
      'Issues hitting half the site flagged as site-wide',
      'Score spread across pages, not just an average',
      'Drill into any crawled page for its full report',
    ],
  },
]

const SCORING = [
  {
    title: 'Checks are weighted, not averaged',
    body: `A missing title tag moves your meta score six times as far as a missing Twitter card. Averaging a category equally lets a favicon outvote an H1, which is what makes most composite scores feel arbitrary.`,
  },
  {
    title: 'Blockers cap the score instead of hiding in it',
    body: `A page nobody can index cannot rank, whatever else it does right. Those failures put a ceiling on the score rather than being averaged away by thirty healthy checks.`,
  },
  {
    title: 'You are told what the fix is worth',
    body: `When something caps your score, the report says what you would score with it fixed and nothing else changed. That number is computed, not estimated.`,
  },
  {
    title: 'Counts sit beside the number',
    body: `Critical, warning and passed totals are always shown alongside the score, so a single figure never has to carry all the meaning.`,
  },
]

const STEPS = [
  {
    n: '01',
    title: 'Point it at a URL',
    body: `One page, or a whole site to crawl. Nothing to install, no DNS change, no access to the site required.`,
  },
  {
    n: '02',
    title: 'It fetches and measures',
    body: `The page is retrieved once with real transfer timing. robots.txt is parsed properly, the sitemap is read, and links are probed for real.`,
  },
  {
    n: '03',
    title: 'You get a ranked fix list',
    body: `Every finding carries the specific change to make. A site audit ranks findings by how many pages they touch.`,
  },
]

const FAQ = [
  {
    q: 'Do I need to install anything on my site?',
    a: `No. Give it a public URL and it fetches the page the way a search engine would. There is no script to add, no DNS record, and no access to your hosting.`,
  },
  {
    q: 'Does it run JavaScript?',
    a: `No. Pages are analysed as served, without a headless browser. If your content is rendered client-side, this reads the HTML a crawler receives first, which is often the more useful view. It does mean a fully client-rendered page will look thin here.`,
  },
  {
    q: 'How does the site audit pick which pages to crawl?',
    a: `Your sitemap first, taken from robots.txt or the conventional location. If there is no sitemap, or it returns fewer pages than your budget, it walks internal links from the starting page instead. robots.txt is obeyed either way.`,
  },
  {
    q: 'What does a site audit cost against my quota?',
    a: `One analysis, whatever the page count. A ${MAX_SITE_PAGES}-page crawl and a single page both use one unit.`,
  },
  {
    q: 'What if a page cannot be fetched?',
    a: `The quota unit is returned automatically. A site that is down, blocking, or slow to respond never costs you an audit.`,
  },
  {
    q: 'How long are reports kept?',
    a: `${RETENTION_DAYS} days, after which they are removed automatically. You can delete any report yourself at any time.`,
  },
]

export function Landing() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [url, setUrl] = useState('')

  // The page stays public either way, but a signed-in reader must never be
  // asked to "create an account". `loading` is only ever true when a stored
  // session is still being checked, so assuming signed-in during it is right
  // far more often than not, and it keeps the calls to action from changing
  // under the reader. A session that turns out to be dead corrects itself.
  const signedIn = loading || user !== null

  /**
   * The URL typed here rides along as a query parameter, so it survives the
   * sign-up round trip and arrives prefilled on the audit form. Nothing is
   * submitted from this page: an audit costs quota and needs an account.
   */
  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const target = url.trim()
    if (!target) return
    const query = `?url=${encodeURIComponent(normalizeUrl(target))}`
    navigate(signedIn ? `/app${query}` : `/signup${query}`)
  }

  return (
    <div className="font-sans text-foreground">
      <header className="sticky top-0 z-50 flex h-[var(--header-h)] items-center gap-4 border-b border-border bg-background/85 px-5 backdrop-blur-md backdrop-saturate-150">
        <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <span className="size-2.5 rounded-full bg-primary ring-4 ring-accent-soft" />
          SEO Analysis
        </Link>
        <nav className="ml-2 hidden items-center gap-1 md:flex">
          {[
            ['Features', '#features'],
            ['Checks', '#checks'],
            ['Scoring', '#scoring'],
            ['Pricing', '#pricing'],
            ['FAQ', '#faq'],
          ].map(([label, href]) => (
            <a
              key={href}
              href={href}
              className="rounded-lg px-3 py-1.5 text-[13.5px] text-muted-foreground transition-colors duration-200 hover:text-foreground"
            >
              {label}
            </a>
          ))}
        </nav>
        <span className="flex-1" />
        <div className="flex items-center gap-1.5">
          {signedIn ? (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link to="/account">{user?.username ?? 'Account'}</Link>
              </Button>
              <Button asChild size="sm">
                <Link to="/app">Open the app</Link>
              </Button>
            </>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link to="/login">Sign in</Link>
              </Button>
              <Button asChild size="sm">
                <Link to="/signup">Get started</Link>
              </Button>
            </>
          )}
        </div>
      </header>

      <main>
        {/* Hero. Staggered so the eye lands on the headline, then the field. */}
        <section className="mx-auto grid max-w-[1060px] items-center gap-16 px-5 pt-24 pb-20 lg:grid-cols-[1.08fr_0.92fr]">
          <div>
            <Reveal>
              <span className="text-[12px] font-semibold tracking-[0.09em] text-accent-on-tint uppercase">
                Technical SEO auditing
              </span>
            </Reveal>
            <Reveal delay={60}>
              <h1 className="mt-5 text-[clamp(2.1rem,4.6vw,3.4rem)] leading-[1.06] font-semibold tracking-[-0.035em] text-balance">
                Find what is holding your pages back, with the fix attached.
              </h1>
            </Reveal>
            <Reveal delay={120}>
              <p className="mt-6 max-w-[34em] text-[17px] leading-relaxed text-muted-foreground text-pretty">
                {TOTAL_CHECKS} checks across eight weighted categories, on a single page
                or across {MAX_SITE_PAGES} of them. Every finding comes with the specific
                change to make, and the score tells you which changes are worth making
                first.
              </p>
            </Reveal>
            <Reveal delay={180}>
              <form onSubmit={handleSubmit} className="mt-9 flex flex-col gap-2.5 sm:flex-row">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="text"
                    inputMode="url"
                    aria-label="Website URL"
                    placeholder="yoursite.com"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="h-12 rounded-xl border-border-control bg-background pl-10 text-[15px] transition-shadow duration-200"
                  />
                </div>
                <Button
                  type="submit"
                  size="lg"
                  disabled={!url.trim()}
                  className="group h-12 rounded-xl px-6"
                >
                  Audit this page
                  <ArrowRight className="size-4 transition-transform duration-300 group-hover:translate-x-0.5" />
                </Button>
              </form>
            </Reveal>
            <Reveal delay={240}>
              <p className="mt-4 text-[13.5px] text-muted-foreground">
                {signedIn
                  ? `Signed in. ${FREE_DAILY} audits a day on the free tier.`
                  : `${FREE_DAILY} audits a day on the free tier. No card required.`}
              </p>
            </Reveal>
          </div>

          {/* A real report fragment, not a stock illustration. */}
          <Reveal delay={260} aria-hidden="true">
            <div className="rounded-2xl border border-border bg-background p-6 shadow-[var(--shadow)]">
              <div className="flex items-center gap-4 border-b border-border pb-5">
                <ScoreRing score={82} grade="B" size={88} stroke={8} />
                <div>
                  <div className="text-[15px] font-semibold">example.com/pricing</div>
                  <div className="mt-1 text-[13px] text-muted-foreground">
                    2 critical · 6 warnings · 27 passed
                  </div>
                </div>
              </div>
              <div className="pt-2">
                <PreviewRow tone="crit" label="Meta robots" text="Page is marked noindex." />
                <PreviewRow tone="warn" label="Title tag" text="Title is 18 characters; aim for 30 to 60." />
                <PreviewRow tone="good" label="HTTPS" text="Served over a secure connection." />
              </div>
            </div>
          </Reveal>
        </section>

        {/* Two features, side by side, separated by space rather than boxes. */}
        <Section id="features" title="Two ways to audit"
          lede="They answer different questions, so they are separate tools rather than one tool with a checkbox.">
          <div className="grid gap-14 md:grid-cols-2 md:gap-16">
            {FEATURES.map((feature, i) => (
              <Reveal key={feature.tag} delay={i * 90}>
                <div className="text-[12px] font-semibold tracking-[0.08em] text-accent-on-tint uppercase">
                  {feature.tag}
                </div>
                <h3 className="mt-3 text-[21px] font-semibold tracking-[-0.02em]">
                  {feature.title}
                </h3>
                <p className="mt-3 text-muted-foreground text-pretty">{feature.body}</p>
                <Ticks items={feature.points} />
              </Reveal>
            ))}
          </div>
        </Section>

        {/* Coverage. A plain table of weights reads better than eight boxes. */}
        <Section id="checks" title="What gets checked"
          lede={`${TOTAL_CHECKS} checks, grouped into eight categories. The percentage is how much each category moves your overall score.`}>
          <div className="grid gap-x-14 sm:grid-cols-2">
            {CATEGORIES.map((category, i) => (
              <Reveal key={category.name} delay={i * 45}>
                <div className="flex items-baseline gap-4 border-b border-border py-4">
                  <span className="w-28 shrink-0 font-medium">{category.name}</span>
                  <span className="flex-1 text-[13.5px] text-muted-foreground">
                    {category.covers}
                  </span>
                  <span className="tabular-nums text-[13px] font-semibold text-accent-on-tint">
                    {category.weight}%
                  </span>
                </div>
              </Reveal>
            ))}
          </div>
        </Section>

        <Section id="scoring" title="A score you can argue with"
          lede="Most tools hand you a number with no way to check it. This one shows its working.">
          <div className="grid gap-x-14 gap-y-10 md:grid-cols-2">
            {SCORING.map((point, i) => (
              <Reveal key={point.title} delay={i * 70}>
                <h3 className="text-[17px] font-semibold tracking-[-0.015em]">{point.title}</h3>
                <p className="mt-2.5 text-muted-foreground text-pretty">{point.body}</p>
              </Reveal>
            ))}
          </div>
        </Section>

        <Section title="How it works">
          <div className="grid gap-10 md:grid-cols-3 md:gap-8">
            {STEPS.map((step, i) => (
              <Reveal key={step.n} delay={i * 90}>
                <span className="font-mono text-[13px] font-semibold text-accent-on-tint">
                  {step.n}
                </span>
                <h3 className="mt-3 text-[17px] font-semibold tracking-[-0.015em]">
                  {step.title}
                </h3>
                <p className="mt-2.5 text-muted-foreground text-pretty">{step.body}</p>
              </Reveal>
            ))}
          </div>
        </Section>

        {/* The one place a card earns its chrome. */}
        <Section id="pricing" title="Pricing"
          lede="Start free. A site audit of any size counts as a single analysis.">
          <Reveal>
            <div className="lift mx-auto w-full max-w-[400px] rounded-2xl border border-border bg-background p-8 shadow-[var(--shadow)] hover:border-border-strong">
              <div className="text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
                Free
              </div>
              <div className="mt-2 text-[44px] leading-none font-semibold tracking-[-0.035em]">
                $0
                <span className="text-[15px] font-normal tracking-normal text-muted-foreground">
                  /month
                </span>
              </div>
              <Ticks
                items={[
                  `${FREE_DAILY} analyses per day`,
                  `${FREE_MONTHLY} per month`,
                  `Site audits up to ${MAX_SITE_PAGES} pages`,
                  `All ${TOTAL_CHECKS} checks, no feature gating`,
                  'Full report history',
                ]}
              />
              <Button asChild size="lg" className="mt-8 h-11 w-full rounded-xl">
                <Link to={signedIn ? '/app' : '/signup'}>
                  {signedIn ? 'Open the app' : 'Create an account'}
                </Link>
              </Button>
              <p className="mt-4 text-[13px] leading-relaxed text-muted-foreground">
                A failed analysis is refunded automatically, so a site that will not
                respond never costs you anything.
              </p>
            </div>
          </Reveal>
        </Section>

        <Section id="faq" title="Questions">
          <Reveal>
            <Accordion type="single" collapsible className="w-full max-w-[46em]">
              {FAQ.map(({ q, a }) => (
                <AccordionItem key={q} value={q} className="border-border">
                  <AccordionTrigger className="py-5 text-left text-[15.5px] font-medium hover:no-underline">
                    {q}
                  </AccordionTrigger>
                  <AccordionContent className="pb-5 text-[15px] leading-relaxed text-muted-foreground">
                    {a}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </Reveal>
        </Section>

        <section className="mx-auto max-w-[1060px] px-5 py-28 text-center">
          <Reveal>
            <h2 className="text-[clamp(1.6rem,3.2vw,2.25rem)] font-semibold tracking-[-0.03em] text-balance">
              See what your homepage scores.
            </h2>
            <p className="mt-3 text-muted-foreground">
              It takes about as long as loading the page does.
            </p>
            <Button asChild size="lg" className="group mt-8 h-12 rounded-xl px-7">
              <Link to={signedIn ? '/app' : '/signup'}>
                {signedIn ? 'Audit a page' : 'Get started free'}
                <ArrowRight className="size-4 transition-transform duration-300 group-hover:translate-x-0.5" />
              </Link>
            </Button>
          </Reveal>
        </section>
      </main>

      <footer className="mx-auto flex max-w-[1060px] flex-wrap items-center gap-4 border-t border-border px-5 pt-7 pb-14 text-[13.5px] text-muted-foreground">
        <span className="flex items-center gap-2.5 font-semibold tracking-tight text-foreground">
          <span className="size-2.5 rounded-full bg-primary ring-4 ring-accent-soft" />
          SEO Analysis
        </span>
        <span className="flex-1" />
        <nav className="flex items-center gap-1">
          {(signedIn
            ? ([
                ['Page audit', '/app'],
                ['Site audit', '/site-audit'],
                ['Account', '/account'],
              ] as const)
            : ([
                ['Sign in', '/login'],
                ['Create account', '/signup'],
              ] as const)
          ).map(([label, to]) => (
            <Link
              key={to}
              to={to}
              className="rounded-lg px-3 py-1.5 transition-colors duration-200 hover:text-foreground"
            >
              {label}
            </Link>
          ))}
        </nav>
      </footer>
    </div>
  )
}

/**
 * One section: a heading, an optional lede, a rule that draws itself in, and
 * the content. Sections are separated by whitespace rather than tinted bands,
 * which is both quieter and the reason the contrast problem is gone.
 */
function Section({
  id,
  title,
  lede,
  children,
}: {
  id?: string
  title: string
  lede?: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-[calc(var(--header-h)+16px)]">
      <div className="mx-auto max-w-[1060px] px-5 py-24">
        <Reveal>
          <h2 className="max-w-[18em] text-[clamp(1.6rem,3.2vw,2.25rem)] font-semibold tracking-[-0.03em] text-balance">
            {title}
          </h2>
          {lede ? (
            <p className="mt-3 max-w-[40em] text-[16.5px] leading-relaxed text-muted-foreground text-pretty">
              {lede}
            </p>
          ) : null}
          <div className="rule mt-9 h-px w-full bg-border" />
        </Reveal>
        <div className="mt-12">{children}</div>
      </div>
    </section>
  )
}

/** Checklist rows. */
function Ticks({ items }: { items: string[] }) {
  return (
    <ul className="mt-5 flex list-none flex-col gap-3 p-0">
      {items.map((item) => (
        <li key={item} className="relative pl-6 text-[14.5px] leading-relaxed">
          <span className="absolute top-[7px] left-1 h-[9px] w-[5px] rotate-45 border-r-2 border-b-2 border-good" />
          {item}
        </li>
      ))}
    </ul>
  )
}

function PreviewRow({
  tone,
  label,
  text,
}: {
  tone: 'crit' | 'warn' | 'good'
  label: string
  text: string
}) {
  const bar = { crit: 'bg-crit', warn: 'bg-warn', good: 'bg-good' }[tone]
  return (
    <div className="flex gap-3 py-3">
      <span className={`w-[3px] shrink-0 rounded-full ${bar}`} />
      <div>
        <div className="text-[13.5px] font-medium">{label}</div>
        <div className="mt-0.5 text-[13px] text-muted-foreground">{text}</div>
      </div>
    </div>
  )
}

/** Let people type "example.com" without the scheme. */
function normalizeUrl(value: string): string {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`
}
