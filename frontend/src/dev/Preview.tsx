/** Visual preview harness for the redesigned views. Not shipped. */
import { MemoryRouter, Link } from 'react-router-dom'
import { FileSearch, Search, Trash2 } from 'lucide-react'
import { ReportBody } from '../components/ReportBody'
import { Notice } from '../components/Notice'
import { StatusPill } from '../components/StatusPill'
import { QuotaBar } from '../components/QuotaBar'
import { ScoreCell } from '../components/ScoreRing'
import { Finding, FindingDetail, FindingFix, FindingList } from '../components/Finding'
import { ShareMeter } from '../components/Readouts'
import { Pager } from '../components/Pager'
import { TextField } from '../components/Field'
import {
  EmptyState,
  PageHeader,
  Panel,
  Section,
} from '../components/Page'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ISSUES, RESULT } from './fixtures'

const QUOTA = {
  daily_limit: 5,
  used_today: 3,
  remaining_today: 2,
  day_reset_date: '2026-09-13',
  monthly_limit: 100,
  used_this_month: 41,
  month_reset_date: null,
}

const HISTORY = [
  { id: 1, title: 'Pricing — Example', url: 'https://example.com/pricing', score: 74, grade: 'C', status: 'done' as const },
  { id: 2, title: 'Docs — Example', url: 'https://example.com/docs', score: 91, grade: 'A', status: 'done' as const },
  { id: 3, title: null, url: 'https://example.com/careers', score: null, grade: null, status: 'running' as const },
  { id: 4, title: 'Blog — Launch week', url: 'https://example.com/blog/launch', score: 48, grade: 'F', status: 'done' as const },
]

export function Preview() {
  return (
    <MemoryRouter>
      <TooltipProvider>
        {/* The app shell, reproduced statically so the chrome is in shot. */}
        <header className="sticky top-0 z-50 h-(--header-h) border-b border-border bg-background/85 backdrop-blur-md">
          <div className="mx-auto flex h-full max-w-(--measure) items-center gap-3 px-5 sm:px-6">
            <Link to="/" className="flex shrink-0 items-center gap-2.5 font-semibold tracking-tight">
              <span className="size-2.5 rounded-full bg-primary ring-4 ring-accent-soft" />
              SEO Analysis
            </Link>
            <nav className="ml-1 flex items-center gap-0.5">
              <span className="rounded-lg bg-accent-soft px-3 py-1.5 text-[13.5px] font-medium text-accent-on-tint">
                Page audit
              </span>
              <span className="rounded-lg px-3 py-1.5 text-[13.5px] text-muted-foreground">
                Site audit
              </span>
              <span className="rounded-lg px-3 py-1.5 text-[13.5px] text-muted-foreground">
                Users
              </span>
            </nav>
            <span className="flex-1" />
            <span className="flex items-center gap-1.5 px-2 text-[13.5px] font-medium">
              aditya
              <Badge variant="info" className="px-1.5 py-0 text-[9.5px] font-bold uppercase">
                Admin
              </Badge>
            </span>
          </div>
        </header>

        <main className="mx-auto max-w-(--measure) px-5 pt-10 pb-28 sm:px-6">
          {/* 1. A list view: header, submit panel, table. */}
          <PageHeader
            title="Page audit"
            description={
              <>
                Every check against a single URL, covering meta, content, structure,
                links, indexability, performance, security and mobile.
              </>
            }
          />

          <Panel className="mt-8">
            <form className="grid gap-4" onSubmit={(e) => e.preventDefault()}>
              <div className="grid gap-1.5">
                <Label htmlFor="p-url">Page URL</Label>
                <div className="flex flex-col gap-2.5 sm:flex-row">
                  <div className="relative flex-1">
                    <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input id="p-url" defaultValue="https://example.com/pricing" className="h-10 pl-9" />
                  </div>
                  <Button type="button" className="h-10 px-5">Analyze</Button>
                </div>
              </div>
              <TextField
                id="p-keywords"
                label="Target keywords"
                optional
                defaultValue="team pricing, per seat billing"
                hint="Up to 5, comma separated. Scored separately so it never moves the page score."
              />
            </form>
            <Separator className="my-5" />
            <QuotaBar quota={QUOTA} />
          </Panel>

          <Section title="Recent page reports" meta="4 total">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Page</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead>Analyzed</TableHead>
                  <TableHead><span className="sr-only">Actions</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {HISTORY.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="max-w-[420px]">
                      <span className="block truncate font-medium">
                        {row.title || row.url.replace(/^https?:\/\//, '')}
                      </span>
                      <span className="block truncate text-[12.5px] text-muted-foreground">
                        {row.url.replace(/^https?:\/\//, '')}
                      </span>
                    </TableCell>
                    <TableCell><StatusPill status={row.status} /></TableCell>
                    <TableCell className="text-right">
                      <ScoreCell score={row.score} grade={row.grade} />
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      12 Sep 2026, 09:20
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon-sm" aria-label="Delete"
                        className="text-muted-foreground hover:bg-crit-soft hover:text-crit">
                        <Trash2 />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pager page={1} totalPages={3} onChange={() => {}} />
          </Section>

          {/* 2. Messages and an empty state. */}
          <Section title="Messages">
            <div className="grid max-w-[70ch] gap-3">
              <Notice tone="error">That URL could not be reached. Nothing was charged to your quota.</Notice>
              <Notice tone="warning"><strong className="font-semibold">Daily limit reached.</strong> Your allowance resets at midnight UTC.</Notice>
              <Notice tone="info">Core Web Vitals need a PageSpeed Insights key, which you can add in Account.</Notice>
              <Notice tone="success">Your profile has been updated.</Notice>
            </div>
            <div className="mt-6 max-w-[70ch]">
              <EmptyState icon={<FileSearch className="size-5" />} title="No page reports yet">
                Audit a page above and it will show up here.
              </EmptyState>
            </div>
          </Section>

          {/* 3. Crawl issues, which use the same finding row as the checks. */}
          <Section title="Issues across the site" meta="Ranked by pages affected">
            <FindingList>
              {ISSUES.map((issue) => (
                <Finding
                  key={issue.id}
                  status={issue.status}
                  label={issue.label}
                  badges={
                    <>
                      <StatusPill status={issue.status} />
                      {issue.sitewide ? <Badge variant="warning">site-wide</Badge> : null}
                    </>
                  }
                  message={`Affects ${issue.affected_pages} of ${issue.total_pages} pages.`}
                  trailing={issue.affected_pages}
                >
                  <ShareMeter
                    share={(issue.affected_pages / issue.total_pages) * 100}
                    tone={issue.status === 'critical' ? 'critical' : 'warning'}
                    ariaLabel="share"
                  />
                  {issue.recommendation ? <FindingFix>{issue.recommendation}</FindingFix> : null}
                  <FindingDetail>e.g. {issue.example_urls.join(' · ')}</FindingDetail>
                </Finding>
              ))}
            </FindingList>
          </Section>

          {/* 4. The full report body. */}
          <div className="mt-16 border-t border-border pt-12">
            <ReportBody
              results={RESULT}
              targetKeywords={['team pricing', 'per seat billing']}
              badge={<StatusPill status="done" />}
            />
          </div>
        </main>
      </TooltipProvider>
    </MemoryRouter>
  )
}
