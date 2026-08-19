import type { ProjectStatus } from './types'

export const projectStatusOptions = [
  { value: 'planning', label: '规划中' },
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
] satisfies Array<{ value: ProjectStatus; label: string }>
