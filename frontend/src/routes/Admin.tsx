/**
 * The user directory.
 *
 * Every destructive action here used to run through `window.confirm` and the
 * quota editor through `window.prompt`, which meant the most consequential
 * screen in the app had the least designed interactions in it: no styling, no
 * focus management, and a quota field that accepted any string and validated it
 * after the fact. Those are dialogs now, and the quota editor is a number input
 * that cannot submit a value the API would reject.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { MoreHorizontal, Search, Users } from 'lucide-react'
import { adminApi } from '../api/endpoints'
import type { Paginated, UserDetail, UserRole } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Notice } from '../components/Notice'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Pager } from '../components/Pager'
import { EmptyState, PageHeader, Section, TableSkeleton } from '../components/Page'
import { Spinner } from '../components/Spinner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDate } from '../lib/format'

const PAGE_SIZE = 20

type ActiveFilter = 'all' | 'active' | 'disabled'
type Pending =
  | { kind: 'revoke'; user: UserDetail }
  | { kind: 'delete'; user: UserDetail }
  | null

export function Admin() {
  const { user } = useAuth()

  const [data, setData] = useState<Paginated<UserDetail> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [role, setRole] = useState<UserRole | 'all'>('all')
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('all')

  const [pending, setPending] = useState<Pending>(null)
  const [quotaTarget, setQuotaTarget] = useState<UserDetail | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await adminApi.listUsers({
        page,
        pageSize: PAGE_SIZE,
        search: search.trim() || undefined,
        role: role === 'all' ? undefined : role,
        isActive: activeFilter === 'all' ? null : activeFilter === 'active',
      })
      setData(result)
      setError(null)
    } catch (caught) {
      setError(caught)
    } finally {
      setLoading(false)
    }
  }, [page, search, role, activeFilter])

  // Debounce the search box so typing does not fire a request per keystroke.
  useEffect(() => {
    const handle = window.setTimeout(load, search ? 300 : 0)
    return () => window.clearTimeout(handle)
  }, [load, search])

  async function act(id: number, action: () => Promise<unknown>) {
    setBusyId(id)
    setError(null)
    try {
      await action()
      await load()
    } catch (caught) {
      setError(caught)
    } finally {
      setBusyId(null)
    }
  }

  function changeRole(target: UserDetail, nextRole: UserRole) {
    return act(target.id, () => adminApi.updateUser(target.id, { role: nextRole }))
  }

  function toggleActive(target: UserDetail) {
    return act(target.id, () =>
      adminApi.updateUser(target.id, { is_active: !target.is_active }),
    )
  }

  function saveQuota(target: UserDetail, dailyLimit: number) {
    setQuotaTarget(null)
    return act(target.id, () =>
      adminApi.updateQuota(target.id, { daily_limit: dailyLimit }),
    )
  }

  function runPending() {
    const request = pending
    setPending(null)
    if (!request) return
    if (request.kind === 'revoke') {
      return act(request.user.id, () => adminApi.revokeSessions(request.user.id))
    }
    return act(request.user.id, () => adminApi.deleteUser(request.user.id))
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader
        title="Users"
        description="Every registered account, with its role, daily allowance and report count."
      />

      <Section title="Directory" meta={data ? `${data.total} total` : undefined}>
        <Notice error={error} className="mb-4" />

        <div className="mb-5 flex flex-col gap-2.5 sm:flex-row">
          <div className="relative flex-1">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              type="search"
              placeholder="Search username or email"
              aria-label="Search users"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="h-9 pl-9"
            />
          </div>
          <Select
            value={role}
            onValueChange={(value) => {
              setRole(value as UserRole | 'all')
              setPage(1)
            }}
          >
            <SelectTrigger aria-label="Filter by role" className="sm:w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All roles</SelectItem>
              <SelectItem value="user">Users</SelectItem>
              <SelectItem value="admin">Admins</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={activeFilter}
            onValueChange={(value) => {
              setActiveFilter(value as ActiveFilter)
              setPage(1)
            }}
          >
            <SelectTrigger aria-label="Filter by status" className="sm:w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Any status</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="disabled">Disabled</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {loading && !data ? (
          <TableSkeleton rows={6} />
        ) : data && data.items.length > 0 ? (
          <>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Quota today</TableHead>
                  <TableHead className="text-right">Reports</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((row) => {
                  const isSelf = row.id === user?.id
                  const busy = busyId === row.id
                  return (
                    <TableRow key={row.id}>
                      <TableCell className="max-w-[260px]">
                        <span className="flex items-center gap-2">
                          <span className="truncate font-medium">{row.username}</span>
                          {isSelf ? (
                            <Badge variant="neutral" className="text-[9.5px] uppercase">
                              You
                            </Badge>
                          ) : null}
                        </span>
                        <span className="block truncate text-[12.5px] text-muted-foreground">
                          {row.email}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Select
                          value={row.role}
                          disabled={busy || isSelf}
                          onValueChange={(value) => changeRole(row, value as UserRole)}
                        >
                          <SelectTrigger
                            size="sm"
                            aria-label={`Role for ${row.username}`}
                            title={isSelf ? 'You cannot change your own role' : undefined}
                            className="w-[104px]"
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="user">user</SelectItem>
                            <SelectItem value="admin">admin</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Badge variant={row.is_active ? 'good' : 'critical'}>
                          {row.is_active ? 'active' : 'disabled'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-[13px] tabular-nums">
                        {row.quota
                          ? `${row.quota.used_today} / ${row.quota.daily_limit}`
                          : '—'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-[13px] tabular-nums">
                        {row.report_count}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {formatDate(row.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              disabled={busy}
                              aria-label={`Actions for ${row.username}`}
                            >
                              {busy ? <Spinner /> : <MoreHorizontal />}
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onSelect={() => setQuotaTarget(row)}>
                              Edit daily quota
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={isSelf}
                              onSelect={() => toggleActive(row)}
                            >
                              {row.is_active ? 'Disable account' : 'Enable account'}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onSelect={() => setPending({ kind: 'revoke', user: row })}
                            >
                              Sign out everywhere
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              variant="destructive"
                              disabled={isSelf}
                              onSelect={() => setPending({ kind: 'delete', user: row })}
                            >
                              Delete account
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>

            <Pager
              page={data.page}
              totalPages={totalPages}
              busy={loading}
              onChange={setPage}
            />
          </>
        ) : (
          <EmptyState icon={<Users className="size-5" />} title="No users match">
            Try clearing the search or the filters above.
          </EmptyState>
        )}
      </Section>

      <QuotaDialog
        target={quotaTarget}
        onCancel={() => setQuotaTarget(null)}
        onSave={saveQuota}
      />

      <ConfirmDialog
        open={pending?.kind === 'revoke'}
        onOpenChange={(open) => {
          if (!open) setPending(null)
        }}
        title="Sign this user out everywhere?"
        description={
          pending
            ? `${pending.user.username} will be signed out of every device and will need to sign in again.`
            : ''
        }
        confirmLabel="Sign out"
        onConfirm={runPending}
      />

      <ConfirmDialog
        open={pending?.kind === 'delete'}
        onOpenChange={(open) => {
          if (!open) setPending(null)
        }}
        title="Delete this account permanently?"
        description={
          pending
            ? `${pending.user.username} and their ${pending.user.report_count} report${pending.user.report_count === 1 ? '' : 's'} will be deleted. This cannot be undone.`
            : ''
        }
        confirmLabel="Delete account"
        destructive
        onConfirm={runPending}
      />
    </>
  )
}

/**
 * Editing one user's daily allowance.
 *
 * The input is `type="number"` with a floor of zero, so the value the old
 * prompt had to reject after the fact cannot be entered in the first place. It
 * is keyed by user id so it resets between rows rather than carrying the
 * previous user's number into the next one.
 */
function QuotaDialog({
  target,
  onCancel,
  onSave,
}: {
  target: UserDetail | null
  onCancel: () => void
  onSave: (user: UserDetail, dailyLimit: number) => void
}) {
  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) onCancel()
      }}
    >
      <DialogContent>
        {target ? (
          <QuotaForm key={target.id} target={target} onSave={onSave} />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function QuotaForm({
  target,
  onSave,
}: {
  target: UserDetail
  onSave: (user: UserDetail, dailyLimit: number) => void
}) {
  const [value, setValue] = useState(String(target.quota?.daily_limit ?? 5))
  const parsed = Number(value)
  const valid = value !== '' && Number.isInteger(parsed) && parsed >= 0

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!valid) return
    onSave(target, parsed)
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>Daily quota</DialogTitle>
        <DialogDescription>
          How many analyses {target.username} may run each day. Zero blocks new
          analyses without disabling the account.
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-1.5">
        <Label htmlFor="daily-limit">Analyses per day</Label>
        <Input
          id="daily-limit"
          type="number"
          min={0}
          step={1}
          inputMode="numeric"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-10 w-32 tabular-nums"
        />
        <p className="text-[12.5px] text-muted-foreground">
          Currently using {target.quota?.used_today ?? 0} of{' '}
          {target.quota?.daily_limit ?? 0} today.
        </p>
      </div>

      <DialogFooter>
        <Button type="submit" disabled={!valid}>
          Save quota
        </Button>
      </DialogFooter>
    </form>
  )
}
