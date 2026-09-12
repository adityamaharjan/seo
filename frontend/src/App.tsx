/**
 * Routing, and the two providers everything below depends on.
 *
 * Every view is loaded on demand. The landing page is the first thing most
 * visitors see and it needs none of the admin table, the report renderer or the
 * site-audit views, all of which are the heavy part of the app; importing them
 * eagerly meant the marketing page paid for the whole product before it drew a
 * single word. Splitting at the route is the one boundary that is both obvious
 * and stable, and React Router already suspends for it.
 */
import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ThemeProvider } from './theme/ThemeContext'
import { RequireAdmin } from './components/RequireAdmin'
import { RequireAuth } from './components/RequireAuth'
import { RouteFallback } from './components/RouteFallback'

const Layout = lazy(() => import('./components/Layout').then((m) => ({ default: m.Layout })))
const Account = lazy(() => import('./routes/Account').then((m) => ({ default: m.Account })))
const Admin = lazy(() => import('./routes/Admin').then((m) => ({ default: m.Admin })))
const PageAudit = lazy(() => import('./routes/PageAudit').then((m) => ({ default: m.PageAudit })))
const Landing = lazy(() => import('./routes/Landing').then((m) => ({ default: m.Landing })))
const Login = lazy(() => import('./routes/Login').then((m) => ({ default: m.Login })))
const NotFound = lazy(() => import('./routes/NotFound').then((m) => ({ default: m.NotFound })))
const Report = lazy(() => import('./routes/Report').then((m) => ({ default: m.Report })))
const SiteAudit = lazy(() => import('./routes/SiteAudit').then((m) => ({ default: m.SiteAudit })))
const SiteAuditPage = lazy(() =>
  import('./routes/SiteAuditPage').then((m) => ({ default: m.SiteAuditPage })),
)
const SiteAuditReport = lazy(() =>
  import('./routes/SiteAuditReport').then((m) => ({ default: m.SiteAuditReport })),
)
const Signup = lazy(() => import('./routes/Signup').then((m) => ({ default: m.Signup })))

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          {/*
            One boundary around the whole switch. A per-route boundary would let
            the header render while the view below it was still arriving, which
            sounds better and is worse: the chrome appears twice on a cold load,
            once outside the shell and once inside it.
          */}
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              {/* Marketing lives at the root; the product lives under /app. */}
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
              <Route
                element={
                  <RequireAuth>
                    <Layout />
                  </RequireAuth>
                }
              >
                <Route path="/app" element={<PageAudit />} />
                <Route path="/report/:id" element={<Report />} />
                <Route path="/site-audit" element={<SiteAudit />} />
                <Route path="/site-audit/:id" element={<SiteAuditReport />} />
                <Route
                  path="/site-audit/:auditId/page/:pageId"
                  element={<SiteAuditPage />}
                />
                <Route path="/account" element={<Account />} />
                <Route
                  path="/admin"
                  element={
                    <RequireAdmin>
                      <Admin />
                    </RequireAdmin>
                  }
                />
                <Route path="/404" element={<NotFound />} />
              </Route>
              <Route path="*" element={<Navigate to="/404" replace />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}
