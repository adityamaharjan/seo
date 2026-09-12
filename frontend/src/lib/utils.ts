import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Joins class names and lets a later Tailwind utility beat an earlier one.
 *
 * The plain concatenation shadcn ships without `tailwind-merge` leaves both
 * classes in the list and hands the decision to stylesheet order, so a caller
 * passing `px-2` to a component whose base is `px-4` gets whichever Tailwind
 * happened to emit last. Merging resolves it by intent instead: the caller wins.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
