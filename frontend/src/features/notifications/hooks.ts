import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  listNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
} from './api'
import type { Notification } from './types'

export const notificationQueryKeys = {
  all: ['notifications'] as const,
}

export function useNotifications() {
  return useQuery({
    queryKey: notificationQueryKeys.all,
    queryFn: listNotifications,
  })
}

export function useMarkNotificationAsRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: markNotificationAsRead,
    onSuccess: (updated) => {
      queryClient.setQueryData<Notification[]>(notificationQueryKeys.all, (current = []) =>
        current.map((item) => item.id === updated.id ? updated : item),
      )
      void queryClient.invalidateQueries({ queryKey: notificationQueryKeys.all })
    },
  })
}

export function useMarkAllNotificationsAsRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: markAllNotificationsAsRead,
    onSuccess: () => {
      const readAt = new Date().toISOString()
      queryClient.setQueryData<Notification[]>(notificationQueryKeys.all, (current = []) =>
        current.map((item) => item.is_read ? item : { ...item, is_read: true, read_at: readAt }),
      )
      void queryClient.invalidateQueries({ queryKey: notificationQueryKeys.all })
    },
  })
}
