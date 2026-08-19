import type { TaskStatus } from './types'

export const personalTaskStatusOptions: { value: TaskStatus; label: string }[] = [
  { value: 'todo', label: '待处理' },
  { value: 'in_progress', label: '进行中' },
  { value: 'in_review', label: '审核中' },
  { value: 'done', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

export const personalTaskFilterOptions: {
  value: 'all' | Exclude<TaskStatus, 'cancelled'>
  label: string
}[] = [
  { value: 'all', label: '全部' },
  { value: 'todo', label: '待处理' },
  { value: 'in_progress', label: '进行中' },
  { value: 'in_review', label: '审核中' },
  { value: 'done', label: '已完成' },
]

