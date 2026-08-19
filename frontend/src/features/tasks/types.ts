import type { components } from '../../api/generated/schema'

export type Task = components['schemas']['TaskResponse']
export type TaskCreate = components['schemas']['TaskCreate']
export type TaskUpdate = components['schemas']['TaskUpdate']
export type TaskStatus = components['schemas']['TaskStatus']
export type TaskStatusUpdate = components['schemas']['TaskStatusUpdate']
export type TaskPriority = components['schemas']['TaskPriority']
export type TaskMember = components['schemas']['TaskMemberResponse']
export type TaskMemberAdd = components['schemas']['TaskMemberAdd']
export type TaskOwnerTransfer = components['schemas']['TaskOwnerTransfer']
export type TaskRole = components['schemas']['TaskRole']
