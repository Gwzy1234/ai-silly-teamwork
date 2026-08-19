import { App, Button, Card, Col, Empty, Flex, Row, Select, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'
import { getApiErrorMessage } from '../../../api/errors'
import { taskBoardStatuses, taskStatusLabels, taskStatusOptions } from '../constants'
import { useBoardTaskStatus } from '../hooks'
import { TaskPriorityTag } from '../presentation'
import type { Task, TaskStatus } from '../types'

interface TaskBoardProps {
  projectId: string
  tasks: Task[]
  loading?: boolean
}

export function TaskBoard({ projectId, tasks, loading = false }: TaskBoardProps) {
  const { message } = App.useApp()
  const statusMutation = useBoardTaskStatus(projectId)

  const changeStatus = async (taskId: string, status: TaskStatus) => {
    try {
      await statusMutation.mutateAsync({ taskId, status })
      message.success('任务状态已更新')
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  return (
    <Row gutter={[12, 12]}>
      {taskBoardStatuses.map((status) => {
        const statusTasks = tasks.filter((task) => task.status === status)
        return (
          <Col xs={24} md={12} xl={6} key={status}>
            <Card
              className="task-board-column"
              loading={loading}
              title={
                <Flex justify="space-between">
                  <span>{taskStatusLabels[status]}</span>
                  <Typography.Text type="secondary">{statusTasks.length}</Typography.Text>
                </Flex>
              }
            >
              {statusTasks.length ? (
                <Flex vertical gap={10}>
                  {statusTasks.map((task) => (
                    <Card key={task.id} size="small" className="task-board-card">
                      <Flex vertical gap={10}>
                        <Link to={`/tasks/${task.id}`}>
                          <Typography.Text strong>{task.title}</Typography.Text>
                        </Link>
                        <Space wrap>
                          <TaskPriorityTag priority={task.priority} />
                          <Typography.Text type="secondary" className="task-due-text">
                            {task.due_at ? dayjs(task.due_at).format('MM-DD HH:mm') : '无截止时间'}
                          </Typography.Text>
                        </Space>
                        <Select
                          size="small"
                          value={task.status}
                          options={taskStatusOptions}
                          onChange={(nextStatus) => void changeStatus(task.id, nextStatus)}
                          loading={statusMutation.isPending && statusMutation.variables?.taskId === task.id}
                        />
                      </Flex>
                    </Card>
                  ))}
                </Flex>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" />
              )}
            </Card>
          </Col>
        )
      })}
      {tasks.some((task) => task.status === 'cancelled') && (
        <Col span={24}>
          <Card size="small" title="已取消任务">
            <Space wrap>
              {tasks.filter((task) => task.status === 'cancelled').map((task) => (
                <Button key={task.id} type="link" href={`/tasks/${task.id}`}>{task.title}</Button>
              ))}
            </Space>
          </Card>
        </Col>
      )}
    </Row>
  )
}
