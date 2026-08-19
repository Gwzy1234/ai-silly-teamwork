import {
  CalendarOutlined,
  CheckSquareOutlined,
  ClockCircleOutlined,
  PaperClipOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Empty,
  Flex,
  List,
  Segmented,
  Skeleton,
  Space,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { personalTaskFilterOptions } from '../features/personal-tasks/constants'
import { useMyPersonalTasks } from '../features/personal-tasks/hooks'
import {
  DeadlineStateTag,
  PersonalTaskPriorityTag,
  PersonalTaskStatusTag,
} from '../features/personal-tasks/presentation'
import type { TaskStatus } from '../features/personal-tasks/types'

type PersonalTaskFilter = 'all' | Exclude<TaskStatus, 'cancelled'>

export function MyTasksPage() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<PersonalTaskFilter>('all')
  const tasks = useMyPersonalTasks(
    statusFilter === 'all' ? { limit: 200 } : { status: statusFilter, limit: 200 },
  )

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <div>
          <Space>
            <CheckSquareOutlined className="page-title-icon" />
            <Typography.Title level={2} style={{ margin: 0 }}>
              我的任务
            </Typography.Title>
          </Space>
          <Typography.Paragraph type="secondary" style={{ margin: '8px 0 0' }}>
            每项任务拥有独立完成状态，不会影响其他成员的进度。
          </Typography.Paragraph>
        </div>
      </Flex>

      <Card className="content-card personal-task-filter-card">
        <Segmented
          block
          options={personalTaskFilterOptions}
          value={statusFilter}
          onChange={(value) => setStatusFilter(value as PersonalTaskFilter)}
        />
      </Card>

      {tasks.isPending ? (
        <Card className="content-card">
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      ) : tasks.isError ? (
        <Alert
          showIcon
          type="error"
          message="个人任务加载失败"
          action={<Button onClick={() => tasks.refetch()}>重试</Button>}
        />
      ) : tasks.data?.length ? (
        <List
          className="personal-task-list"
          dataSource={tasks.data}
          renderItem={({ assignment, task }) => (
            <List.Item>
              <Card
                hoverable
                className="personal-task-card"
                onClick={() => navigate(`/my-tasks/${assignment.id}`)}
              >
                <Flex vertical gap={14}>
                  <Flex justify="space-between" align="flex-start" gap={12} wrap>
                    <div className="personal-task-card-title">
                      <Typography.Title level={4} ellipsis={{ rows: 2 }} style={{ margin: 0 }}>
                        {task.title}
                      </Typography.Title>
                      <Typography.Text type="secondary">
                        {task.project.team.name} · {task.project.name}
                      </Typography.Text>
                    </div>
                    <Space wrap>
                      <PersonalTaskStatusTag status={assignment.status} />
                      <PersonalTaskPriorityTag priority={task.priority} />
                      <DeadlineStateTag task={task} status={assignment.status} />
                    </Space>
                  </Flex>

                  {task.description && (
                    <Typography.Paragraph
                      type="secondary"
                      ellipsis={{ rows: 2 }}
                      style={{ margin: 0 }}
                    >
                      {task.description}
                    </Typography.Paragraph>
                  )}

                  <Flex gap={16} wrap className="personal-task-meta">
                    <Typography.Text type="secondary">
                      <CalendarOutlined /> 开始：
                      {task.starts_at ? dayjs(task.starts_at).format('MM-DD HH:mm') : '未设置'}
                    </Typography.Text>
                    <Typography.Text type={
                      task.due_at && dayjs(task.due_at).isBefore(dayjs()) &&
                      !['done', 'cancelled'].includes(assignment.status)
                        ? 'danger'
                        : 'secondary'
                    }>
                      <ClockCircleOutlined /> 截止：
                      {task.due_at ? dayjs(task.due_at).format('MM-DD HH:mm') : '未设置'}
                    </Typography.Text>
                    <Typography.Text type="secondary">
                      <PaperClipOutlined /> {task.attachment_mode === 'shared' ? '共享附件' : '独立附件'}
                    </Typography.Text>
                  </Flex>
                </Flex>
              </Card>
            </List.Item>
          )}
        />
      ) : (
        <Card className="content-card">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={statusFilter === 'all' ? '暂时没有个人任务' : '该状态下暂无任务'}
          />
        </Card>
      )}
    </Flex>
  )
}

