import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { TokenResponse } from './types'

const AUTH_STORAGE_KEY = 'silly-teamwork-auth'

function migrateLegacySession() {
  if (localStorage.getItem(AUTH_STORAGE_KEY)) return

  const legacySession = sessionStorage.getItem(AUTH_STORAGE_KEY)
  if (legacySession) {
    localStorage.setItem(AUTH_STORAGE_KEY, legacySession)
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
  }
}

migrateLegacySession()

interface AuthState {
  accessToken: string | null
  expiresAt: number | null
  hasHydrated: boolean
  setSession: (token: TokenResponse) => void
  clearSession: () => void
  finishHydration: () => void
  hasValidSession: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      expiresAt: null,
      hasHydrated: false,
      setSession: (token) => {
        set({
          accessToken: token.access_token,
          expiresAt: Date.now() + token.expires_in * 1000,
        })
      },
      clearSession: () => set({ accessToken: null, expiresAt: null }),
      finishHydration: () => {
        const { accessToken, expiresAt } = get()
        const sessionIsValid = Boolean(accessToken && expiresAt && expiresAt > Date.now())
        set({
          accessToken: sessionIsValid ? accessToken : null,
          expiresAt: sessionIsValid ? expiresAt : null,
          hasHydrated: true,
        })
      },
      hasValidSession: () => {
        const { accessToken, expiresAt } = get()
        return Boolean(accessToken && expiresAt && expiresAt > Date.now())
      },
    }),
    {
      name: AUTH_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: ({ accessToken, expiresAt }) => ({ accessToken, expiresAt }),
      onRehydrateStorage: () => (state) => state?.finishHydration(),
    },
  ),
)

export function clearAuthSession() {
  useAuthStore.getState().clearSession()
}
