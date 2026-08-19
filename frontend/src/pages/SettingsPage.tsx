import {
  CalendarOutlined,
  CameraOutlined,
  DeleteOutlined,
  IdcardOutlined,
  LaptopOutlined,
  LockOutlined,
  LogoutOutlined,
  MailOutlined,
  MenuFoldOutlined,
  MoonOutlined,
  SaveOutlined,
  SunOutlined,
  UserOutlined,
} from '@ant-design/icons'
import {
  App,
  Avatar,
  Button,
  Card,
  Descriptions,
  Flex,
  Form,
  Input,
  Popconfirm,
  Result,
  Segmented,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
  Typography,
  Upload,
} from 'antd'
import type { UploadProps } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { resolveApiUrl } from '../api/client'
import { getApiErrorMessage } from '../api/errors'
import {
  logout,
  useChangePassword,
  useCurrentUser,
  useDeleteAvatar,
  useUpdateCurrentUser,
  useUploadAvatar,
} from '../features/auth/hooks'
import {
  usePreferencesStore,
  type DashboardDeadlineHours,
  type ThemePreference,
} from '../features/settings/store'

interface ProfileFormValues {
  nickname: string
  bio?: string
}

interface PasswordFormValues {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

const deadlineOptions: { value: DashboardDeadlineHours; label: string }[] = [
  { value: 24, label: '未来 24 小时' },
  { value: 48, label: '未来 48 小时' },
  { value: 72, label: '未来 72 小时' },
  { value: 168, label: '未来 7 天' },
]

export function SettingsPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const currentUser = useCurrentUser()
  const updateProfile = useUpdateCurrentUser()
  const changePassword = useChangePassword()
  const uploadAvatar = useUploadAvatar()
  const deleteAvatar = useDeleteAvatar()
  const [profileForm] = Form.useForm<ProfileFormValues>()
  const [passwordForm] = Form.useForm<PasswordFormValues>()
  const profileFormInitialized = useRef(false)
  const sidebarCollapsed = usePreferencesStore((state) => state.sidebarCollapsed)
  const theme = usePreferencesStore((state) => state.theme)
  const dashboardDeadlineHours = usePreferencesStore((state) => state.dashboardDeadlineHours)
  const setSidebarCollapsed = usePreferencesStore((state) => state.setSidebarCollapsed)
  const setTheme = usePreferencesStore((state) => state.setTheme)
  const setDashboardDeadlineHours = usePreferencesStore((state) => state.setDashboardDeadlineHours)

  useEffect(() => {
    if (!currentUser.data || profileFormInitialized.current) return
    profileForm.setFieldsValue({
      nickname: currentUser.data.nickname || '',
      bio: currentUser.data.bio || '',
    })
    profileFormInitialized.current = true
  }, [currentUser.data, profileForm])

  if (currentUser.isPending) return <Card><Skeleton active avatar paragraph={{ rows: 8 }} /></Card>
  if (currentUser.isError || !currentUser.data) {
    return <Result status="error" title="账号信息加载失败" extra={<Button onClick={() => currentUser.refetch()}>重试</Button>} />
  }

  const user = currentUser.data
  const avatarUrl = resolveApiUrl(user.avatar_url)
  const versionedAvatarUrl = avatarUrl
    ? `${avatarUrl}${avatarUrl.includes('?') ? '&' : '?'}v=${encodeURIComponent(user.updated_at)}`
    : undefined

  const signOut = () => {
    logout()
    message.success('已退出登录')
    navigate('/login', { replace: true })
  }

  const submitProfile = async (values: ProfileFormValues) => {
    try {
      await updateProfile.mutateAsync({
        nickname: values.nickname.trim(),
        bio: values.bio?.trim() || null,
      })
      message.success('账号资料已更新')
    } catch (error) {
      message.error(getApiErrorMessage(error, '账号资料更新失败'))
    }
  }

  const submitPassword = async (values: PasswordFormValues) => {
    try {
      await changePassword.mutateAsync({
        current_password: values.currentPassword,
        new_password: values.newPassword,
      })
      passwordForm.resetFields()
      message.success('密码修改成功，请重新登录')
      logout()
      navigate('/login', { replace: true })
    } catch (error) {
      message.error(getApiErrorMessage(error, '密码修改失败'))
    }
  }

  const avatarRequest: UploadProps['customRequest'] = async ({ file, onSuccess, onError }) => {
    if (!(file instanceof File)) return
    try {
      const updatedUser = await uploadAvatar.mutateAsync(file)
      onSuccess?.(updatedUser)
      message.success('头像已更新')
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('头像上传失败'))
      message.error(getApiErrorMessage(error, '头像上传失败'))
    }
  }

  const removeAvatar = async () => {
    try {
      await deleteAvatar.mutateAsync()
      message.success('头像已删除')
    } catch (error) {
      message.error(getApiErrorMessage(error, '头像删除失败'))
    }
  }

  return (
    <Flex vertical gap={24}>
      <div>
        <Typography.Title level={2} style={{ margin: 0 }}>用户设置</Typography.Title>
        <Typography.Text type="secondary">管理账号资料、安全设置和当前设备偏好</Typography.Text>
      </div>

      <Card className="content-card" title="账号资料">
        <div className="settings-profile-layout">
          <Flex vertical align="center" gap={14} className="settings-avatar-panel">
            <Avatar size={96} src={versionedAvatarUrl} icon={<UserOutlined />} />
            <Space wrap className="settings-avatar-actions">
              <Upload
                accept="image/jpeg,image/png,image/webp"
                showUploadList={false}
                customRequest={avatarRequest}
                disabled={uploadAvatar.isPending}
              >
                <Button icon={<CameraOutlined />} loading={uploadAvatar.isPending}>
                  上传头像
                </Button>
              </Upload>
              {user.avatar_url && (
                <Popconfirm
                  title="删除头像"
                  description="删除后将恢复默认头像，确定继续吗？"
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                  onConfirm={removeAvatar}
                >
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    loading={deleteAvatar.isPending}
                  >
                    删除
                  </Button>
                </Popconfirm>
              )}
            </Space>
            <Typography.Text type="secondary" className="settings-avatar-hint">
              支持 JPEG、PNG、WebP，最大 5 MB
            </Typography.Text>
          </Flex>

          <Flex vertical gap={20} className="settings-profile-content">
            <Descriptions column={{ xs: 1, md: 2 }}>
              <Descriptions.Item label="用户名"><UserOutlined /> {user.username}</Descriptions.Item>
              <Descriptions.Item label="邮箱"><MailOutlined /> {user.email || '未设置'}</Descriptions.Item>
              <Descriptions.Item label="用户 ID" span={2}><IdcardOutlined /> {user.id}</Descriptions.Item>
              <Descriptions.Item label="账号状态">
                <Tag color={user.is_active ? 'success' : 'error'}>{user.is_active ? '正常' : '已停用'}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">{dayjs(user.updated_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
            </Descriptions>

            <Form<ProfileFormValues>
              form={profileForm}
              layout="vertical"
              onFinish={submitProfile}
              requiredMark={false}
            >
              <Form.Item
                name="nickname"
                label="昵称"
                rules={[
                  { required: true, whitespace: true, message: '请输入昵称' },
                  { max: 100, message: '昵称不能超过 100 个字符' },
                ]}
              >
                <Input prefix={<UserOutlined />} maxLength={100} placeholder="请输入昵称" />
              </Form.Item>
              <Form.Item
                name="bio"
                label="个人简介"
                rules={[{ max: 1000, message: '个人简介不能超过 1000 个字符' }]}
              >
                <Input.TextArea
                  rows={4}
                  maxLength={1000}
                  showCount
                  placeholder="介绍一下自己或你擅长的协作内容"
                />
              </Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<SaveOutlined />}
                loading={updateProfile.isPending}
              >
                保存资料
              </Button>
            </Form>
          </Flex>
        </div>
      </Card>

      <Card className="content-card" title="账号安全">
        <Form<PasswordFormValues>
          form={passwordForm}
          layout="vertical"
          className="settings-password-form"
          onFinish={submitPassword}
          requiredMark={false}
        >
          <Form.Item
            name="currentPassword"
            label="原密码"
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            name="newPassword"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '新密码至少需要 8 个字符' },
              { max: 128, message: '新密码不能超过 128 个字符' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label="确认新密码"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的新密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
          </Form.Item>
          <Flex justify="space-between" align="center" gap={16} wrap>
            <Typography.Text type="secondary">修改成功后将退出当前账号，需要使用新密码重新登录。</Typography.Text>
            <Button type="primary" htmlType="submit" loading={changePassword.isPending}>
              修改密码
            </Button>
          </Flex>
        </Form>
      </Card>

      <Card className="content-card" title="本地偏好">
        <Flex vertical gap={24}>
          <Flex justify="space-between" align="center" gap={20} wrap>
            <Space align="start">
              <MenuFoldOutlined className="settings-preference-icon" />
              <div>
                <Typography.Text strong>折叠侧边栏</Typography.Text>
                <br />
                <Typography.Text type="secondary">为主要内容留出更多显示空间</Typography.Text>
              </div>
            </Space>
            <Switch checked={sidebarCollapsed} onChange={setSidebarCollapsed} />
          </Flex>

          <Flex justify="space-between" align="center" gap={20} wrap>
            <Space align="start">
              <LaptopOutlined className="settings-preference-icon" />
              <div>
                <Typography.Text strong>主题偏好</Typography.Text>
                <br />
                <Typography.Text type="secondary">仅保存在当前浏览器</Typography.Text>
              </div>
            </Space>
            <Segmented<ThemePreference>
              value={theme}
              onChange={setTheme}
              options={[
                { value: 'light', label: '浅色', icon: <SunOutlined /> },
                { value: 'dark', label: '深色', icon: <MoonOutlined /> },
              ]}
            />
          </Flex>

          <Flex justify="space-between" align="center" gap={20} wrap>
            <Space align="start">
              <CalendarOutlined className="settings-preference-icon" />
              <div>
                <Typography.Text strong>Dashboard 默认截止范围</Typography.Text>
                <br />
                <Typography.Text type="secondary">控制概览页“即将截止”任务的时间窗口</Typography.Text>
              </div>
            </Space>
            <Select
              value={dashboardDeadlineHours}
              options={deadlineOptions}
              style={{ width: 160 }}
              onChange={setDashboardDeadlineHours}
            />
          </Flex>
        </Flex>
      </Card>

      <Card className="content-card" title="账号操作">
        <Flex justify="space-between" align="center" gap={16} wrap>
          <div>
            <Typography.Text strong>退出当前账号</Typography.Text>
            <br />
            <Typography.Text type="secondary">清除当前登录状态并返回登录页</Typography.Text>
          </div>
          <Button danger icon={<LogoutOutlined />} onClick={signOut}>退出登录</Button>
        </Flex>
      </Card>
    </Flex>
  )
}
