import type { components, paths } from '../../api/generated/schema'

export type PersonalTaskCreate = components['schemas']['PersonalTaskCreate']
export type PersonalTaskCreateResponse = components['schemas']['PersonalTaskCreateResponse']
export type PersonalTaskDetail = components['schemas']['PersonalTaskDetailResponse']
export type PersonalTaskSummary = components['schemas']['PersonalTaskSummaryResponse']
export type MyPersonalTask = components['schemas']['MyPersonalTaskResponse']
export type MyPersonalTaskCount = components['schemas']['MyPersonalTaskCountResponse']
export type ProjectPersonalTaskListItem =
  components['schemas']['ProjectPersonalTaskListItemResponse']
export type ProjectPersonalTaskPage =
  components['schemas']['ProjectPersonalTaskPageResponse']
export type TaskAssignment = components['schemas']['TaskAssignmentResponse']
export type TaskStatus = components['schemas']['TaskStatus']
export type TaskPriority = components['schemas']['TaskPriority']
export type TaskStatusUpdate = components['schemas']['TaskStatusUpdate']
export type MyPersonalTaskFilters = NonNullable<
  paths['/api/v1/tasks/my']['get']['parameters']['query']
>
export type ProjectPersonalTaskFilters = NonNullable<
  paths['/api/v1/projects/{project_id}/personal-tasks']['get']['parameters']['query']
>
