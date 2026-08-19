import type { TaskPriority, TaskRole, TaskStatus } from './types'

export const taskStatusOptions: { value: TaskStatus; label: string }[] = [
  { value: 'todo', label: '待开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'in_review', label: '审核中' },
  { value: 'done', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

export const taskStatusLabels: Record<TaskStatus, string> = {
  todo: '待开始',
  in_progress: '进行中',
  in_review: '审核中',
  done: '已完成',
  cancelled: '已取消',
}

export const taskBoardStatuses: TaskStatus[] = ['todo', 'in_progress', 'in_review', 'done']

export const taskPriorityOptions: { value: TaskPriority; label: string }[] = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'urgent', label: '紧急' },
]

export const taskMemberRoleOptions: { value: TaskRole; label: string }[] = [
  { value: 'collaborator', label: '协作者' },
  { value: 'reviewer', label: '审核人' },
]
