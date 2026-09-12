import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { RequireAdmin } from './components/RequireAdmin'
import { RequireAuth } from './components/RequireAuth'
import { Account } from './routes/Account'
import { Admin } from './routes/Admin'
import { PageAudit } from './routes/PageAudit'
import { Landing } from './routes/Landing'
import { Login } from './routes/Login'
import { NotFound } from './routes/NotFound'
import { Report } from './routes/Report'
import { SiteAudit } from './routes/SiteAudit'
import { SiteAuditPage } from './routes/SiteAuditPage'
import { SiteAuditReport } from './routes/SiteAuditReport'
import { Signup } from './routes/Signup'

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
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
      </AuthProvider>
    </BrowserRouter>
  )
}
