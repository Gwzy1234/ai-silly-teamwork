import {
  IdcardOutlined,
  LockOutlined,
  MailOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/errors'
import { useRegister } from '../features/auth/hooks'
import type { RegisterRequest } from '../features/auth/types'

interface RegisterFormValues extends RegisterRequest {
  confirmPassword: string
}

export function RegisterPage() {
  const navigate = useNavigate()
  const registerMutation = useRegister()

  const handleSubmit = async ({ confirmPassword: _, ...values }: RegisterFormValues) => {
    try {
      const user = await registerMutation.mutateAsync({
        ...values,
        email: values.email || null,
      })
      navigate('/login', {
        replace: true,
        state: { registrationSuccess: true, username: user.username },
      })
    } catch {
      // The mutation error is rendered below the heading.
    }
  }

  return (
    <Card className="auth-card" bordered={false}>
      <div className="auth-title">
        <Typography.Title level={2}>创建账号</Typography.Title>
        <Typography.Text type="secondary">使用有效邀请码加入 Silly Teamwork</Typography.Text>
      </div>

      {registerMutation.isError && (
        <Alert
          showIcon
          closable
          type="error"
          message={getApiErrorMessage(registerMutation.error, '注册失败，请检查填写内容')}
          style={{ marginBottom: 20 }}
        />
      )}

      <Form<RegisterFormValues>
        layout="vertical"
        requiredMark={false}
        onFinish={handleSubmit}
      >
        <Form.Item
          name="username"
          label="用户名"
          rules={[
            { required: true, message: '请输入用户名' },
            { min: 3, max: 50, message: '用户名长度为 3–50 个字符' },
            {
              pattern: /^[A-Za-z0-9_-]+$/,
              message: '只能包含字母、数字、下划线和连字符',
            },
          ]}
        >
          <Input
            size="large"
            autoComplete="username"
            prefix={<UserOutlined />}
            placeholder="例如 alice_chen"
          />
        </Form.Item>
        <Form.Item
          name="nickname"
          label="昵称"
          rules={[
            { required: true, message: '请输入昵称' },
            { max: 100, message: '昵称不能超过 100 个字符' },
          ]}
        >
          <Input size="large" prefix={<IdcardOutlined />} placeholder="你希望显示的名字" />
        </Form.Item>
        <Form.Item
          name="email"
          label="邮箱（可选）"
          rules={[{ type: 'email', message: '请输入有效邮箱地址' }]}
        >
          <Input
            size="large"
            type="email"
            autoComplete="email"
            prefix={<MailOutlined />}
            placeholder="name@example.edu"
          />
        </Form.Item>
        <Form.Item
          name="password"
          label="密码"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 8, max: 128, message: '密码长度为 8–128 个字符' },
          ]}
        >
          <Input.Password
            size="large"
            autoComplete="new-password"
            prefix={<LockOutlined />}
            placeholder="至少 8 个字符"
          />
        </Form.Item>
        <Form.Item
          name="confirmPassword"
          label="确认密码"
          dependencies={['password']}
          rules={[
            { required: true, message: '请再次输入密码' },
            ({ getFieldValue }) => ({
              validator(_, value: string) {
                return !value || getFieldValue('password') === value
                  ? Promise.resolve()
                  : Promise.reject(new Error('两次输入的密码不一致'))
              },
            }),
          ]}
        >
          <Input.Password
            size="large"
            autoComplete="new-password"
            prefix={<LockOutlined />}
            placeholder="再次输入密码"
          />
        </Form.Item>
        <Form.Item
          name="invite_code"
          label="邀请码"
          rules={[{ required: true, message: '请输入邀请码' }]}
        >
          <Input
            size="large"
            prefix={<SafetyCertificateOutlined />}
            placeholder="例如 ST-DEV-2026"
          />
        </Form.Item>
        <Button
          block
          size="large"
          type="primary"
          htmlType="submit"
          loading={registerMutation.isPending}
        >
          注册
        </Button>
      </Form>

      <div className="auth-footer">
        <Typography.Text type="secondary">已有账号？</Typography.Text>{' '}
        <Link to="/login">返回登录</Link>
      </div>
    </Card>
  )
}
