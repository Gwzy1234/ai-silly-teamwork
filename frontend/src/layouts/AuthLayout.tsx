import { TeamOutlined } from '@ant-design/icons'
import { Typography } from 'antd'
import { Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <main className="auth-shell">
      <div className="auth-content">
        <header className="auth-brand">
          <span className="auth-logo">
            <TeamOutlined />
          </span>
          <Typography.Title level={1}>Silly Teamwork</Typography.Title>
          <Typography.Text type="secondary">让大学小组协作更简单</Typography.Text>
        </header>
        <Outlet />
      </div>
    </main>
  )
}
