import { useLayoutEffect, type PropsWithChildren } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp, ConfigProvider, theme as antTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { queryClient } from './query-client'
import { SessionExpiryWatcher } from '../features/auth/components/SessionExpiryWatcher'
import { usePreferencesStore } from '../features/settings/store'

const initialTheme = usePreferencesStore.getState().theme
document.documentElement.dataset.theme = initialTheme
document.documentElement.style.colorScheme = initialTheme

interface ThemeScopeProps extends PropsWithChildren {
  preference: 'light' | 'dark'
}

function ThemeScope({ children, preference }: ThemeScopeProps) {
  const { token } = antTheme.useToken()

  useLayoutEffect(() => {
    const root = document.documentElement
    const variables = {
      '--app-color-primary': token.colorPrimary,
      '--app-color-primary-bg': token.colorPrimaryBg,
      '--app-color-primary-border': token.colorPrimaryBorder,
      '--app-color-text': token.colorText,
      '--app-color-text-secondary': token.colorTextSecondary,
      '--app-color-text-tertiary': token.colorTextTertiary,
      '--app-color-bg-layout': token.colorBgLayout,
      '--app-color-bg-container': token.colorBgContainer,
      '--app-color-bg-elevated': token.colorBgElevated,
      '--app-color-border': token.colorBorder,
      '--app-color-border-secondary': token.colorBorderSecondary,
      '--app-color-fill-secondary': token.colorFillSecondary,
      '--app-color-fill-tertiary': token.colorFillTertiary,
      '--app-color-fill-quaternary': token.colorFillQuaternary,
      '--app-control-item-bg-hover': token.controlItemBgHover,
      '--app-color-error': token.colorError,
      '--app-color-error-bg': token.colorErrorBg,
      '--app-color-error-border': token.colorErrorBorder,
      '--app-box-shadow-tertiary': token.boxShadowTertiary,
    }

    root.dataset.theme = preference
    root.style.colorScheme = preference
    for (const [name, value] of Object.entries(variables)) {
      root.style.setProperty(name, value)
    }
  }, [preference, token])

  return (
    <AntApp className={`theme-${preference}`}>
      <SessionExpiryWatcher />
      {children}
    </AntApp>
  )
}

export function AppProviders({ children }: PropsWithChildren) {
  const theme = usePreferencesStore((state) => state.theme)

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme === 'dark' ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
          token: {
            colorPrimary: '#1677ff',
            borderRadius: 10,
            fontFamily:
              "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          },
        }}
      >
        <ThemeScope preference={theme}>{children}</ThemeScope>
      </ConfigProvider>
    </QueryClientProvider>
  )
}
