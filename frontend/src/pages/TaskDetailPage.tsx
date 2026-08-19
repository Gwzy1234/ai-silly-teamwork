import {
  ArrowLeftOutlined,
  CalendarOutlined,
  CrownOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  SwapOutlined,
  UserOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App,
  Avatar,
  Button,
  Card,
  Descriptions,
  Empty,
  Flex,
  Form,
  List,
  Modal,
  Popconfirm,
  Result,
  Select,
  Skeleton,
  Space,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, getApiErrorMessage } from '../api/errors'
import { FilePanel } from '../features/files/components/FilePanel'
import { useProject, useProjectMembers } from '../features/projects/hooks'
import { useTeamMembers } from '../features/teams/hooks'
import { taskMemberRoleOptions, taskStatusOptions } from '../features/tasks/constants'
import { TaskForm } from '../features/tasks/components/TaskForm'
import {
  taskFormInitialValues,
  toTaskUpdate,
  type TaskFormValues,
} from '../features/tasks/forms'
import {
  useAddTaskMember,
  useDeleteTask,
  useRemoveTaskMember,
  useTask,
  useTaskMembers,
  useTransferTaskOwner,
  useUpdateTask,
  useUpdateTaskStatus,
} from '../features/tasks/hooks'
import { TaskPriorityTag, TaskRoleTag, TaskStatusTag } from '../features/tasks/presentation'
import type { TaskRole, TaskStatus } from '../features/tasks/types'

export function TaskDetailPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const task = useTask(taskId)
  const projectId = task.data?.project_id || ''
  const project = useProject(projectId)
  const members = useTaskMembers(taskId)
  const projectMembers = useProjectMembers(projectId)
  const teamMembers = useTeamMembers(project.data?.team_id || '')
  const updateMutation = useUpdateTask(taskId, projectId)
  const statusMutation = useUpdateTaskStatus(taskId, projectId)
  const addMutation = useAddTaskMember(taskId, projectId)
  const deleteMutation = useDeleteTask(taskId, projectId)
  const removeMutation = useRemoveTaskMember(taskId, projectId)
  const transferMutation = useTransferTaskOwner(taskId, projectId)
  const [editOpen, setEditOpen] = useState(false)
  const [statusOpen, setStatusOpen] = useState(false)
  const [memberOpen, setMemberOpen] = useState(false)
  const [ownerOpen, setOwnerOpen] = useState(false)
  const [editForm] = Form.useForm<TaskFormValues>()
  const [statusForm] = Form.useForm<{ status: TaskStatus }>()
  const [memberForm] = Form.useForm<{ user_id: string; role: TaskRole }>()
  const [ownerForm] = Form.useForm<{ user_id: string }>()

  const userNames = useMemo(
    () => new Map((teamMembers.data ?? []).map((member) => [member.user_id, member])),
    [teamMembers.data],
  )
  const existingMemberIds = new Set((members.data ?? []).map((member) => member.user_id))
  const projectMemberOptions = (projectMembers.data ?? []).map((membership) => {
    const user = userNames.get(membership.user_id)
    return {
      value: membership.user_id,
      label: user ? `${user.nickname || user.username} (@${user.username})` : membership.user_id,
    }
  })
  const availableMemberOptions = projectMemberOptions.filter(
    (option) => !existingMemberIds.has(option.value),
  )

  const runAction = async (action: () => Promise<unknown>, success: string, close?: () => void) => {
    try {
      await action()
      message.success(success)
      close?.()
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  if (task.isPending) return <Card><Skeleton active paragraph={{ rows: 9 }} /></Card>
  if (task.isError || !task.data) {
    return <Result status="404" title="任务不存在或你无权访问" extra={<Button onClick={() => navigate('/teams')}>返回团队</Button>} />
  }

  const detail = task.data
  const openEdit = () => {
    editForm.setFieldsValue(taskFormInitialValues(detail))
    setEditOpen(true)
  }

  const deleteCurrentTask = async () => {
    try {
      await deleteMutation.mutateAsync()
      message.success('任务已删除')
      navigate(`/projects/${detail.project_id}/tasks`, { replace: true })
    } catch (error) {
      message.error(
        error instanceof ApiError && error.status === 403
          ? '无权限删除该任务'
          : getApiErrorMessage(error),
      )
    }
  }

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <Space align="start">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(`/projects/${detail.project_id}/tasks`)} />
          <div>
            <Space wrap>
              <Typography.Title level={2} style={{ margin: 0 }}>{detail.title}</Typography.Title>
              <TaskStatusTag status={detail.status} />
              <TaskPriorityTag priority={detail.priority} />
            </Space>
            <Typography.Text type="secondary">任务 ID：{detail.id}</Typography.Text>
          </div>
        </Space>
        <Space wrap>
          <Button icon={<EditOutlined />} onClick={openEdit}>修改任务</Button>
          <Button type="primary" icon={<SwapOutlined />} onClick={() => { statusForm.setFieldValue('status', detail.status); setStatusOpen(true) }}>
            修改状态
          </Button>
        </Space>
      </Flex>

      <Card className="content-card">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="状态"><TaskStatusTag status={detail.status} /></Descriptions.Item>
          <Descriptions.Item label="优先级"><TaskPriorityTag priority={detail.priority} /></Descriptions.Item>
          <Descriptions.Item label="开始时间"><CalendarOutlined /> {detail.starts_at ? dayjs(detail.starts_at).format('YYYY-MM-DD HH:mm') : '未设置'}</Descriptions.Item>
          <Descriptions.Item label="截止时间"><CalendarOutlined /> {detail.due_at ? dayjs(detail.due_at).format('YYYY-MM-DD HH:mm') : '未设置'}</Descriptions.Item>
          {detail.completed_at && <Descriptions.Item label="完成时间">{dayjs(detail.completed_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>}
          <Descriptions.Item label="创建时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
          <Descriptions.Item label="任务描述" span={2}>{detail.description || '暂未填写任务描述'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card className="content-card" title="任务附件">
        <FilePanel scope="task" ownerId={taskId} title="附件列表" />
      </Card>

      <Card
        className="content-card"
        title="任务成员"
        extra={
          <Space wrap>
            <Button icon={<CrownOutlined />} onClick={() => setOwnerOpen(true)}>转移负责人</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setMemberOpen(true)}>分配成员</Button>
          </Space>
        }
        loading={members.isPending}
      >
        {members.isError ? (
          <Alert showIcon type="error" message="任务成员加载失败" action={<Button onClick={() => members.refetch()}>重试</Button>} />
        ) : members.data?.length ? (
          <List
            dataSource={members.data}
            renderItem={(membership) => {
              const user = userNames.get(membership.user_id)
              return (
                <List.Item
                  extra={
                    <Space>
                      <TaskRoleTag role={membership.role} />
                      {membership.role !== 'owner' && (
                        <Popconfirm
                          title="移除任务成员"
                          okText="移除"
                          cancelText="取消"
                          onConfirm={() => runAction(() => removeMutation.mutateAsync(membership.user_id), '任务成员已移除')}
                        >
                          <Button danger type="text" icon={<DeleteOutlined />} loading={removeMutation.isPending}>移除</Button>
                        </Popconfirm>
                      )}
                    </Space>
                  }
                >
                  <List.Item.Meta
                    avatar={<Avatar icon={<UserOutlined />} />}
                    title={user?.nickname || user?.username || membership.user_id}
                    description={user ? `@${user.username}` : `用户 ID：${membership.user_id}`}
                  />
                </List.Item>
              )
            }}
          />
        ) : (
          <Empty description="暂无任务成员" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      <Card className="content-card danger-zone-card" title="危险操作">
        <Flex justify="space-between" align="center" gap={16} wrap>
          <div>
            <Typography.Text strong>删除任务</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
              删除后，任务成员和任务附件也会被永久清理，且无法恢复。
            </Typography.Paragraph>
          </div>
          <Popconfirm
            title="确认删除此任务？"
            description="删除后无法恢复。"
            okText="确认删除"
            cancelText="取消"
            okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
            onConfirm={deleteCurrentTask}
          >
            <Button danger icon={<DeleteOutlined />} loading={deleteMutation.isPending}>
              删除任务
            </Button>
          </Popconfirm>
        </Flex>
      </Card>

      <Modal
        title="修改任务"
        open={editOpen}
        width={620}
        onCancel={() => setEditOpen(false)}
        onOk={() => runAction(async () => updateMutation.mutateAsync(toTaskUpdate(await editForm.validateFields())), '任务已更新', () => setEditOpen(false))}
        confirmLoading={updateMutation.isPending}
        okText="保存"
      >
        <TaskForm form={editForm} />
      </Modal>

      <Modal
        title="修改任务状态"
        open={statusOpen}
        onCancel={() => setStatusOpen(false)}
        onOk={() => runAction(async () => statusMutation.mutateAsync(await statusForm.validateFields()), '任务状态已更新', () => setStatusOpen(false))}
        confirmLoading={statusMutation.isPending}
        okText="更新"
      >
        <Form form={statusForm} layout="vertical">
          <Form.Item name="status" label="目标状态" rules={[{ required: true }]}>
            <Select options={taskStatusOptions} />
          </Form.Item>
          <Alert showIcon type="info" message="允许的状态流转和操作权限由后端校验。" />
        </Form>
      </Modal>

      <Modal
        title="分配任务成员"
        open={memberOpen}
        onCancel={() => setMemberOpen(false)}
        onOk={() => runAction(async () => addMutation.mutateAsync(await memberForm.validateFields()), '任务成员已添加', () => { setMemberOpen(false); memberForm.resetFields() })}
        confirmLoading={addMutation.isPending}
        okText="添加"
      >
        <Form form={memberForm} layout="vertical" initialValues={{ role: 'collaborator' }}>
          <Form.Item name="user_id" label="科目成员" rules={[{ required: true, message: '请选择成员' }]}>
            <Select showSearch optionFilterProp="label" options={availableMemberOptions} placeholder="选择尚未参与任务的科目成员" />
          </Form.Item>
          <Form.Item name="role" label="任务角色" rules={[{ required: true }]}>
            <Select options={taskMemberRoleOptions} />
          </Form.Item>
          {!availableMemberOptions.length && <Alert showIcon type="info" message="所有科目成员都已参与该任务" />}
        </Form>
      </Modal>

      <Modal
        title="转移任务负责人"
        open={ownerOpen}
        onCancel={() => setOwnerOpen(false)}
        onOk={() => runAction(async () => transferMutation.mutateAsync(await ownerForm.validateFields()), '任务负责人已转移', () => { setOwnerOpen(false); ownerForm.resetFields() })}
        confirmLoading={transferMutation.isPending}
        okText="确认转移"
      >
        <Form form={ownerForm} layout="vertical">
          <Form.Item name="user_id" label="新负责人" rules={[{ required: true, message: '请选择新负责人' }]}>
            <Select showSearch optionFilterProp="label" options={projectMemberOptions} placeholder="选择科目成员" />
          </Form.Item>
          <Alert showIcon type="warning" message="原负责人将自动变为协作者。" />
        </Form>
      </Modal>
    </Flex>
  )
}
