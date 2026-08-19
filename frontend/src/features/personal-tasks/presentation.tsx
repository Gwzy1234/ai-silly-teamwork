import { ClockCircleOutlined } from '@ant-design/icons'
import { Tag } from 'antd'
import dayjs from 'dayjs'
import { TaskPriorityTag, TaskStatusTag } from '../tasks/presentation'
import type { PersonalTaskSummary, TaskPriority, TaskStatus } from './types'

export { TaskPriorityTag, TaskStatusTag }

export function PersonalTaskStatusTag({ status }: { status: TaskStatus }) {
  return <TaskStatusTag status={status} />
}

export function PersonalTaskPriorityTag({ priority }: { priority: TaskPriority }) {
  return <TaskPriorityTag priority={priority} />
}

export function DeadlineStateTag({ task, status }: {
  task: Pick<PersonalTaskSummary, 'due_at'>
  status: TaskStatus
}) {
  if (status === 'done') return <Tag color="success">已完成</Tag>
  if (status === 'cancelled') return <Tag>已取消</Tag>
  if (!task.due_at) return <Tag>无截止时间</Tag>

  const dueAt = dayjs(task.due_at)
  const hours = dueAt.diff(dayjs(), 'hour', true)
  if (hours < 0) {
    return <Tag color="error" icon={<ClockCircleOutlined />}>已逾期</Tag>
  }
  if (hours <= 72) {
    return <Tag color="warning" icon={<ClockCircleOutlined />}>即将截止</Tag>
  }
  return <Tag color="blue">进行中</Tag>
}

