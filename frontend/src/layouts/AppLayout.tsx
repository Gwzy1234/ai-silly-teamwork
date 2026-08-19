import {
  BellOutlined,
  CheckSquareOutlined,
  DashboardOutlined,
  FolderOpenOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Avatar, Badge, Button, Drawer, Dropdown, Layout, Menu, Space, Typography } from 'antd'
import type { MenuProps } from 'antd'
import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import '../App.css'
import { resolveApiUrl } from '../api/client'
import { useCurrentUser, logout } from '../features/auth/hooks'
import { useNotifications } from '../features/notifications/hooks'
import { usePreferencesStore } from '../features/settings/store'
import { useTeams } from '../features/teams/hooks'

const { Header, Content, Sider } = Layout

export function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const currentUser = useCurrentUser().data
  const notifications = useNotifications()
  const teams = useTeams()
  const unreadCount = notifications.data?.filter((item) => !item.is_read).length ?? 0
  const sidebarCollapsed = usePreferencesStore((state) => state.sidebarCollapsed)
  const toggleSidebar = usePreferencesStore((state) => state.toggleSidebar)
  const theme = usePreferencesStore((state) => state.theme)
  const avatarUrl = resolveApiUrl(currentUser?.avatar_url)
  const versionedAvatarUrl = avatarUrl && currentUser
    ? `${avatarUrl}${avatarUrl.includes('?') ? '&' : '?'}v=${encodeURIComponent(currentUser.updated_at)}`
    : undefined

  const teamNavigationItems: MenuProps['items'] = teams.isPending
    ? [{ key: 'teams-loading', label: '正在加载团队…', disabled: true }]
    : teams.data?.length
      ? teams.data.map((team) => ({
          key: `/teams/${team.id}`,
          icon: <TeamOutlined />,
          label: <span className="team-navigation-label">{team.name}</span>,
        }))
      : [{ key: 'teams-empty', label: '暂无团队', disabled: true }]

  const navigationItems: MenuProps['items'] = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: '概览' },
    { key: '/my-tasks', icon: <CheckSquareOutlined />, label: '我的任务' },
    { key: '/files', icon: <FolderOpenOutlined />, label: '文件池' },
    {
      type: 'group',
      key: 'team-navigation-group',
      label: '我的团队',
      children: teamNavigationItems,
    },
    {
      key: '/notifications',
      icon: <BellOutlined />,
      label: <Space size={8}>通知中心 <Badge count={unreadCount} size="small" /></Space>,
    },
    { key: '/settings', icon: <SettingOutlined />, label: '用户设置' },
  ]
  const selectedNavigationKey = location.pathname

  const navigateFromMobileMenu = (key: string) => {
    setMobileNavigationOpen(false)
    navigate(key)
  }

  return (
    <Layout className="app-layout">
      <Sider
        width={236}
        collapsedWidth={72}
        collapsed={sidebarCollapsed}
        theme={theme}
        className="app-sider"
      >
        <div className="app-brand">
          <span className="app-logo">
            <TeamOutlined />
          </span>
          {!sidebarCollapsed && <span>Silly Teamwork</span>}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedNavigationKey]}
          items={navigationItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Button
            type="text"
            className="sidebar-toggle desktop-sidebar-toggle"
            aria-label={sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'}
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={toggleSidebar}
          />
          <Button
            type="text"
            className="mobile-menu-toggle"
            aria-label="打开导航菜单"
            icon={<MenuUnfoldOutlined />}
            onClick={() => setMobileNavigationOpen(true)}
          />
          <Typography.Text className="mobile-header-title" strong>
            Silly Teamwork
          </Typography.Text>
          <Button
            type="text"
            className="app-header-action"
            aria-label="通知中心"
            icon={<Badge count={unreadCount} size="small"><BellOutlined /></Badge>}
            onClick={() => navigate('/notifications')}
          />
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: () => {
                    logout()
                    navigate('/login', { replace: true })
                  },
                },
              ],
            }}
          >
            <Button type="text" className="app-user-menu" aria-label="用户菜单">
              <Space>
                <Avatar size="small" src={versionedAvatarUrl} icon={<UserOutlined />} />
                <Typography.Text strong className="app-user-name">
                  {currentUser?.nickname || currentUser?.username}
                </Typography.Text>
              </Space>
            </Button>
          </Dropdown>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
      <Drawer
        className="mobile-navigation-drawer"
        placement="left"
        width={280}
        open={mobileNavigationOpen}
        onClose={() => setMobileNavigationOpen(false)}
        closable={false}
        title={null}
      >
        <div className="app-brand mobile-drawer-brand">
          <span className="app-logo">
            <TeamOutlined />
          </span>
          <span>Silly Teamwork</span>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedNavigationKey]}
          items={navigationItems}
          onClick={({ key }) => navigateFromMobileMenu(key)}
        />
      </Drawer>
    </Layout>
  )
}
