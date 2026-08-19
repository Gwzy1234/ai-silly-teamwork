import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type {
  MyPersonalTask,
  MyPersonalTaskCount,
  MyPersonalTaskFilters,
  PersonalTaskCreate,
  PersonalTaskCreateResponse,
  PersonalTaskDetail,
  ProjectPersonalTaskFilters,
  ProjectPersonalTaskPage,
  TaskAssignment,
  TaskStatusUpdate,
} from './types'

export async function createPersonalTask(
  projectId: string,
  payload: PersonalTaskCreate,
): Promise<PersonalTaskCreateResponse> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/personal-tasks',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function listMyPersonalTasks(
  filters: MyPersonalTaskFilters = {},
): Promise<MyPersonalTask[]> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks/my', {
    params: { query: filters },
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function countMyPersonalTasks(): Promise<MyPersonalTaskCount> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks/my/count')
  if (!data) throw createApiError(response, error)
  return data
}

export async function listProjectPersonalTasks(
  projectId: string,
  filters: ProjectPersonalTaskFilters = {},
): Promise<ProjectPersonalTaskPage> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/projects/{project_id}/personal-tasks',
    {
      params: {
        path: { project_id: projectId },
        query: filters,
      },
    },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function getPersonalTask(taskId: string): Promise<PersonalTaskDetail> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/personal-tasks/{task_id}',
    { params: { path: { task_id: taskId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function listPersonalTaskAssignments(
  taskId: string,
): Promise<TaskAssignment[]> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/personal-tasks/{task_id}/assignments',
    { params: { path: { task_id: taskId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function getTaskAssignment(
  assignmentId: string,
): Promise<TaskAssignment> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/task-assignments/{assignment_id}',
    { params: { path: { assignment_id: assignmentId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function updateTaskAssignmentStatus(
  assignmentId: string,
  payload: TaskStatusUpdate,
): Promise<TaskAssignment> {
  const { data, error, response } = await apiClient.PATCH(
    '/api/v1/task-assignments/{assignment_id}/status',
    { params: { path: { assignment_id: assignmentId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function deletePersonalTask(taskId: string): Promise<void> {
  const { error, response } = await apiClient.DELETE(
    '/api/v1/personal-tasks/{task_id}',
    { params: { path: { task_id: taskId } } },
  )
  if (!response.ok) throw createApiError(response, error)
}

export async function checkSystemAdminAccess(): Promise<boolean> {
  const { error, response } = await apiClient.GET('/api/v1/admin/teams')
  if (response.status === 403) return false
  if (!response.ok) throw createApiError(response, error)
  return true
}
