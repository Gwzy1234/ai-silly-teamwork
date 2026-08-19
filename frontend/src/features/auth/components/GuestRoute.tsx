import { Button, Result, Spin } from 'antd'
import { Navigate, Outlet } from 'react-router-dom'
import { useCurrentUser } from '../hooks'
import { useAuthStore } from '../store'

export function GuestRoute() {
  const hasHydrated = useAuthStore((state) => state.hasHydrated)
  const sessionIsValid = useAuthStore((state) => state.hasValidSession())
  const currentUser = useCurrentUser()

  if (!hasHydrated) {
    return (
      <div className="screen-center">
        <Spin size="large" tip="正在恢复登录状态…" />
      </div>
    )
  }
  if (!sessionIsValid) {
    return <Outlet />
  }
  if (currentUser.isPending) {
    return (
      <div className="screen-center">
        <Spin size="large" tip="正在验证登录状态…" />
      </div>
    )
  }
  if (currentUser.isError || !currentUser.data) {
    return (
      <Result
        status="warning"
        title="暂时无法验证登录状态"
        subTitle="请检查网络连接后重试，或退出后重新登录。"
        extra={[
          <Button key="retry" type="primary" onClick={() => currentUser.refetch()}>
            重试
          </Button>,
          <Button key="logout" onClick={() => useAuthStore.getState().clearSession()}>
            退出登录
          </Button>,
        ]}
      />
    )
  }
  return <Navigate to="/dashboard" replace />
}
