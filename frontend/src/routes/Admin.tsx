import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/endpoints'
import type { Paginated, UserDetail, UserRole } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Notice } from '../components/Notice'
import { formatDate } from '../lib/format'

const PAGE_SIZE = 20

type ActiveFilter = 'all' | 'active' | 'disabled'

export function Admin() {
  const { user } = useAuth()

  const [data, setData] = useState<Paginated<UserDetail> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [role, setRole] = useState<UserRole | ''>('')
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('all')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await adminApi.listUsers({
        page,
        pageSize: PAGE_SIZE,
        search: search.trim() || undefined,
        role: role || undefined,
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

  async function editQuota(target: UserDetail) {
    const raw = window.prompt(
      `Daily analysis limit for ${target.username}:`,
      String(target.quota?.daily_limit ?? 5),
    )
    if (raw === null) return
    const daily_limit = Number(raw)
    if (!Number.isInteger(daily_limit) || daily_limit < 0) {
      setError(new Error('The daily limit must be a whole number of zero or more.'))
      return
    }
    await act(target.id, () => adminApi.updateQuota(target.id, { daily_limit }))
  }

  function revoke(target: UserDetail) {
    if (!window.confirm(`Sign ${target.username} out of every device?`)) return
    return act(target.id, () => adminApi.revokeSessions(target.id))
  }

  function remove(target: UserDetail) {
    const warning =
      `Delete ${target.username} permanently?\n\n` +
      `This also deletes their ${target.report_count} report(s). It cannot be undone.`
    if (!window.confirm(warning)) return
    return act(target.id, () => adminApi.deleteUser(target.id))
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="card">
      <div className="section-head">
        <h2>Users</h2>
        {data ? <span className="quota-text">{data.total} total</span> : null}
      </div>

      <Notice error={error} />

      <div className="admin-filters">
        <input
          className="admin-search"
          type="search"
          placeholder="Search username or email"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <select
          value={role}
          onChange={(e) => {
            setRole(e.target.value as UserRole | '')
            setPage(1)
          }}
          aria-label="Filter by role"
        >
          <option value="">All roles</option>
          <option value="user">Users</option>
          <option value="admin">Admins</option>
        </select>
        <select
          value={activeFilter}
          onChange={(e) => {
            setActiveFilter(e.target.value as ActiveFilter)
            setPage(1)
          }}
          aria-label="Filter by status"
        >
          <option value="all">Any status</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>
      </div>

      {loading && !data ? (
        <div className="empty">
          <span className="spinner" /> Loading users…
        </div>
      ) : data && data.items.length > 0 ? (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th className="right">Quota today</th>
                  <th className="right">Reports</th>
                  <th>Joined</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => {
                  const isSelf = row.id === user?.id
                  const busy = busyId === row.id
                  return (
                    <tr key={row.id}>
                      <td>
                        <div className="cell-url">
                          <span className="primary">
                            {row.username}
                            {isSelf ? <span className="you">you</span> : null}
                          </span>
                          <span className="secondary">{row.email}</span>
                        </div>
                      </td>
                      <td>
                        <select
                          value={row.role}
                          disabled={busy || isSelf}
                          title={isSelf ? 'You cannot change your own role' : undefined}
                          onChange={(e) => changeRole(row, e.target.value as UserRole)}
                          aria-label={`Role for ${row.username}`}
                        >
                          <option value="user">user</option>
                          <option value="admin">admin</option>
                        </select>
                      </td>
                      <td>
                        <span className={`pill ${row.is_active ? 'done' : 'failed'}`}>
                          {row.is_active ? 'active' : 'disabled'}
                        </span>
                      </td>
                      <td className="right mono">
                        {row.quota
                          ? `${row.quota.used_today} / ${row.quota.daily_limit}`
                          : '—'}
                      </td>
                      <td className="right mono">{row.report_count}</td>
                      <td style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(row.created_at)}
                      </td>
                      <td className="right">
                        <div className="row-actions">
                          <button
                            type="button"
                            className="btn ghost"
                            disabled={busy}
                            onClick={() => editQuota(row)}
                          >
                            Quota
                          </button>
                          <button
                            type="button"
                            className="btn ghost"
                            disabled={busy || isSelf}
                            title={isSelf ? 'You cannot disable your own account' : undefined}
                            onClick={() => toggleActive(row)}
                          >
                            {row.is_active ? 'Disable' : 'Enable'}
                          </button>
                          <button
                            type="button"
                            className="btn ghost"
                            disabled={busy}
                            onClick={() => revoke(row)}
                          >
                            Sign out
                          </button>
                          <button
                            type="button"
                            className="btn danger"
                            disabled={busy || isSelf}
                            title={isSelf ? 'You cannot delete your own account' : undefined}
                            onClick={() => remove(row)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 ? (
            <div className="pager">
              <span>
                Page {data.page} of {totalPages}
              </span>
              <div className="controls">
                <button
                  type="button"
                  className="btn secondary"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn secondary"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <div className="empty">
          <h3>No users match</h3>
          <p>Try clearing the search or filters.</p>
        </div>
      )}
    </div>
  )
}
