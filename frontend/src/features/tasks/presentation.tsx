import { Tag } from 'antd'
import type { TaskPriority, TaskRole, TaskStatus } from './types'

const statusPresentation: Record<TaskStatus, { label: string; color: string }> = {
  todo: { label: '待开始', color: 'default' },
  in_progress: { label: '进行中', color: 'processing' },
  in_review: { label: '审核中', color: 'purple' },
  done: { label: '已完成', color: 'success' },
  cancelled: { label: '已取消', color: 'default' },
}

const priorityPresentation: Record<TaskPriority, { label: string; color: string }> = {
  low: { label: '低', color: 'blue' },
  medium: { label: '中', color: 'cyan' },
  high: { label: '高', color: 'orange' },
  urgent: { label: '紧急', color: 'red' },
}

const rolePresentation: Record<TaskRole, { label: string; color: string }> = {
  owner: { label: '负责人', color: 'gold' },
  collaborator: { label: '协作者', color: 'blue' },
  reviewer: { label: '审核人', color: 'purple' },
}

export function TaskStatusTag({ status }: { status: TaskStatus }) {
  const item = statusPresentation[status]
  return <Tag color={item.color}>{item.label}</Tag>
}

export function TaskPriorityTag({ priority }: { priority: TaskPriority }) {
  const item = priorityPresentation[priority]
  return <Tag color={item.color}>{item.label}</Tag>
}

export function TaskRoleTag({ role }: { role: TaskRole }) {
  const item = rolePresentation[role]
  return <Tag color={item.color}>{item.label}</Tag>
}
