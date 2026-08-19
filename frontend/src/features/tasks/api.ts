import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type {
  Task,
  TaskCreate,
  TaskMember,
  TaskMemberAdd,
  TaskOwnerTransfer,
  TaskStatusUpdate,
  TaskUpdate,
} from './types'

export async function listTasks(projectId: string): Promise<Task[]> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/projects/{project_id}/tasks',
    { params: { path: { project_id: projectId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function createTask(projectId: string, payload: TaskCreate): Promise<Task> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/tasks',
    { params: { path: { project_id: projectId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function getTask(taskId: string): Promise<Task> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks/{task_id}', {
    params: { path: { task_id: taskId } },
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function deleteTask(taskId: string): Promise<void> {
  const { error, response } = await apiClient.DELETE('/api/v1/tasks/{task_id}', {
    params: { path: { task_id: taskId } },
  })
  if (!response.ok) throw createApiError(response, error)
}

export async function updateTask(taskId: string, payload: TaskUpdate): Promise<Task> {
  const { data, error, response } = await apiClient.PATCH('/api/v1/tasks/{task_id}', {
    params: { path: { task_id: taskId } },
    body: payload,
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function updateTaskStatus(
  taskId: string,
  payload: TaskStatusUpdate,
): Promise<Task> {
  const { data, error, response } = await apiClient.PATCH(
    '/api/v1/tasks/{task_id}/status',
    { params: { path: { task_id: taskId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function listTaskMembers(taskId: string): Promise<TaskMember[]> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/tasks/{task_id}/members',
    { params: { path: { task_id: taskId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function addTaskMember(
  taskId: string,
  payload: TaskMemberAdd,
): Promise<TaskMember> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/tasks/{task_id}/members',
    { params: { path: { task_id: taskId } }, body: payload },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function removeTaskMember(taskId: string, userId: string): Promise<void> {
  const { error, response } = await apiClient.DELETE(
    '/api/v1/tasks/{task_id}/members/{user_id}',
    { params: { path: { task_id: taskId, user_id: userId } } },
  )
  if (!response.ok) throw createApiError(response, error)
}

export async function transferTaskOwner(
  taskId: string,
  payload: TaskOwnerTransfer,
): Promise<TaskMember> {
  const { data, error, response } = await apiClient.PUT('/api/v1/tasks/{task_id}/owner', {
    params: { path: { task_id: taskId } },
    body: payload,
  })
  if (!data) throw createApiError(response, error)
  return data
}
