import { useEffect } from 'react'
import { logout } from '../hooks'
import { useAuthStore } from '../store'

const MAX_TIMEOUT_MS = 2_147_483_647

export function SessionExpiryWatcher() {
  const expiresAt = useAuthStore((state) => state.expiresAt)

  useEffect(() => {
    if (!expiresAt) {
      return
    }
    const remaining = expiresAt - Date.now()
    if (remaining <= 0) {
      logout()
      return
    }
    const timer = window.setTimeout(logout, Math.min(remaining, MAX_TIMEOUT_MS))
    return () => window.clearTimeout(timer)
  }, [expiresAt])

  return null
}
