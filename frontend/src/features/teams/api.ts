import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type {
  InvitationCode,
  InvitationCreateRequest,
  Team,
  TeamCreateRequest,
  TeamDetail,
  TeamJoinRequest,
  TeamMember,
} from './types'

export async function listTeams(): Promise<Team[]> {
  const { data, error, response } = await apiClient.GET('/api/v1/teams')
  if (!data) throw createApiError(response, error)
  return data
}

export async function createTeam(payload: TeamCreateRequest): Promise<Team> {
  const { data, error, response } = await apiClient.POST('/api/v1/teams', {
    body: payload,
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function joinTeam(payload: TeamJoinRequest): Promise<Team> {
  const { data, error, response } = await apiClient.POST('/api/v1/teams/join', {
    body: payload,
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function getTeam(teamId: string): Promise<TeamDetail> {
  const { data, error, response } = await apiClient.GET('/api/v1/teams/{team_id}', {
    params: { path: { team_id: teamId } },
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function deleteTeam(teamId: string): Promise<void> {
  const { error, response } = await apiClient.DELETE('/api/v1/teams/{team_id}', {
    params: { path: { team_id: teamId } },
  })
  if (!response.ok) throw createApiError(response, error)
}

export async function listTeamMembers(teamId: string): Promise<TeamMember[]> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/teams/{team_id}/members',
    { params: { path: { team_id: teamId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function createTeamInvitation(
  teamId: string,
  payload: InvitationCreateRequest,
): Promise<InvitationCode> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/teams/{team_id}/invite',
    {
      params: { path: { team_id: teamId } },
      body: payload,
    },
  )
  if (!data) throw createApiError(response, error)
  return data
}
