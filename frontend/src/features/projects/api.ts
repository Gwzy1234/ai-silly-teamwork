import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type {
  Project,
  ProjectCreate,
  ProjectMember,
  ProjectMemberAdd,
  ProjectOwnerTransfer,
  ProjectStatusUpdate,
  ProjectUpdate,
} from './types'

export async function listProjects(teamId: string): Promise<Project[]> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/teams/{team_id}/projects',
    { params: { path: { team_id: teamId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function createProject(teamId: string, payload: ProjectCreate): Promise<Project> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/teams/{team_id}/projects',
    { params: { path: { team_id: teamId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function getProject(projectId: string): Promise<Project> {
  const { data, error, response } = await apiClient.GET('/api/v1/projects/{project_id}', {
    params: { path: { project_id: projectId } },
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function deleteProject(projectId: string): Promise<void> {
  const { error, response } = await apiClient.DELETE('/api/v1/projects/{project_id}', {
    params: { path: { project_id: projectId } },
  })
  if (!response.ok) throw createApiError(response, error)
}

export async function updateProject(
  projectId: string,
  payload: ProjectUpdate,
): Promise<Project> {
  const { data, error, response } = await apiClient.PATCH(
    '/api/v1/projects/{project_id}',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function updateProjectStatus(
  projectId: string,
  payload: ProjectStatusUpdate,
): Promise<Project> {
  const { data, error, response } = await apiClient.PATCH(
    '/api/v1/projects/{project_id}/status',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function listProjectMembers(projectId: string): Promise<ProjectMember[]> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/projects/{project_id}/members',
    { params: { path: { project_id: projectId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function addProjectMember(
  projectId: string,
  payload: ProjectMemberAdd,
): Promise<ProjectMember> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/members',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function removeProjectMember(projectId: string, userId: string): Promise<void> {
  const { error, response } = await apiClient.DELETE(
    '/api/v1/projects/{project_id}/members/{user_id}',
    { params: { path: { project_id: projectId, user_id: userId } } },
  )
  if (!response.ok) throw createApiError(response, error)
}

export async function transferProjectOwner(
  projectId: string,
  payload: ProjectOwnerTransfer,
): Promise<ProjectMember> {
  const { data, error, response } = await apiClient.PUT(
    '/api/v1/projects/{project_id}/owner',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}
