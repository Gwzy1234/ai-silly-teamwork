import {
  ArrowLeftOutlined,
  CalendarOutlined,
  CrownOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  SwapOutlined,
  UnorderedListOutlined,
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
  Input,
  List,
  Modal,
  Popconfirm,
  Result,
  Select,
  Skeleton,
  Space,
  Tabs,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, getApiErrorMessage } from '../api/errors'
import { AIProjectDiagnosisCard } from '../features/ai/components/AIProjectDiagnosisCard'
import { ProjectFileIndexPanel } from '../features/files/components/ProjectFileIndexPanel'
import { PersonalTaskCreateModal } from '../features/personal-tasks/components/PersonalTaskCreateModal'
import { ProjectPersonalTaskPanel } from '../features/personal-tasks/components/ProjectPersonalTaskPanel'
import { useCanPublishPersonalTask } from '../features/personal-tasks/hooks'
import { ProjectForm } from '../features/projects/components/ProjectForm'
import { projectStatusOptions } from '../features/projects/constants'
import {
  projectFormInitialValues,
  toProjectUpdate,
  type ProjectFormValues,
} from '../features/projects/forms'
import {
  useAddProjectMember,
  useDeleteProject,
  useProject,
  useProjectMembers,
  useRemoveProjectMember,
  useTransferProjectOwner,
  useUpdateProject,
  useUpdateProjectStatus,
} from '../features/projects/hooks'
import {
  ProjectRoleTag,
  ProjectStatusTag,
} from '../features/projects/presentation'
import type { ProjectStatus } from '../features/projects/types'
import { useTeamMembers } from '../features/teams/hooks'
import { CreateTaskModal } from '../features/tasks/components/CreateTaskModal'
import { TaskBoard } from '../features/tasks/components/TaskBoard'
import { useTasks } from '../features/tasks/hooks'

export function ProjectDetailPage() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const project = useProject(projectId)
  const projectMembers = useProjectMembers(projectId)
  const teamMembers = useTeamMembers(project.data?.team_id || '')
  const tasks = useTasks(projectId)
  const personalTaskPermission = useCanPublishPersonalTask(project.data?.team_id || '')
  const updateMutation = useUpdateProject(projectId)
  const statusMutation = useUpdateProjectStatus(projectId)
  const addMutation = useAddProjectMember(projectId)
  const deleteMutation = useDeleteProject(projectId, project.data?.team_id || '')
  const removeMutation = useRemoveProjectMember(projectId)
  const transferMutation = useTransferProjectOwner(projectId)
  const [editOpen, setEditOpen] = useState(false)
  const [memberOpen, setMemberOpen] = useState(false)
  const [ownerOpen, setOwnerOpen] = useState(false)
  const [statusOpen, setStatusOpen] = useState(false)
  const [createTaskOpen, setCreateTaskOpen] = useState(false)
  const [createPersonalTaskOpen, setCreatePersonalTaskOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteName, setDeleteName] = useState('')
  const [editForm] = Form.useForm<ProjectFormValues>()
  const [addForm] = Form.useForm<{ user_id: string }>()
  const [ownerForm] = Form.useForm<{ user_id: string }>()
  const [statusForm] = Form.useForm<{ status: ProjectStatus }>()

  const memberNames = useMemo(
    () => new Map((teamMembers.data ?? []).map((member) => [member.user_id, member])),
    [teamMembers.data],
  )
  const existingMemberIds = new Set((projectMembers.data ?? []).map((item) => item.user_id))
  const availableTeamMembers = (teamMembers.data ?? []).filter(
    (member) => !existingMemberIds.has(member.user_id),
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

  if (project.isPending) return <Card><Skeleton active paragraph={{ rows: 8 }} /></Card>
  if (project.isError || !project.data) {
    return <Result status="404" title="科目不存在或你无权访问" extra={<Button onClick={() => navigate('/teams')}>返回团队</Button>} />
  }

  const detail = project.data
  const openEdit = () => {
    editForm.setFieldsValue(projectFormInitialValues(detail))
    setEditOpen(true)
  }

  const deleteCurrentProject = async () => {
    if (deleteName !== detail.name) return
    try {
      await deleteMutation.mutateAsync()
      message.success('科目已永久删除')
      navigate(`/teams/${detail.team_id}`, { replace: true })
    } catch (error) {
      message.error(
        error instanceof ApiError && error.status === 403
          ? '无权限删除该科目'
          : getApiErrorMessage(error),
      )
    }
  }

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <Space align="start">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(`/teams/${detail.team_id}`)} />
          <div>
            <Space wrap>
              <Typography.Title level={2} style={{ margin: 0 }}>{detail.name}</Typography.Title>
              <ProjectStatusTag status={detail.status} />
            </Space>
            <Typography.Text type="secondary">科目 ID：{detail.id}</Typography.Text>
          </div>
        </Space>
        <Space wrap>
          <Button icon={<EditOutlined />} onClick={openEdit}>修改科目</Button>
          <Button type="primary" icon={<SwapOutlined />} onClick={() => { statusForm.setFieldValue('status', detail.status); setStatusOpen(true) }}>
            修改状态
          </Button>
        </Space>
      </Flex>

      <Card className="content-card">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="状态"><ProjectStatusTag status={detail.status} /></Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
          <Descriptions.Item label="课程开始时间"><CalendarOutlined /> {detail.starts_at ? dayjs(detail.starts_at).format('YYYY-MM-DD HH:mm') : '未设置'}</Descriptions.Item>
          <Descriptions.Item label="课程结束时间"><CalendarOutlined /> {detail.due_at ? dayjs(detail.due_at).format('YYYY-MM-DD HH:mm') : '未设置'}</Descriptions.Item>
          {detail.completed_at && <Descriptions.Item label="完成时间">{dayjs(detail.completed_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>}
          <Descriptions.Item label="科目描述" span={2}>{detail.description || '暂未填写科目描述'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <AIProjectDiagnosisCard projectId={projectId} />

      <Card className="content-card">
        <Tabs
          defaultActiveKey="tasks"
          items={[
            {
              key: 'tasks',
              label: '任务看板',
              children: (
                <Flex vertical gap={18}>
                  <Flex justify="flex-end" gap={8} wrap>
                    <Button icon={<UnorderedListOutlined />} onClick={() => navigate(`/projects/${projectId}/tasks`)}>
                      任务列表
                    </Button>
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateTaskOpen(true)}>
                      创建任务
                    </Button>
                    {personalTaskPermission.canPublish && (
                      <Button icon={<UserOutlined />} onClick={() => setCreatePersonalTaskOpen(true)}>
                        发布个人任务
                      </Button>
                    )}
                  </Flex>
                  {tasks.isError ? (
                    <Alert showIcon type="error" message="任务看板加载失败" action={<Button onClick={() => tasks.refetch()}>重试</Button>} />
                  ) : (
                    <TaskBoard projectId={projectId} tasks={tasks.data ?? []} loading={tasks.isPending} />
                  )}
                  {personalTaskPermission.canPublish && (
                    <ProjectPersonalTaskPanel projectId={projectId} />
                  )}
                </Flex>
              ),
            },
            {
              key: 'files',
              label: '文件',
              children: <ProjectFileIndexPanel projectId={projectId} />,
            },
          ]}
        />
      </Card>

      <Card
        className="content-card"
        title="科目成员"
        extra={
          <Space wrap>
            <Button icon={<CrownOutlined />} onClick={() => setOwnerOpen(true)}>转移负责人</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setMemberOpen(true)}>添加成员</Button>
          </Space>
        }
        loading={projectMembers.isPending}
      >
        {projectMembers.isError ? (
          <Alert showIcon type="error" message="科目成员加载失败" action={<Button onClick={() => projectMembers.refetch()}>重试</Button>} />
        ) : projectMembers.data?.length ? (
          <List
            dataSource={projectMembers.data}
            renderItem={(membership) => {
              const user = memberNames.get(membership.user_id)
              return (
                <List.Item
                  extra={
                    <Space>
                      <ProjectRoleTag role={membership.role} />
                      {membership.role !== 'owner' && (
                        <Popconfirm
                          title="移除科目成员"
                          description="移除后，该用户关联的 TaskMember 也会被后端清理。"
                          okText="移除"
                          cancelText="取消"
                          onConfirm={() => runAction(() => removeMutation.mutateAsync(membership.user_id), '成员已移除')}
                        >
                          <Button danger type="text" icon={<DeleteOutlined />} loading={removeMutation.isPending}>
                            移除
                          </Button>
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
          <Empty description="暂无科目成员" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      <Card className="content-card danger-zone-card" title="危险操作">
        <Flex justify="space-between" align="center" gap={16} wrap>
          <div>
            <Typography.Text strong>永久删除科目</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
              归档仍可通过科目状态操作；永久删除会同时清理任务和文件且无法恢复。
            </Typography.Paragraph>
          </div>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              setDeleteName('')
              setDeleteOpen(true)
            }}
          >
            永久删除科目
          </Button>
        </Flex>
      </Card>

      <Modal title="修改科目" open={editOpen} width={620} onCancel={() => setEditOpen(false)} onOk={() => runAction(async () => updateMutation.mutateAsync(toProjectUpdate(await editForm.validateFields())), '科目已更新', () => setEditOpen(false))} confirmLoading={updateMutation.isPending} okText="保存">
        <ProjectForm form={editForm} />
      </Modal>

      <Modal title="修改科目状态" open={statusOpen} onCancel={() => setStatusOpen(false)} onOk={() => runAction(async () => statusMutation.mutateAsync(await statusForm.validateFields()), '科目状态已更新', () => setStatusOpen(false))} confirmLoading={statusMutation.isPending} okText="更新">
        <Form form={statusForm} layout="vertical">
          <Form.Item name="status" label="目标状态" rules={[{ required: true }]}>
            <Select options={projectStatusOptions} />
          </Form.Item>
          <Alert showIcon type="info" message="状态流转和归档权限由后端校验；无效流转不会保存。" />
        </Form>
      </Modal>

      <Modal title="添加科目成员" open={memberOpen} onCancel={() => setMemberOpen(false)} onOk={() => runAction(async () => addMutation.mutateAsync(await addForm.validateFields()), '成员已添加', () => { setMemberOpen(false); addForm.resetFields() })} confirmLoading={addMutation.isPending} okText="添加">
        <Form form={addForm} layout="vertical">
          <Form.Item name="user_id" label="团队成员" rules={[{ required: true, message: '请选择成员' }]}>
            <Select showSearch optionFilterProp="label" placeholder="选择要加入科目的团队成员" options={availableTeamMembers.map((member) => ({ value: member.user_id, label: `${member.nickname || member.username} (@${member.username})` }))} />
          </Form.Item>
          {!availableTeamMembers.length && <Alert showIcon type="info" message="所有团队成员都已加入该科目" />}
        </Form>
      </Modal>

      <Modal title="转移科目负责人" open={ownerOpen} onCancel={() => setOwnerOpen(false)} onOk={() => runAction(async () => transferMutation.mutateAsync(await ownerForm.validateFields()), '科目负责人已转移', () => { setOwnerOpen(false); ownerForm.resetFields() })} confirmLoading={transferMutation.isPending} okText="确认转移">
        <Form form={ownerForm} layout="vertical">
          <Form.Item name="user_id" label="新负责人" rules={[{ required: true, message: '请选择新负责人' }]}>
            <Select showSearch optionFilterProp="label" placeholder="可选择任意团队成员" options={(teamMembers.data ?? []).map((member) => ({ value: member.user_id, label: `${member.nickname || member.username} (@${member.username})` }))} />
          </Form.Item>
          <Alert showIcon type="warning" message="原负责人将自动变为普通科目成员。" />
        </Form>
      </Modal>

      <Modal
        title="永久删除科目"
        open={deleteOpen}
        okText="永久删除"
        cancelText="取消"
        confirmLoading={deleteMutation.isPending}
        okButtonProps={{ danger: true, disabled: deleteName !== detail.name }}
        onOk={deleteCurrentProject}
        onCancel={() => {
          if (deleteMutation.isPending) return
          setDeleteOpen(false)
          setDeleteName('')
        }}
        closable={!deleteMutation.isPending}
        maskClosable={!deleteMutation.isPending}
      >
        <Alert
          showIcon
          type="error"
          message="删除后无法恢复"
          description="该科目下的任务、成员关系和文件都将被永久删除。"
          style={{ marginBottom: 16 }}
        />
        <Typography.Paragraph>
          请输入科目名称 <Typography.Text strong>{detail.name}</Typography.Text> 以确认：
        </Typography.Paragraph>
        <Input
          value={deleteName}
          onChange={(event) => setDeleteName(event.target.value)}
          placeholder={detail.name}
          disabled={deleteMutation.isPending}
          autoComplete="off"
        />
      </Modal>

      <CreateTaskModal
        projectId={projectId}
        teamMembers={teamMembers.data ?? []}
        open={createTaskOpen}
        onClose={() => setCreateTaskOpen(false)}
      />
      <PersonalTaskCreateModal
        projectId={projectId}
        teamMembers={teamMembers.data ?? []}
        open={createPersonalTaskOpen}
        onClose={() => setCreatePersonalTaskOpen(false)}
        onCreated={(taskId) => navigate(`/personal-tasks/${taskId}`)}
      />
    </Flex>
  )
}
