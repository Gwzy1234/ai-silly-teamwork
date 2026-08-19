import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { dashboardQueryKeys } from '../dashboard/hooks'
import { notificationQueryKeys } from '../notifications/hooks'
import {
  addProjectMember,
  createProject,
  deleteProject,
  getProject,
  listProjectMembers,
  listProjects,
  removeProjectMember,
  transferProjectOwner,
  updateProject,
  updateProjectStatus,
} from './api'

export const projectQueryKeys = {
  teamProjects: (teamId: string) => ['teams', teamId, 'projects'] as const,
  detail: (projectId: string) => ['projects', projectId] as const,
  members: (projectId: string) => ['projects', projectId, 'members'] as const,
}

export function useProjects(teamId: string) {
  return useQuery({
    queryKey: projectQueryKeys.teamProjects(teamId),
    queryFn: () => listProjects(teamId),
    enabled: Boolean(teamId),
  })
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: projectQueryKeys.detail(projectId),
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
  })
}

export function useProjectMembers(projectId: string) {
  return useQuery({
    queryKey: projectQueryKeys.members(projectId),
    queryFn: () => listProjectMembers(projectId),
    enabled: Boolean(projectId),
  })
}

export function useCreateProject(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof createProject>[1]) =>
      createProject(teamId, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.teamProjects(teamId) }),
  })
}

export function useDeleteProject(projectId: string, teamId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deleteProject(projectId),
    async onSuccess() {
      queryClient.removeQueries({ queryKey: projectQueryKeys.detail(projectId) })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: projectQueryKeys.teamProjects(teamId) }),
        queryClient.invalidateQueries({ queryKey: ['tasks'] }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.upcomingRoot }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.overdue }),
        queryClient.invalidateQueries({ queryKey: notificationQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: ['files', 'index'] }),
      ])
    },
  })
}

function useProjectMutationInvalidation(projectId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['teams'] })
    void queryClient.invalidateQueries({ queryKey: projectQueryKeys.detail(projectId) })
    void queryClient.invalidateQueries({ queryKey: projectQueryKeys.members(projectId) })
  }
}

export function useUpdateProject(projectId: string) {
  const invalidate = useProjectMutationInvalidation(projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof updateProject>[1]) =>
      updateProject(projectId, payload),
    onSuccess: invalidate,
  })
}

export function useUpdateProjectStatus(projectId: string) {
  const invalidate = useProjectMutationInvalidation(projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof updateProjectStatus>[1]) =>
      updateProjectStatus(projectId, payload),
    onSuccess: invalidate,
  })
}

export function useAddProjectMember(projectId: string) {
  const invalidate = useProjectMutationInvalidation(projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof addProjectMember>[1]) =>
      addProjectMember(projectId, payload),
    onSuccess: invalidate,
  })
}

export function useRemoveProjectMember(projectId: string) {
  const invalidate = useProjectMutationInvalidation(projectId)
  return useMutation({
    mutationFn: (userId: string) => removeProjectMember(projectId, userId),
    onSuccess: invalidate,
  })
}

export function useTransferProjectOwner(projectId: string) {
  const invalidate = useProjectMutationInvalidation(projectId)
  return useMutation({
    mutationFn: (payload: Parameters<typeof transferProjectOwner>[1]) =>
      transferProjectOwner(projectId, payload),
    onSuccess: invalidate,
  })
}
