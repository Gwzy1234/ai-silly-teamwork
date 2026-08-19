import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

export type ThemePreference = 'light' | 'dark'
export type DashboardDeadlineHours = 24 | 48 | 72 | 168

interface PreferencesState {
  sidebarCollapsed: boolean
  theme: ThemePreference
  dashboardDeadlineHours: DashboardDeadlineHours
  setSidebarCollapsed: (collapsed: boolean) => void
  toggleSidebar: () => void
  setTheme: (theme: ThemePreference) => void
  setDashboardDeadlineHours: (hours: DashboardDeadlineHours) => void
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      theme: 'light',
      dashboardDeadlineHours: 72,
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setTheme: (theme) => set({ theme }),
      setDashboardDeadlineHours: (dashboardDeadlineHours) => set({ dashboardDeadlineHours }),
    }),
    {
      name: 'silly-teamwork-preferences',
      storage: createJSONStorage(() => localStorage),
    },
  ),
)
