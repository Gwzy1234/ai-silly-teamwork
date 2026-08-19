import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { dashboardQueryKeys } from '../dashboard/hooks'
import { notificationQueryKeys } from '../notifications/hooks'
import {
  createTeam,
  createTeamInvitation,
  deleteTeam,
  getTeam,
  joinTeam,
  listTeamMembers,
  listTeams,
} from './api'

export const teamQueryKeys = {
  all: ['teams'] as const,
  detail: (teamId: string) => ['teams', teamId] as const,
  members: (teamId: string) => ['teams', teamId, 'members'] as const,
}

export function useTeams() {
  return useQuery({ queryKey: teamQueryKeys.all, queryFn: listTeams })
}

export function useTeam(teamId: string) {
  return useQuery({
    queryKey: teamQueryKeys.detail(teamId),
    queryFn: () => getTeam(teamId),
    enabled: Boolean(teamId),
  })
}

export function useTeamMembers(teamId: string) {
  return useQuery({
    queryKey: teamQueryKeys.members(teamId),
    queryFn: () => listTeamMembers(teamId),
    enabled: Boolean(teamId),
  })
}

export function useCreateTeam() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createTeam,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: teamQueryKeys.all }),
  })
}

export function useJoinTeam() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: joinTeam,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: teamQueryKeys.all }),
  })
}

export function useDeleteTeam(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => deleteTeam(teamId),
    async onSuccess() {
      queryClient.removeQueries({ queryKey: teamQueryKeys.detail(teamId) })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: teamQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: ['projects'] }),
        queryClient.invalidateQueries({ queryKey: ['tasks'] }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.upcomingRoot }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.overdue }),
        queryClient.invalidateQueries({ queryKey: notificationQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: ['files', 'index'] }),
      ])
    },
  })
}

export function useCreateTeamInvitation(teamId: string) {
  return useMutation({
    mutationFn: (payload: Parameters<typeof createTeamInvitation>[1]) =>
      createTeamInvitation(teamId, payload),
  })
}
