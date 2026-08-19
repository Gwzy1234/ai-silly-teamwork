import { useQuery } from '@tanstack/react-query'
import { listOverdueTasks, listUpcomingTasks } from './api'

export const dashboardQueryKeys = {
  upcomingRoot: ['tasks', 'upcoming'] as const,
  upcoming: (hours: number) => ['tasks', 'upcoming', hours] as const,
  overdue: ['tasks', 'overdue'] as const,
}

export function useUpcomingTasks(hours = 72) {
  return useQuery({
    queryKey: dashboardQueryKeys.upcoming(hours),
    queryFn: () => listUpcomingTasks(hours),
    refetchOnMount: 'always',
  })
}

export function useOverdueTasks() {
  return useQuery({
    queryKey: dashboardQueryKeys.overdue,
    queryFn: listOverdueTasks,
    refetchOnMount: 'always',
  })
}
