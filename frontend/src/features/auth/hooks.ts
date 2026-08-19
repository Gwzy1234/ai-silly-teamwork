import { useMutation, useQuery } from '@tanstack/react-query'
import { queryClient } from '../../app/query-client'
import {
  changePassword,
  deleteAvatar,
  getCurrentUser,
  login,
  register,
  updateCurrentUser,
  uploadAvatar,
} from './api'
import { clearAuthSession, useAuthStore } from './store'
import type { User } from './types'

export const authQueryKeys = {
  currentUser: ['auth', 'current-user'] as const,
}

export function useCurrentUser() {
  const accessToken = useAuthStore((state) => state.accessToken)
  const expiresAt = useAuthStore((state) => state.expiresAt)
  const hasHydrated = useAuthStore((state) => state.hasHydrated)
  const sessionIsValid = Boolean(accessToken && expiresAt && expiresAt > Date.now())

  return useQuery({
    queryKey: authQueryKeys.currentUser,
    queryFn: () => getCurrentUser(),
    enabled: hasHydrated && sessionIsValid,
    retry: false,
    staleTime: 60_000,
  })
}

export function useLogin() {
  const setSession = useAuthStore((state) => state.setSession)

  return useMutation({
    async mutationFn(payload: Parameters<typeof login>[0]) {
      const token = await login(payload)
      const user = await getCurrentUser(token.access_token)
      return { token, user }
    },
    onSuccess({ token, user }) {
      setSession(token)
      setCurrentUser(user)
    },
  })
}

export function useRegister() {
  return useMutation({ mutationFn: register })
}

export function useUpdateCurrentUser() {
  return useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: setCurrentUser,
  })
}

export function useChangePassword() {
  return useMutation({ mutationFn: changePassword })
}

export function useUploadAvatar() {
  return useMutation({
    mutationFn: uploadAvatar,
    onSuccess: setCurrentUser,
  })
}

export function useDeleteAvatar() {
  return useMutation({
    mutationFn: deleteAvatar,
    async onSuccess() {
      queryClient.setQueryData<User>(authQueryKeys.currentUser, (currentUser) =>
        currentUser ? { ...currentUser, avatar_url: null } : currentUser,
      )
      await queryClient.invalidateQueries({ queryKey: authQueryKeys.currentUser })
    },
  })
}

export function setCurrentUser(user: User) {
  queryClient.setQueryData(authQueryKeys.currentUser, user)
}

export function logout() {
  clearAuthSession()
  queryClient.clear()
}
