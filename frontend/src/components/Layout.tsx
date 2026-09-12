/**
 * The signed-in shell: a sticky header, and the view under it.
 *
 * The header is the one piece of chrome that survived the redesign more or less
 * intact, because it was already doing its job. What changed is the right-hand
 * side: the username and a bare "Sign out" button have become a real menu, so
 * account, admin and sign-out live together instead of being spread between the
 * header and the nav, and the destructive one is not a single stray click away.
 */
import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom'
import { ChevronDown, LogOut, Shield, UserRound } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/app', label: 'Page audit', end: true },
  { to: '/site-audit', label: 'Site audit', end: false },
]

export function Layout() {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <TooltipProvider>
      {/*
        Keyboard users land on this first and can jump the nav. It is visually
        hidden until focused, which is the only state it needs to be seen in.
      */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-lg focus:bg-background focus:px-3 focus:py-2 focus:text-[13.5px] focus:font-medium focus:shadow-[var(--shadow-raised)]"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-50 h-(--header-h) border-b border-border bg-background/85 backdrop-blur-md backdrop-saturate-150">
        <div className="mx-auto flex h-full max-w-(--measure) items-center gap-3 px-5 sm:px-6">
          <Link
            to="/"
            className="flex shrink-0 items-center gap-2.5 font-semibold tracking-tight whitespace-nowrap"
          >
            <span className="size-2.5 rounded-full bg-primary ring-4 ring-accent-soft" />
            <span className="hidden sm:inline">SEO Analysis</span>
          </Link>

          <nav aria-label="Main" className="ml-1 flex items-center gap-0.5">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-lg px-2.5 py-1.5 text-[13.5px] transition-colors sm:px-3',
                    isActive
                      ? 'bg-accent-soft font-medium text-accent-on-tint'
                      : 'text-muted-foreground hover:bg-surface hover:text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
            {isAdmin ? (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  cn(
                    'rounded-lg px-2.5 py-1.5 text-[13.5px] transition-colors sm:px-3',
                    isActive
                      ? 'bg-accent-soft font-medium text-accent-on-tint'
                      : 'text-muted-foreground hover:bg-surface hover:text-foreground',
                  )
                }
              >
                Users
              </NavLink>
            ) : null}
          </nav>

          <span className="flex-1" />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="max-w-[40vw] gap-1.5 px-2 font-medium sm:max-w-none"
              >
                <span className="truncate">{user?.username}</span>
                {isAdmin ? (
                  <Badge
                    variant="info"
                    className="px-1.5 py-0 text-[9.5px] font-bold tracking-[0.06em] uppercase"
                  >
                    Admin
                  </Badge>
                ) : null}
                <ChevronDown className="size-3.5 opacity-55" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[200px]">
              <DropdownMenuLabel className="normal-case">
                <span className="block truncate text-[13px] font-normal tracking-normal text-foreground">
                  {user?.email}
                </span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/account">
                  <UserRound />
                  Account settings
                </Link>
              </DropdownMenuItem>
              {isAdmin ? (
                <DropdownMenuItem asChild>
                  <Link to="/admin">
                    <Shield />
                    User directory
                  </Link>
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={handleSignOut}>
                <LogOut />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-(--measure) px-5 pt-10 pb-28 sm:px-6">
        <Outlet />
      </main>
    </TooltipProvider>
  )
}
