import { apiClient } from '../../api/client'
import { createApiError } from '../../api/errors'
import type {
  CollaborationFile,
  FileIndexItem,
  FileMetadataUpdate,
  FileRecord,
  ProjectFileIndex,
} from './types'

const multipartSerializer = (body: { file: File }) => {
  const formData = new FormData()
  formData.append('file', body.file)
  return formData
}

export async function listProjectFiles(projectId: string): Promise<FileRecord[]> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/projects/{project_id}/files',
    { params: { path: { project_id: projectId } } },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function uploadProjectFile(projectId: string, file: File): Promise<FileRecord> {
  const { data, error, response } = await apiClient.POST(
    '/api/v1/projects/{project_id}/files',
    {
      params: { path: { project_id: projectId } },
      body: { file: file as unknown as string },
      bodySerializer: multipartSerializer as never,
    },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function listTaskFiles(taskId: string): Promise<CollaborationFile[]> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks/{task_id}/files', {
    params: { path: { task_id: taskId } },
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function listFileIndex(query?: string): Promise<FileIndexItem[]> {
  const { data, error, response } = await apiClient.GET('/api/v1/files/index', {
    params: { query: query ? { q: query } : {} },
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function getProjectFileIndex(
  projectId: string,
  query?: string,
): Promise<ProjectFileIndex> {
  const { data, error, response } = await apiClient.GET(
    '/api/v1/projects/{project_id}/file-index',
    {
      params: {
        path: { project_id: projectId },
        query: query ? { q: query } : {},
      },
    },
  )
  if (!data) throw createApiError(response, error)
  return data
}

export async function uploadTaskFile(taskId: string, file: File): Promise<FileRecord> {
  const { data, error, response } = await apiClient.POST('/api/v1/tasks/{task_id}/files', {
    params: { path: { task_id: taskId } },
    body: { file: file as unknown as string },
    bodySerializer: multipartSerializer as never,
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function updateFileMetadata(
  fileId: string,
  payload: FileMetadataUpdate,
): Promise<FileRecord> {
  const { data, error, response } = await apiClient.PATCH('/api/v1/files/{file_id}', {
    params: { path: { file_id: fileId } },
    body: payload,
  })
  if (!data) throw createApiError(response, error)
  return data
}

export async function deleteFile(fileId: string): Promise<void> {
  const { error, response } = await apiClient.DELETE('/api/v1/files/{file_id}', {
    params: { path: { file_id: fileId } },
  })
  if (!response.ok) throw createApiError(response, error)
}

export async function downloadFile(fileId: string): Promise<Blob> {
  const { data, error, response } = await apiClient.GET('/api/v1/files/{file_id}/download', {
    params: { path: { file_id: fileId } },
    parseAs: 'blob',
  })
  if (!response.ok || !data) throw createApiError(response, error)
  return data
}
