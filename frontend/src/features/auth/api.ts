import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type {
  LoginRequest,
  PasswordChangeRequest,
  RegisterRequest,
  TokenResponse,
  User,
  UserProfileUpdate,
} from './types'

const avatarMultipartSerializer = (body: { file: File }) => {
  const formData = new FormData()
  formData.append('file', body.file)
  return formData
}

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const { data, error, response } = await apiClient.POST('/api/v1/auth/login', {
    body: payload,
  })
  if (!data) {
    throw createApiError(response, error)
  }
  return data
}

export async function register(payload: RegisterRequest): Promise<User> {
  const { data, error, response } = await apiClient.POST('/api/v1/auth/register', {
    body: payload,
  })
  if (!data) {
    throw createApiError(response, error)
  }
  return data
}

export async function getCurrentUser(accessToken?: string): Promise<User> {
  const { data, error, response } = await apiClient.GET('/api/v1/users/me', {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  })
  if (!data) {
    throw createApiError(response, error)
  }
  return data
}

export async function updateCurrentUser(payload: UserProfileUpdate): Promise<User> {
  const { data, error, response } = await apiClient.PATCH('/api/v1/users/me', {
    body: payload,
  })
  if (!data) {
    throw createApiError(response, error)
  }
  return data
}

export async function changePassword(payload: PasswordChangeRequest): Promise<void> {
  const { error, response } = await apiClient.PATCH('/api/v1/users/me/password', {
    body: payload,
  })
  if (!response.ok) {
    throw createApiError(response, error)
  }
}

export async function uploadAvatar(file: File): Promise<User> {
  const { data, error, response } = await apiClient.POST('/api/v1/users/me/avatar', {
    body: { file: file as unknown as string },
    bodySerializer: avatarMultipartSerializer as never,
  })
  if (!data) {
    throw createApiError(response, error)
  }
  return data
}

export async function deleteAvatar(): Promise<void> {
  const { error, response } = await apiClient.DELETE('/api/v1/users/me/avatar')
  if (!response.ok) {
    throw createApiError(response, error)
  }
}
