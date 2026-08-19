import dayjs, { type Dayjs } from 'dayjs'
import type { ProjectCreate, ProjectUpdate } from './types'

export interface ProjectFormValues {
  name: string
  description?: string
  starts_at?: Dayjs
  due_at?: Dayjs
  owner_user_id?: string
}

export function toProjectCreate(values: ProjectFormValues): ProjectCreate {
  return {
    name: values.name,
    description: values.description || null,
    starts_at: values.starts_at?.toISOString() || null,
    due_at: values.due_at?.toISOString() || null,
    owner_user_id: values.owner_user_id || null,
  }
}

export function toProjectUpdate(values: ProjectFormValues): ProjectUpdate {
  return {
    name: values.name,
    description: values.description || null,
    starts_at: values.starts_at?.toISOString() || null,
    due_at: values.due_at?.toISOString() || null,
  }
}

export function projectFormInitialValues(project: {
  name: string
  description: string | null
  starts_at: string | null
  due_at: string | null
}): ProjectFormValues {
  return {
    name: project.name,
    description: project.description || undefined,
    starts_at: project.starts_at ? dayjs(project.starts_at) : undefined,
    due_at: project.due_at ? dayjs(project.due_at) : undefined,
  }
}
