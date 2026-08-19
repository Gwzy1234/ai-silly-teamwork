import createClient, { type Middleware } from 'openapi-fetch'
import type { paths } from './generated/schema'
import { queryClient } from '../app/query-client'
import { clearAuthSession, useAuthStore } from '../features/auth/store'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

export const apiClient = createClient<paths>({ baseUrl: apiBaseUrl })

export function resolveApiUrl(path: string | null | undefined) {
  if (!path) return undefined
  if (/^https?:\/\//i.test(path)) return path
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return apiBaseUrl ? `${apiBaseUrl.replace(/\/+$/, '')}${normalizedPath}` : normalizedPath
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const { accessToken, expiresAt } = useAuthStore.getState()
    if (!accessToken || !expiresAt || expiresAt <= Date.now()) {
      if (accessToken) {
        clearAuthSession()
      }
      return request
    }

    const headers = new Headers(request.headers)
    headers.set('Authorization', `Bearer ${accessToken}`)
    return new Request(request, { headers })
  },
  onResponse({ response }) {
    if (response.status === 401 && useAuthStore.getState().accessToken) {
      clearAuthSession()
      queryClient.clear()
    }
    return response
  },
}

apiClient.use(authMiddleware)
