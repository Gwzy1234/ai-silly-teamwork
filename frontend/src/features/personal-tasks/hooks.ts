import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTeams } from '../teams/hooks'
import {
  checkSystemAdminAccess,
  countMyPersonalTasks,
  createPersonalTask,
  deletePersonalTask,
  getPersonalTask,
  getTaskAssignment,
  listMyPersonalTasks,
  listProjectPersonalTasks,
  listPersonalTaskAssignments,
  updateTaskAssignmentStatus,
} from './api'
import type {
  MyPersonalTaskFilters,
  ProjectPersonalTaskFilters,
  TaskAssignment,
} from './types'

export const personalTaskQueryKeys = {
  all: ['personal-tasks'] as const,
  mineRoot: ['personal-tasks', 'mine'] as const,
  mine: (filters: MyPersonalTaskFilters) =>
    ['personal-tasks', 'mine', filters] as const,
  mineCount: ['personal-tasks', 'mine', 'count'] as const,
  projectRoot: ['personal-tasks', 'project'] as const,
  project: (projectId: string, filters: ProjectPersonalTaskFilters) =>
    ['personal-tasks', 'project', projectId, filters] as const,
  detail: (taskId: string) => ['personal-tasks', taskId] as const,
  assignments: (taskId: string) =>
    ['personal-tasks', taskId, 'assignments'] as const,
  assignment: (assignmentId: string) =>
    ['task-assignments', assignmentId] as const,
  systemAdmin: ['auth', 'system-admin-status'] as const,
}

export function useMyPersonalTasks(filters: MyPersonalTaskFilters = {}) {
  return useQuery({
    queryKey: personalTaskQueryKeys.mine(filters),
    queryFn: () => listMyPersonalTasks(filters),
  })
}

export function useMyPersonalTaskCount() {
  return useQuery({
    queryKey: personalTaskQueryKeys.mineCount,
    queryFn: countMyPersonalTasks,
  })
}

export function useProjectPersonalTasks(
  projectId: string,
  filters: ProjectPersonalTaskFilters = {},
  enabled = true,
) {
  return useQuery({
    queryKey: personalTaskQueryKeys.project(projectId, filters),
    queryFn: () => listProjectPersonalTasks(projectId, filters),
    enabled: enabled && Boolean(projectId),
    retry: false,
  })
}

export function usePersonalTask(taskId: string) {
  return useQuery({
    queryKey: personalTaskQueryKeys.detail(taskId),
    queryFn: () => getPersonalTask(taskId),
    enabled: Boolean(taskId),
  })
}

export function usePersonalTaskAssignments(taskId: string) {
  return useQuery({
    queryKey: personalTaskQueryKeys.assignments(taskId),
    queryFn: () => listPersonalTaskAssignments(taskId),
    enabled: Boolean(taskId),
    retry: false,
  })
}

export function useTaskAssignment(assignmentId: string) {
  return useQuery({
    queryKey: personalTaskQueryKeys.assignment(assignmentId),
    queryFn: () => getTaskAssignment(assignmentId),
    enabled: Boolean(assignmentId),
  })
}

export function useCreatePersonalTask(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof createPersonalTask>[1]) =>
      createPersonalTask(projectId, payload),
    async onSuccess(result) {
      queryClient.setQueryData(personalTaskQueryKeys.detail(result.task.id), {
        task: result.task,
        my_assignment: null,
      })
      queryClient.setQueryData(
        personalTaskQueryKeys.assignments(result.task.id),
        result.assignments,
      )
      await queryClient.invalidateQueries({
        queryKey: personalTaskQueryKeys.mineRoot,
      })
      await queryClient.invalidateQueries({
        queryKey: personalTaskQueryKeys.projectRoot,
      })
    },
  })
}

export function useUpdateTaskAssignmentStatus(
  assignmentId: string,
  taskId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof updateTaskAssignmentStatus>[1]) =>
      updateTaskAssignmentStatus(assignmentId, payload),
    async onSuccess(updated) {
      queryClient.setQueryData<TaskAssignment>(
        personalTaskQueryKeys.assignment(assignmentId),
        updated,
      )
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: personalTaskQueryKeys.mineRoot,
        }),
        queryClient.invalidateQueries({
          queryKey: personalTaskQueryKeys.detail(taskId),
        }),
        queryClient.invalidateQueries({
          queryKey: personalTaskQueryKeys.assignments(taskId),
        }),
        queryClient.invalidateQueries({
          queryKey: personalTaskQueryKeys.mineCount,
        }),
      ])
    },
  })
}

export function useDeletePersonalTask(taskId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deletePersonalTask(taskId),
    async onSuccess() {
      queryClient.removeQueries({ queryKey: personalTaskQueryKeys.detail(taskId) })
      queryClient.removeQueries({
        queryKey: personalTaskQueryKeys.assignments(taskId),
      })
      await queryClient.invalidateQueries({
        queryKey: personalTaskQueryKeys.mineRoot,
      })
      await queryClient.invalidateQueries({
        queryKey: personalTaskQueryKeys.projectRoot,
      })
    },
  })
}

export function useCanPublishPersonalTask(teamId: string) {
  const teams = useTeams()
  const isTeamLeader =
    teams.data?.some((team) => team.id === teamId && team.role === 'leader') ?? false
  const systemAdmin = useQuery({
    queryKey: personalTaskQueryKeys.systemAdmin,
    queryFn: checkSystemAdminAccess,
    enabled: teams.isSuccess && !isTeamLeader && Boolean(teamId),
    retry: false,
    staleTime: 5 * 60_000,
  })

  return {
    canPublish: isTeamLeader || systemAdmin.data === true,
    isPending: teams.isPending || (!isTeamLeader && systemAdmin.isPending),
  }
}
