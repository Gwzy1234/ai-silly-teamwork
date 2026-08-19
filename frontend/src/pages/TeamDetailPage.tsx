import {
  ArrowLeftOutlined,
  BookOutlined,
  CopyOutlined,
  DeleteOutlined,
  LinkOutlined,
  PlusOutlined,
  TeamOutlined,
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
  Result,
  Select,
  Skeleton,
  Space,
  Statistic,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, getApiErrorMessage } from '../api/errors'
import {
  useCreateTeamInvitation,
  useDeleteTeam,
  useTeam,
  useTeamMembers,
} from '../features/teams/hooks'
import { TeamRoleTag } from '../features/teams/role'
import type { InvitationCreateRequest } from '../features/teams/types'
import { ProjectForm } from '../features/projects/components/ProjectForm'
import { toProjectCreate, type ProjectFormValues } from '../features/projects/forms'
import { useCreateProject, useProjects } from '../features/projects/hooks'
import { ProjectStatusTag } from '../features/projects/presentation'

export function TeamDetailPage() {
  const { teamId = '' } = useParams()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const team = useTeam(teamId)
  const members = useTeamMembers(teamId)
  const inviteMutation = useCreateTeamInvitation(teamId)
  const deleteMutation = useDeleteTeam(teamId)
  const projects = useProjects(teamId)
  const createProjectMutation = useCreateProject(teamId)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteCode, setInviteCode] = useState<string | null>(null)
  const [inviteForm] = Form.useForm<InvitationCreateRequest>()
  const [projectOpen, setProjectOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteName, setDeleteName] = useState('')
  const [projectForm] = Form.useForm<ProjectFormValues>()

  const createInvite = async () => {
    try {
      const values = await inviteForm.validateFields()
      const invitation = await inviteMutation.mutateAsync(values)
      setInviteCode(invitation.invite_code)
    } catch (error) {
      if (error instanceof Error) message.error(getApiErrorMessage(error))
    }
  }

  const submitProject = async () => {
    try {
      const values = await projectForm.validateFields()
      const project = await createProjectMutation.mutateAsync(toProjectCreate(values))
      message.success('科目创建成功')
      setProjectOpen(false)
      projectForm.resetFields()
      navigate(`/projects/${project.id}`)
    } catch (error) {
      if (error instanceof Error) message.error(getApiErrorMessage(error))
    }
  }

  const deleteCurrentTeam = async () => {
    if (!team.data || deleteName !== team.data.name) return
    try {
      await deleteMutation.mutateAsync()
      message.success('小组已删除')
      navigate('/teams', { replace: true })
    } catch (error) {
      message.error(
        error instanceof ApiError && error.status === 403
          ? '无权限删除该小组'
          : getApiErrorMessage(error),
      )
    }
  }

  if (team.isPending) {
    return <Card><Skeleton active paragraph={{ rows: 8 }} /></Card>
  }
  if (team.isError || !team.data) {
    return <Result status="404" title="团队不存在或你无权访问" extra={<Button onClick={() => navigate('/teams')}>返回团队列表</Button>} />
  }

  const detail = team.data
  const memberList = members.data ?? detail.members

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <Space align="start">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/teams')} />
          <div>
            <Space wrap>
              <Typography.Title level={2} style={{ margin: 0 }}>{detail.name}</Typography.Title>
              <TeamRoleTag role={detail.role} />
            </Space>
            <Typography.Text type="secondary">{detail.course_name || '未设置课程名称'}</Typography.Text>
          </div>
        </Space>
        {detail.role === 'leader' && (
          <Button type="primary" icon={<LinkOutlined />} onClick={() => { setInviteCode(null); setInviteOpen(true) }}>
            生成邀请码
          </Button>
        )}
      </Flex>

      <Card className="content-card">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="课程"><BookOutlined /> {detail.course_name || '未设置'}</Descriptions.Item>
          <Descriptions.Item label="成员数量"><TeamOutlined /> {memberList.length}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
          <Descriptions.Item label="我的角色"><TeamRoleTag role={detail.role} /></Descriptions.Item>
          <Descriptions.Item label="团队描述" span={2}>{detail.description || '暂未填写团队描述'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        className="content-card"
        title="团队科目"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setProjectOpen(true)}>
            创建科目
          </Button>
        }
        loading={projects.isPending}
      >
        {projects.isError ? (
          <Alert
            showIcon
            type="error"
            message="科目列表加载失败"
            action={<Button onClick={() => projects.refetch()}>重试</Button>}
          />
        ) : projects.data?.length ? (
          <List
            grid={{ gutter: 16, xs: 1, md: 2, xl: 3 }}
            dataSource={projects.data}
            renderItem={(project) => (
              <List.Item>
                <Card
                  hoverable
                  className="project-card"
                  onClick={() => navigate(`/projects/${project.id}`)}
                >
                  <Flex vertical gap={12}>
                    <Flex justify="space-between" gap={12}>
                      <Typography.Title level={4} ellipsis={{ rows: 1 }} style={{ margin: 0 }}>
                        {project.name}
                      </Typography.Title>
                      <ProjectStatusTag status={project.status} />
                    </Flex>
                    <Typography.Paragraph
                      type="secondary"
                      ellipsis={{ rows: 2 }}
                      style={{ minHeight: 44, margin: 0 }}
                    >
                      {project.description || '暂未填写科目描述'}
                    </Typography.Paragraph>
                    <Typography.Text type="secondary">
                      开始：{project.starts_at ? dayjs(project.starts_at).format('YYYY-MM-DD HH:mm') : '未设置'}
                    </Typography.Text>
                    <Typography.Text type={project.due_at && dayjs(project.due_at).isBefore(dayjs()) ? 'danger' : 'secondary'}>
                      截止：{project.due_at ? dayjs(project.due_at).format('YYYY-MM-DD HH:mm') : '未设置'}
                    </Typography.Text>
                  </Flex>
                </Card>
              </List.Item>
            )}
          />
        ) : (
          <Empty description="当前团队暂无可访问科目" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      <Card
        className="content-card"
        title="团队成员"
        extra={<Statistic value={memberList.length} suffix="人" valueStyle={{ fontSize: 18 }} />}
        loading={members.isPending}
      >
        {members.isError && <Alert showIcon type="warning" message="独立成员接口加载失败，当前展示团队详情中的成员快照。" style={{ marginBottom: 16 }} />}
        {memberList.length ? (
          <List
            dataSource={memberList}
            renderItem={(member) => (
              <List.Item extra={<TeamRoleTag role={member.role} />}>
                <List.Item.Meta
                  avatar={<Avatar icon={<UserOutlined />} />}
                  title={member.nickname || member.username}
                  description={`@${member.username} · 加入于 ${dayjs(member.joined_at).format('YYYY-MM-DD')}`}
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无成员" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      <Card className="content-card danger-zone-card" title="危险操作">
        <Flex justify="space-between" align="center" gap={16} wrap>
          <div>
            <Typography.Text strong>删除小组</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
              将永久删除小组内所有科目、任务和文件，此操作无法恢复。
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
            删除小组
          </Button>
        </Flex>
      </Card>

      <Modal
        title="生成团队邀请码"
        open={inviteOpen}
        onCancel={() => setInviteOpen(false)}
        footer={
          inviteCode
            ? [<Button key="close" type="primary" onClick={() => setInviteOpen(false)}>完成</Button>]
            : undefined
        }
        onOk={createInvite}
        confirmLoading={inviteMutation.isPending}
        okText="生成"
      >
        {inviteCode ? (
          <Flex vertical gap={12}>
            <Alert showIcon type="success" message="邀请码已生成" description="邀请码只会在此处显示，请立即复制并发送给成员。" />
            <Input
              readOnly
              size="large"
              value={inviteCode}
              addonAfter={
                <Button
                  type="text"
                  icon={<CopyOutlined />}
                  onClick={async () => {
                    await navigator.clipboard.writeText(inviteCode)
                    message.success('邀请码已复制')
                  }}
                >
                  复制
                </Button>
              }
            />
          </Flex>
        ) : (
          <Form form={inviteForm} layout="vertical" initialValues={{ role: 'member' }}>
            <Form.Item name="role" label="加入后的角色" rules={[{ required: true }]}>
              <Select options={[{ value: 'member', label: '普通成员' }, { value: 'leader', label: '组长' }]} />
            </Form.Item>
            <Typography.Paragraph type="secondary">
              邀请码为一次性使用。生成组长邀请码意味着受邀用户也可以管理团队邀请。
            </Typography.Paragraph>
          </Form>
        )}
      </Modal>

      <Modal
        title="创建科目"
        open={projectOpen}
        width={620}
        onCancel={() => setProjectOpen(false)}
        onOk={submitProject}
        confirmLoading={createProjectMutation.isPending}
        okText="创建"
      >
        <ProjectForm form={projectForm} teamMembers={memberList} showOwner />
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          创建权限由后端验证；没有权限时不会保存任何科目数据。
        </Typography.Paragraph>
      </Modal>

      <Modal
        title="删除小组"
        open={deleteOpen}
        okText="永久删除"
        cancelText="取消"
        confirmLoading={deleteMutation.isPending}
        okButtonProps={{ danger: true, disabled: deleteName !== detail.name }}
        onOk={deleteCurrentTeam}
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
          message="这是不可恢复的操作"
          description="该小组下的科目、任务、成员关系和文件都会被永久删除。"
          style={{ marginBottom: 16 }}
        />
        <Typography.Paragraph>
          请输入小组名称 <Typography.Text strong>{detail.name}</Typography.Text> 以确认：
        </Typography.Paragraph>
        <Input
          value={deleteName}
          onChange={(event) => setDeleteName(event.target.value)}
          placeholder={detail.name}
          disabled={deleteMutation.isPending}
          autoComplete="off"
        />
      </Modal>
    </Flex>
  )
}
