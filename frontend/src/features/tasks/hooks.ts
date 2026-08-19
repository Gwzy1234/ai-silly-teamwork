import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { dashboardQueryKeys } from '../dashboard/hooks'
import { notificationQueryKeys } from '../notifications/hooks'
import {
  addTaskMember,
  createTask,
  deleteTask,
  getTask,
  listTaskMembers,
  listTasks,
  removeTaskMember,
  transferTaskOwner,
  updateTask,
  updateTaskStatus,
} from './api'
import type { TaskStatus } from './types'

export const taskQueryKeys = {
  projectTasks: (projectId: string) => ['projects', projectId, 'tasks'] as const,
  detail: (taskId: string) => ['tasks', taskId] as const,
  members: (taskId: string) => ['tasks', taskId, 'members'] as const,
}

export function useTasks(projectId: string) {
  return useQuery({
    queryKey: taskQueryKeys.projectTasks(projectId),
    queryFn: () => listTasks(projectId),
    enabled: Boolean(projectId),
  })
}

export function useTask(taskId: string) {
  return useQuery({
    queryKey: taskQueryKeys.detail(taskId),
    queryFn: () => getTask(taskId),
    enabled: Boolean(taskId),
  })
}

export function useTaskMembers(taskId: string) {
  return useQuery({
    queryKey: taskQueryKeys.members(taskId),
    queryFn: () => listTaskMembers(taskId),
    enabled: Boolean(taskId),
  })
}

export function useTaskMemberQueries(taskIds: string[]) {
  return useQueries({
    queries: taskIds.map((taskId) => ({
      queryKey: taskQueryKeys.members(taskId),
      queryFn: () => listTaskMembers(taskId),
    })),
  })
}

async function invalidateDeadlineDashboard(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.upcomingRoot }),
    queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.overdue }),
    queryClient.invalidateQueries({ queryKey: notificationQueryKeys.all }),
  ])
}

export function useCreateTask(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof createTask>[1]) => createTask(projectId, payload),
    onSuccess: (task) => {
      queryClient.setQueryData<Awaited<ReturnType<typeof listTasks>>>(
        taskQueryKeys.projectTasks(projectId),
        (current = []) => current.some((item) => item.id === task.id) ? current : [task, ...current],
      )
      void queryClient.invalidateQueries({ queryKey: taskQueryKeys.projectTasks(projectId) })
      void invalidateDeadlineDashboard(queryClient)
    },
  })
}

export function useDeleteTask(taskId: string, projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deleteTask(taskId),
    async onSuccess() {
      queryClient.removeQueries({ queryKey: taskQueryKeys.detail(taskId) })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: taskQueryKeys.projectTasks(projectId) }),
        invalidateDeadlineDashboard(queryClient),
        queryClient.invalidateQueries({ queryKey: ['files', 'index'] }),
        queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'file-index'] }),
      ])
    },
  })
}

function useTaskMutationInvalidation(taskId: string, projectId: string) {
  const queryClient = useQueryClient()
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: taskQueryKeys.detail(taskId) }),
      queryClient.invalidateQueries({ queryKey: taskQueryKeys.members(taskId) }),
      queryClient.invalidateQueries({ queryKey: taskQueryKeys.projectTasks(projectId) }),
      invalidateDeadlineDashboard(queryClient),
    ])
  }
}

export function useUpdateTask(taskId: string, projectId: string) {
  const invalidate = useTaskMutationInvalidation(taskId, projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof updateTask>[1]) => updateTask(taskId, payload),
    onSuccess: invalidate,
  })
}

export function useUpdateTaskStatus(taskId: string, projectId: string) {
  const invalidate = useTaskMutationInvalidation(taskId, projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof updateTaskStatus>[1]) =>
      updateTaskStatus(taskId, payload),
    onSuccess: invalidate,
  })
}

export function useBoardTaskStatus(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: TaskStatus }) =>
      updateTaskStatus(taskId, { status }),
    onSuccess: async (_, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: taskQueryKeys.detail(variables.taskId) }),
        queryClient.invalidateQueries({ queryKey: taskQueryKeys.projectTasks(projectId) }),
        invalidateDeadlineDashboard(queryClient),
      ])
    },
  })
}

export function useAddTaskMember(taskId: string, projectId: string) {
  const invalidate = useTaskMutationInvalidation(taskId, projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof addTaskMember>[1]) => addTaskMember(taskId, payload),
    onSuccess: invalidate,
  })
}

export function useRemoveTaskMember(taskId: string, projectId: string) {
  const invalidate = useTaskMutationInvalidation(taskId, projectId)
  return useMutation({
    mutationFn: (userId: string) => removeTaskMember(taskId, userId),
    onSuccess: invalidate,
  })
}

export function useTransferTaskOwner(taskId: string, projectId: string) {
  const invalidate = useTaskMutationInvalidation(taskId, projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof transferTaskOwner>[1]) =>
      transferTaskOwner(taskId, payload),
    onSuccess: invalidate,
  })
}
