import type { components } from '../../api/generated/schema'

export type CollaborationFile = components['schemas']['FileListItemResponse']
export type FileRecord = components['schemas']['FileResponse']
export type FileMetadataUpdate = components['schemas']['FileMetadataUpdate']
export type FileIndexItem = components['schemas']['FileIndexItemResponse']
export type ProjectFileIndex = components['schemas']['ProjectFileIndexResponse']
export type FileScope = 'project' | 'task'
