import { ArrowLeftOutlined, PlusOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Empty, Flex, Result, Skeleton, Space, Table, Typography } from 'antd'
import type { TableProps } from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useProject } from '../features/projects/hooks'
import { PersonalTaskCreateModal } from '../features/personal-tasks/components/PersonalTaskCreateModal'
import { useCanPublishPersonalTask } from '../features/personal-tasks/hooks'
import { useTeamMembers } from '../features/teams/hooks'
import { CreateTaskModal } from '../features/tasks/components/CreateTaskModal'
import { useTaskMemberQueries, useTasks } from '../features/tasks/hooks'
import { TaskPriorityTag, TaskRoleTag, TaskStatusTag } from '../features/tasks/presentation'
import type { Task } from '../features/tasks/types'

export function ProjectTasksPage() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [createPersonalOpen, setCreatePersonalOpen] = useState(false)
  const project = useProject(projectId)
  const tasks = useTasks(projectId)
  const teamMembers = useTeamMembers(project.data?.team_id || '')
  const personalTaskPermission = useCanPublishPersonalTask(project.data?.team_id || '')
  const taskIds = (tasks.data ?? []).map((task) => task.id)
  const taskMemberQueries = useTaskMemberQueries(taskIds)

  const userNames = useMemo(
    () => new Map((teamMembers.data ?? []).map((member) => [member.user_id, member])),
    [teamMembers.data],
  )
  const owners = useMemo(() => {
    const result = new Map<string, string>()
    taskIds.forEach((taskId, index) => {
      const owner = taskMemberQueries[index]?.data?.find((member) => member.role === 'owner')
      if (!owner) return
      const user = userNames.get(owner.user_id)
      result.set(taskId, user?.nickname || user?.username || owner.user_id)
    })
    return result
  }, [taskIds, taskMemberQueries, userNames])

  const columns: TableProps<Task>['columns'] = [
    {
      title: '任务',
      dataIndex: 'title',
      render: (title: string, task) => <Link to={`/tasks/${task.id}`}>{title}</Link>,
    },
    { title: '状态', dataIndex: 'status', render: (status) => <TaskStatusTag status={status} /> },
    { title: '优先级', dataIndex: 'priority', render: (priority) => <TaskPriorityTag priority={priority} /> },
    {
      title: '截止时间',
      dataIndex: 'due_at',
      render: (dueAt: string | null) => dueAt ? dayjs(dueAt).format('YYYY-MM-DD HH:mm') : '未设置',
    },
    {
      title: '负责人',
      key: 'owner',
      render: (_, task) => owners.has(task.id)
        ? <Space><TaskRoleTag role="owner" />{owners.get(task.id)}</Space>
        : '加载中',
    },
  ]

  if (project.isPending) return <Card><Skeleton active paragraph={{ rows: 8 }} /></Card>
  if (project.isError || !project.data) {
    return <Result status="404" title="科目不存在或你无权访问" extra={<Button onClick={() => navigate('/teams')}>返回团队</Button>} />
  }

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="center" wrap gap={16}>
        <Space align="start">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(`/projects/${projectId}`)} />
          <div>
            <Typography.Title level={2} style={{ margin: 0 }}>{project.data.name} · 任务</Typography.Title>
            <Typography.Text type="secondary">集中查看该科目的任务状态、优先级、截止时间和负责人</Typography.Text>
          </div>
        </Space>
        <Space wrap>
          {personalTaskPermission.canPublish && (
            <Button icon={<UserOutlined />} onClick={() => setCreatePersonalOpen(true)}>
              发布个人任务
            </Button>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>创建任务</Button>
        </Space>
      </Flex>

      <Card className="content-card">
        {tasks.isError ? (
          <Alert showIcon type="error" message="任务列表加载失败" action={<Button onClick={() => tasks.refetch()}>重试</Button>} />
        ) : (
          <Table
            rowKey="id"
            loading={tasks.isPending}
            columns={columns}
            dataSource={tasks.data ?? []}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            locale={{ emptyText: <Empty description="该科目中还没有任务" /> }}
            scroll={{ x: 760 }}
          />
        )}
      </Card>

      <CreateTaskModal
        projectId={projectId}
        teamMembers={teamMembers.data ?? []}
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
      <PersonalTaskCreateModal
        projectId={projectId}
        teamMembers={teamMembers.data ?? []}
        open={createPersonalOpen}
        onClose={() => setCreatePersonalOpen(false)}
        onCreated={(taskId) => navigate(`/personal-tasks/${taskId}`)}
      />
    </Flex>
  )
}
