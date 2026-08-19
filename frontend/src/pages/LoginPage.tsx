import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, App, Button, Card, Form, Input, Typography } from 'antd'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/errors'
import { useLogin } from '../features/auth/hooks'
import type { LoginRequest } from '../features/auth/types'

interface LoginLocationState {
  from?: { pathname?: string; search?: string }
  registrationSuccess?: boolean
  username?: string
}

export function LoginPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as LoginLocationState | null
  const loginMutation = useLogin()

  const handleSubmit = async (values: LoginRequest) => {
    try {
      await loginMutation.mutateAsync(values)
      message.success('登录成功')
      const destination = state?.from?.pathname
        ? `${state.from.pathname}${state.from.search || ''}`
        : '/dashboard'
      navigate(destination, { replace: true })
    } catch {
      // The mutation error is rendered below the form.
    }
  }

  return (
    <Card className="auth-card" bordered={false}>
      <div className="auth-title">
        <Typography.Title level={2}>欢迎回来</Typography.Title>
        <Typography.Text type="secondary">登录后继续管理你的团队任务</Typography.Text>
      </div>

      {state?.registrationSuccess && (
        <Alert
          showIcon
          type="success"
          message="注册成功，请使用新账号登录"
          style={{ marginBottom: 20 }}
        />
      )}
      {loginMutation.isError && (
        <Alert
          showIcon
          closable
          type="error"
          message={getApiErrorMessage(loginMutation.error, '用户名或密码错误')}
          style={{ marginBottom: 20 }}
        />
      )}

      <Form<LoginRequest>
        layout="vertical"
        requiredMark={false}
        initialValues={{ username: state?.username || '' }}
        onFinish={handleSubmit}
      >
        <Form.Item
          name="username"
          label="用户名"
          rules={[{ required: true, message: '请输入用户名' }]}
        >
          <Input
            size="large"
            autoComplete="username"
            prefix={<UserOutlined />}
            placeholder="请输入用户名"
          />
        </Form.Item>
        <Form.Item
          name="password"
          label="密码"
          rules={[{ required: true, message: '请输入密码' }]}
        >
          <Input.Password
            size="large"
            autoComplete="current-password"
            prefix={<LockOutlined />}
            placeholder="请输入密码"
          />
        </Form.Item>
        <Button
          block
          size="large"
          type="primary"
          htmlType="submit"
          loading={loginMutation.isPending}
        >
          登录
        </Button>
      </Form>

      <div className="auth-footer">
        <Typography.Text type="secondary">还没有账号？</Typography.Text>{' '}
        <Link to="/register">使用邀请码注册</Link>
      </div>
    </Card>
  )
}
