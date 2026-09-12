import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function Layout() {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <header className="app-header">
        {/* The wordmark goes home, which is the public landing page. The nav
            below is how you get to the product itself. */}
        <Link to="/" className="brand">
          <span className="dot" />
          SEO Analysis
        </Link>
        <nav>
          <NavLink to="/app" end className={({ isActive }) => (isActive ? 'active' : '')}>
            Page audit
          </NavLink>
          <NavLink
            to="/site-audit"
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            Site audit
          </NavLink>
          {isAdmin ? (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? 'active' : '')}>
              Users
            </NavLink>
          ) : null}
        </nav>
        <span className="spacer" />
        <div className="who">
          <Link to="/account" className="who-name">
            {user?.username}
            {isAdmin ? <span className="badge-admin">admin</span> : null}
          </Link>
          <button type="button" className="btn ghost" onClick={handleSignOut}>
            Sign out
          </button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
