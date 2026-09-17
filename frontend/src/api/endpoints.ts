/** Typed wrappers around every endpoint the UI uses. */
import { request } from './client'
import type {
  AnalysisAccepted,
  ApiKeyProvider,
  ApiKeySettings,
  Paginated,
  PsiScope,
  Quota,
  ReportDetail,
  ReportSummary,
  SiteAuditAccepted,
  SiteAuditDetail,
  SiteAuditPageDetail,
  SiteAuditSummary,
  SessionsRevoked,
  TokenPair,
  User,
  UserDetail,
  UserRole,
} from './types'

export const authApi = {
  signup: (username: string, email: string, password: string) =>
    request<User>('/auth/signup', {
      method: 'POST',
      body: { username, email, password },
      auth: false,
    }),

  login: (email: string, password: string) =>
    request<TokenPair>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    }),

  logout: (refresh_token: string) =>
    request<void>('/auth/logout', {
      method: 'POST',
      body: { refresh_token },
      auth: false,
    }),

  me: () => request<User>('/auth/me'),
}

export const quotaApi = {
  status: () => request<Quota>('/users/me/quota'),
}

export const accountApi = {
  updateProfile: (changes: { username?: string; email?: string }) =>
    request<User>('/users/me', { method: 'PATCH', body: changes }),

  changePassword: (current_password: string, new_password: string) =>
    request<SessionsRevoked>('/users/me/password', {
      method: 'POST',
      body: { current_password, new_password },
    }),
}

export const apiKeysApi = {
  list: () => request<ApiKeySettings>('/users/me/api-keys'),

  save: (provider: ApiKeyProvider, key: string) =>
    request<ApiKeySettings>(`/users/me/api-keys/${provider}`, {
      method: 'PUT',
      body: { key },
    }),

  remove: (provider: ApiKeyProvider) =>
    request<void>(`/users/me/api-keys/${provider}`, { method: 'DELETE' }),
}

export interface UserListFilters {
  page?: number
  pageSize?: number
  search?: string
  role?: UserRole | ''
  isActive?: boolean | null
}

export const adminApi = {
  listUsers: (filters: UserListFilters = {}) => {
    const params = new URLSearchParams()
    params.set('page', String(filters.page ?? 1))
    params.set('page_size', String(filters.pageSize ?? 20))
    if (filters.search) params.set('search', filters.search)
    if (filters.role) params.set('role', filters.role)
    if (filters.isActive !== null && filters.isActive !== undefined) {
      params.set('is_active', String(filters.isActive))
    }
    return request<Paginated<UserDetail>>(`/admin/users?${params.toString()}`)
  },

  getUser: (id: number) => request<UserDetail>(`/admin/users/${id}`),

  updateUser: (id: number, changes: { role?: UserRole; is_active?: boolean }) =>
    request<UserDetail>(`/admin/users/${id}`, { method: 'PATCH', body: changes }),

  updateQuota: (id: number, limits: { daily_limit?: number; monthly_limit?: number }) =>
    request<UserDetail>(`/admin/users/${id}/quota`, { method: 'PATCH', body: limits }),

  revokeSessions: (id: number) =>
    request<SessionsRevoked>(`/admin/users/${id}/revoke-sessions`, { method: 'POST' }),

  deleteUser: (id: number) =>
    request<void>(`/admin/users/${id}`, { method: 'DELETE' }),
}

export const analysesApi = {
  /**
   * `usePsi` is tri-state on purpose: `undefined` follows whatever key the
   * account has, `true` insists (and is rejected with a 400 when no key is
   * saved), `false` skips PageSpeed without having to delete the stored key.
   */
  submit: (url: string, targetKeywords: string[] = [], usePsi?: boolean) =>
    request<AnalysisAccepted>('/analyses', {
      method: 'POST',
      body: { url, target_keywords: targetKeywords, use_psi: usePsi },
    }),

  list: (page = 1, pageSize = 20) =>
    request<Paginated<ReportSummary>>(`/analyses?page=${page}&page_size=${pageSize}`),

  get: (id: number, signal?: AbortSignal) =>
    request<ReportDetail>(`/analyses/${id}`, { signal }),

  remove: (id: number) => request<void>(`/analyses/${id}`, { method: 'DELETE' }),
}

/**
 * Site audits: crawl many pages of one site. Deliberately separate from
 * analysesApi — a site audit takes a page budget and never takes keywords.
 */
export const siteAuditsApi = {
  submit: (url: string, maxPages: number, usePsi?: boolean, psiScope?: PsiScope) =>
    request<SiteAuditAccepted>('/site-audits', {
      method: 'POST',
      body: { url, max_pages: maxPages, use_psi: usePsi, psi_scope: psiScope },
    }),

  list: (page = 1, pageSize = 20) =>
    request<Paginated<SiteAuditSummary>>(
      `/site-audits?page=${page}&page_size=${pageSize}`,
    ),

  get: (id: number, signal?: AbortSignal) =>
    request<SiteAuditDetail>(`/site-audits/${id}`, { signal }),

  getPage: (auditId: number, pageId: number) =>
    request<SiteAuditPageDetail>(`/site-audits/${auditId}/pages/${pageId}`),

  remove: (id: number) => request<void>(`/site-audits/${id}`, { method: 'DELETE' }),
}
