import {
  ArrowRightOutlined,
  BookOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Alert, App, Button, Card, Col, Empty, Flex, Form, Input, Modal, Row, Skeleton, Space, Typography } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/errors'
import { useCreateTeam, useJoinTeam, useTeams } from '../features/teams/hooks'
import { TeamRoleTag } from '../features/teams/role'
import type { TeamCreateRequest, TeamJoinRequest } from '../features/teams/types'

const { TextArea } = Input

export function TeamsPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const teams = useTeams()
  const createMutation = useCreateTeam()
  const joinMutation = useJoinTeam()
  const [createOpen, setCreateOpen] = useState(false)
  const [joinOpen, setJoinOpen] = useState(false)
  const [createForm] = Form.useForm<TeamCreateRequest>()
  const [joinForm] = Form.useForm<TeamJoinRequest>()

  const submitCreate = async () => {
    try {
      const values = await createForm.validateFields()
      const team = await createMutation.mutateAsync(values)
      message.success('团队创建成功')
      setCreateOpen(false)
      createForm.resetFields()
      navigate(`/teams/${team.id}`)
    } catch (error) {
      if (error instanceof Error) message.error(getApiErrorMessage(error))
    }
  }

  const submitJoin = async () => {
    try {
      const values = await joinForm.validateFields()
      const team = await joinMutation.mutateAsync(values)
      message.success(`已加入 ${team.name}`)
      setJoinOpen(false)
      joinForm.resetFields()
      navigate(`/teams/${team.id}`)
    } catch (error) {
      if (error instanceof Error) message.error(getApiErrorMessage(error))
    }
  }

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="flex-start" gap={16} wrap>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>我的团队</Typography.Title>
          <Typography.Text type="secondary">管理你参加的课程小组</Typography.Text>
        </div>
        <Space wrap>
          <Button icon={<SafetyCertificateOutlined />} onClick={() => setJoinOpen(true)}>
            使用邀请码加入
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            创建团队
          </Button>
        </Space>
      </Flex>

      {teams.isError && <Alert showIcon type="error" message="团队列表加载失败" action={<Button onClick={() => teams.refetch()}>重试</Button>} />}
      {teams.isPending ? (
        <Row gutter={[16, 16]}>{[1, 2, 3].map((item) => <Col xs={24} md={12} xl={8} key={item}><Card><Skeleton active /></Card></Col>)}</Row>
      ) : teams.data?.length ? (
        <Row gutter={[16, 16]}>
          {teams.data.map((team) => (
            <Col xs={24} md={12} xl={8} key={team.id}>
              <Card
                hoverable
                className="team-card"
                onClick={() => navigate(`/teams/${team.id}`)}
                actions={[<span key="detail">进入团队 <ArrowRightOutlined /></span>]}
              >
                <Flex vertical gap={14}>
                  <Flex justify="space-between" align="flex-start" gap={12}>
                    <span className="team-card-icon"><TeamOutlined /></span>
                    <TeamRoleTag role={team.role} />
                  </Flex>
                  <div>
                    <Typography.Title level={4} ellipsis={{ rows: 1 }} style={{ margin: 0 }}>{team.name}</Typography.Title>
                    {team.course_name && <Typography.Text type="secondary"><BookOutlined /> {team.course_name}</Typography.Text>}
                  </div>
                  <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ minHeight: 44, margin: 0 }}>
                    {team.description || '暂未填写团队描述'}
                  </Typography.Paragraph>
                </Flex>
              </Card>
            </Col>
          ))}
        </Row>
      ) : !teams.isError ? (
        <Card><Empty description="你还没有加入团队" image={Empty.PRESENTED_IMAGE_SIMPLE}><Button type="primary" onClick={() => setCreateOpen(true)}>创建第一个团队</Button></Empty></Card>
      ) : null}

      <Modal title="创建团队" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={submitCreate} confirmLoading={createMutation.isPending} okText="创建">
        <Form form={createForm} layout="vertical" requiredMark={false}>
          <Form.Item name="name" label="团队名称" rules={[{ required: true, message: '请输入团队名称' }, { max: 120 }]}><Input placeholder="例如 数据库课程小组" /></Form.Item>
          <Form.Item name="course_name" label="课程名称（可选）" rules={[{ max: 160 }]}><Input placeholder="例如 数据库系统" /></Form.Item>
          <Form.Item name="description" label="团队描述（可选）" rules={[{ max: 5000 }]}><TextArea rows={4} showCount maxLength={5000} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="使用邀请码加入团队" open={joinOpen} onCancel={() => setJoinOpen(false)} onOk={submitJoin} confirmLoading={joinMutation.isPending} okText="加入">
        <Form form={joinForm} layout="vertical" requiredMark={false}>
          <Form.Item name="invite_code" label="邀请码" rules={[{ required: true, message: '请输入邀请码' }, { max: 256 }]}><Input prefix={<SafetyCertificateOutlined />} placeholder="输入团队邀请码" /></Form.Item>
        </Form>
      </Modal>
    </Flex>
  )
}
