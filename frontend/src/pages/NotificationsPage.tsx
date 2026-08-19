import { CheckOutlined } from '@ant-design/icons'
import { Alert, App, Badge, Button, Card, Empty, Flex, List, Space, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/errors'
import {
  formatNotificationContent,
  formatNotificationDateTime,
} from '../features/notifications/formatters'
import {
  useMarkAllNotificationsAsRead,
  useMarkNotificationAsRead,
  useNotifications,
} from '../features/notifications/hooks'
import { NotificationTypeTag } from '../features/notifications/presentation'
import type { Notification } from '../features/notifications/types'

function notificationTarget(notification: Notification) {
  if (notification.related_task_id) return `/tasks/${notification.related_task_id}`
  if (notification.related_project_id) return `/projects/${notification.related_project_id}`
  return null
}

export function NotificationsPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const notifications = useNotifications()
  const markRead = useMarkNotificationAsRead()
  const markAllRead = useMarkAllNotificationsAsRead()
  const unreadCount = notifications.data?.filter((item) => !item.is_read).length ?? 0

  const openNotification = async (notification: Notification) => {
    try {
      if (!notification.is_read) await markRead.mutateAsync(notification.id)
      const target = notificationTarget(notification)
      if (target) navigate(target)
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  const markAll = async () => {
    try {
      const result = await markAllRead.mutateAsync()
      message.success(result.updated_count ? `已将 ${result.updated_count} 条通知标记为已读` : '没有未读通知')
    } catch (error) {
      message.error(getApiErrorMessage(error))
    }
  }

  return (
    <Flex vertical gap={24}>
      <Flex justify="space-between" align="center" gap={16} wrap>
        <div>
          <Space align="center">
            <Typography.Title level={2} style={{ margin: 0 }}>通知中心</Typography.Title>
            <Badge count={unreadCount} overflowCount={99} />
          </Space>
          <Typography.Text type="secondary">查看任务截止、科目进度与系统提醒</Typography.Text>
        </div>
        <Button
          icon={<CheckOutlined />}
          disabled={!unreadCount}
          loading={markAllRead.isPending}
          onClick={() => void markAll()}
        >
          全部标记为已读
        </Button>
      </Flex>

      <Card className="content-card" loading={notifications.isPending}>
        {notifications.isError ? (
          <Alert
            showIcon
            type="error"
            message="通知加载失败"
            action={<Button onClick={() => notifications.refetch()}>重试</Button>}
          />
        ) : notifications.data?.length ? (
          <List
            dataSource={notifications.data}
            renderItem={(notification) => {
              const target = notificationTarget(notification)
              return (
                <List.Item
                  className={notification.is_read ? 'notification-item' : 'notification-item notification-item-unread'}
                  onClick={() => void openNotification(notification)}
                  actions={[
                    notification.is_read
                      ? <Typography.Text key="status" type="secondary">已读</Typography.Text>
                      : <Badge key="status" status="processing" text="未读" />,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space wrap>
                        <Typography.Text strong={!notification.is_read}>{notification.title}</Typography.Text>
                        <NotificationTypeTag type={notification.type} />
                      </Space>
                    }
                    description={
                      <Flex vertical gap={6}>
                        <Typography.Text type="secondary">
                          {formatNotificationContent(notification.content)}
                        </Typography.Text>
                        <Typography.Text type="secondary" className="notification-time">
                          {formatNotificationDateTime(notification.created_at)}
                          {target ? ' · 点击查看详情' : ''}
                        </Typography.Text>
                      </Flex>
                    }
                  />
                </List.Item>
              )
            }}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无通知" />
        )}
      </Card>
    </Flex>
  )
}
