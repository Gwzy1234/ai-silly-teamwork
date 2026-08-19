import dayjs, { type Dayjs } from 'dayjs'
import type { TaskCreate, TaskPriority, TaskUpdate } from './types'

export interface TaskFormValues {
  title: string
  description?: string
  priority: TaskPriority
  starts_at?: Dayjs
  due_at?: Dayjs
  owner_user_id?: string
}

export function toTaskCreate(values: TaskFormValues): TaskCreate {
  return {
    title: values.title,
    description: values.description || null,
    priority: values.priority,
    starts_at: values.starts_at?.toISOString() || null,
    due_at: values.due_at?.toISOString() || null,
    owner_user_id: values.owner_user_id || null,
  }
}

export function toTaskUpdate(values: TaskFormValues): TaskUpdate {
  return {
    title: values.title,
    description: values.description || null,
    priority: values.priority,
    starts_at: values.starts_at?.toISOString() || null,
    due_at: values.due_at?.toISOString() || null,
  }
}

export function taskFormInitialValues(task: {
  title: string
  description: string | null
  priority: TaskPriority
  starts_at: string | null
  due_at: string | null
}): TaskFormValues {
  return {
    title: task.title,
    description: task.description || undefined,
    priority: task.priority,
    starts_at: task.starts_at ? dayjs(task.starts_at) : undefined,
    due_at: task.due_at ? dayjs(task.due_at) : undefined,
  }
}
