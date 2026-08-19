import type { Dayjs } from 'dayjs'
import type { PersonalTaskCreate, TaskPriority } from './types'

export interface PersonalTaskFormValues {
  title: string
  description?: string
  priority: TaskPriority
  starts_at?: Dayjs
  due_at?: Dayjs
  assignee_user_ids: string[]
}

export function toPersonalTaskCreate(
  values: PersonalTaskFormValues,
): PersonalTaskCreate {
  return {
    title: values.title,
    description: values.description || null,
    priority: values.priority,
    starts_at: values.starts_at?.toISOString() || null,
    due_at: values.due_at?.toISOString() || null,
    assignee_user_ids: values.assignee_user_ids,
    attachment_mode: 'shared',
  }
}

