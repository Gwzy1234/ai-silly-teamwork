import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type { DashboardTask } from './types'

export async function listUpcomingTasks(hours = 72): Promise<DashboardTask[]> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks/upcoming', {
    params: { query: { hours } },
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function listOverdueTasks(): Promise<DashboardTask[]> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks/overdue')
  if (!data) throw createApiError(response, error)
  return data
}
