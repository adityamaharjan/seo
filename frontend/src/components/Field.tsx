/**
 * A labelled text input with its hint or error wired up.
 *
 * Every form in the app was repeating the same four elements by hand, and the
 * wiring drifted: some inputs pointed `aria-describedby` at their hint, most
 * did not, and an input showing an error usually left the error unassociated,
 * so a screen reader announced the field as invalid without saying why. Doing
 * it in one place makes that correct everywhere at once.
 *
 * An error replaces the hint rather than stacking under it. Both at once makes
 * the field taller at the exact moment the reader is trying to fix something,
 * and the error is the more useful of the two.
 */
import type { ComponentProps, ReactNode } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

interface Props extends Omit<ComponentProps<'input'>, 'id'> {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  /** Marks the field as not required, in words rather than by omission. */
  optional?: boolean
  containerClassName?: string
}

export function TextField({
  id,
  label,
  hint,
  error,
  optional,
  containerClassName,
  className,
  ...inputProps
}: Props) {
  const messageId = error ? `${id}-error` : hint ? `${id}-hint` : undefined

  return (
    <div className={cn('grid gap-1.5', containerClassName)}>
      <Label htmlFor={id}>
        {label}
        {optional ? (
          <span className="font-normal text-muted-foreground">optional</span>
        ) : null}
      </Label>
      <Input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={messageId}
        className={cn('h-10', className)}
        {...inputProps}
      />
      {error ? (
        <p id={messageId} className="text-[12.5px] text-crit">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="text-[12.5px] text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
