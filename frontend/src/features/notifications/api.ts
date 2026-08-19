import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type { MarkAllNotificationsReadResponse, Notification } from './types'

export async function listNotifications(): Promise<Notification[]> {
  const { data, error, response } = await apiClient.GET('/api/v1/notifications')
  if (!data) throw createApiError(response, error)
  return data
}

export async function markNotificationAsRead(notificationId: string): Promise<Notification> {
  const { data, error, response } = await apiClient.PATCH(
    '/api/v1/notifications/{notification_id}/read',
    { params: { path: { notification_id: notificationId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function markAllNotificationsAsRead(): Promise<MarkAllNotificationsReadResponse> {
  const { data, error, response } = await apiClient.PATCH('/api/v1/notifications/read-all')
  if (!data) throw createApiError(response, error)
  return data
}
