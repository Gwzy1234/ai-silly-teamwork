import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query'
import {
  deleteFile,
  downloadFile,
  getProjectFileIndex,
  listFileIndex,
  listProjectFiles,
  listTaskFiles,
  updateFileMetadata,
  uploadProjectFile,
  uploadTaskFile,
} from './api'
import type { CollaborationFile, FileRecord, FileScope } from './types'

export const fileQueryKeys = {
  index: (query: string) => ['files', 'index', { query }] as const,
  projectIndex: (projectId: string, query: string) =>
    ['projects', projectId, 'file-index', { query }] as const,
  project: (projectId: string) => ['projects', projectId, 'files'] as const,
  task: (taskId: string) => ['tasks', taskId, 'files'] as const,
}

export function useFileIndex(query: string) {
  return useQuery({
    queryKey: fileQueryKeys.index(query),
    queryFn: () => listFileIndex(query || undefined),
  })
}

export function useProjectFileIndex(projectId: string, query: string) {
  return useQuery({
    queryKey: fileQueryKeys.projectIndex(projectId, query),
    queryFn: () => getProjectFileIndex(projectId, query || undefined),
    enabled: Boolean(projectId),
  })
}

function scopeQueryKey(scope: FileScope, ownerId: string) {
  return scope === 'project' ? fileQueryKeys.project(ownerId) : fileQueryKeys.task(ownerId)
}

export function useCollaborationFiles(
  scope: 'task',
  ownerId: string,
): UseQueryResult<CollaborationFile[]>
export function useCollaborationFiles(
  scope: 'project',
  ownerId: string,
): UseQueryResult<FileRecord[]>
export function useCollaborationFiles(scope: FileScope, ownerId: string) {
  return useQuery({
    queryKey: scopeQueryKey(scope, ownerId),
    queryFn: () => scope === 'project' ? listProjectFiles(ownerId) : listTaskFiles(ownerId),
    enabled: Boolean(ownerId),
  })
}

export function useUploadFile(scope: FileScope, ownerId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => scope === 'project'
      ? uploadProjectFile(ownerId, file)
      : uploadTaskFile(ownerId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: scopeQueryKey(scope, ownerId) }),
  })
}

export function useUpdateFileMetadata(scope: FileScope, ownerId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ fileId, originalName }: { fileId: string; originalName: string }) =>
      updateFileMetadata(fileId, { original_name: originalName }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: scopeQueryKey(scope, ownerId) }),
  })
}

export function useDeleteFile(scope: FileScope, ownerId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteFile,
    async onSuccess() {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['files', 'index'] }),
        queryClient.invalidateQueries({
          predicate: (query) => query.queryKey[0] === 'projects'
            && query.queryKey[2] === 'file-index',
        }),
        queryClient.invalidateQueries({ queryKey: scopeQueryKey(scope, ownerId) }),
      ])
    },
  })
}

export function useDeleteIndexedFile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteFile,
    async onSuccess() {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['files', 'index'] }),
        queryClient.invalidateQueries({
          predicate: (query) => query.queryKey[0] === 'projects'
            && query.queryKey[2] === 'file-index',
        }),
        queryClient.invalidateQueries({
          predicate: (query) => query.queryKey[0] === 'tasks'
            && query.queryKey[2] === 'files',
        }),
      ])
    },
  })
}

export function useDownloadFile() {
  return useMutation({
    mutationFn: async ({ fileId, originalName }: { fileId: string; originalName: string }) => {
      const blob = await downloadFile(fileId)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = originalName
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    },
  })
}
