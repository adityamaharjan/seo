/**
 * The theme control.
 *
 * A menu rather than a two-state switch, because the useful default is a third
 * state: follow the machine. A switch can only ever say light or dark, so the
 * moment a user touches it they lose the OS handoff and never get it back
 * without clearing storage. The trigger shows what is currently on screen; the
 * menu shows what was chosen, which are different things while "System" is
 * selected and the label spells that out.
 */
import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme, type ThemeChoice } from '../theme/ThemeContext'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

const OPTIONS: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, resolved, setTheme } = useTheme()
  const chosen = OPTIONS.find((option) => option.value === theme) ?? OPTIONS[2]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          className={cn('text-muted-foreground hover:text-foreground', className)}
          aria-label={`Theme: ${chosen.label.toLowerCase()}. Change theme`}
        >
          {/*
            The icon crossfades rather than swapping, so the change reads as the
            same control turning over instead of one button replacing another.
          */}
          <span className="relative grid size-4 place-items-center">
            <Sun
              aria-hidden="true"
              className={cn(
                'absolute size-4 transition-all duration-300 motion-reduce:transition-none',
                resolved === 'dark'
                  ? '-rotate-90 scale-0 opacity-0'
                  : 'rotate-0 scale-100 opacity-100',
              )}
            />
            <Moon
              aria-hidden="true"
              className={cn(
                'absolute size-4 transition-all duration-300 motion-reduce:transition-none',
                resolved === 'dark'
                  ? 'rotate-0 scale-100 opacity-100'
                  : 'rotate-90 scale-0 opacity-0',
              )}
            />
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[148px]">
        <DropdownMenuRadioGroup
          value={theme}
          onValueChange={(value) => setTheme(value as ThemeChoice)}
        >
          {OPTIONS.map(({ value, label, icon: Icon }) => (
            <DropdownMenuRadioItem key={value} value={value}>
              <Icon aria-hidden="true" className="opacity-70" />
              {label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
