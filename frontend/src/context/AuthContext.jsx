import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { setSessionExpiredHandler, tokenStore } from '../api/client'
import * as authApi from '../api/auth'
import { ADMIN_ROLES } from '../utils/constants'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // "đang kiểm tra token cũ" khác với "chưa đăng nhập" — nếu không phân biệt,
  // người dùng F5 sẽ thấy màn hình đăng nhập loé lên rồi mới vào được trang.
  const [isRestoring, setIsRestoring] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function restoreSession() {
      if (!tokenStore.getAccess()) {
        setIsRestoring(false)
        return
      }
      try {
        const profile = await authApi.fetchMe()
        if (!cancelled) setUser(profile)
      } catch {
        tokenStore.clear()
      } finally {
        if (!cancelled) setIsRestoring(false)
      }
    }

    restoreSession()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(() => setUser(null))
  }, [])

  const login = useCallback(async (email, password) => {
    const profile = await authApi.login(email, password)
    setUser(profile)
    return profile
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    const profile = await authApi.fetchMe()
    setUser(profile)
    return profile
  }, [])

  const value = useMemo(
    () => ({
      user,
      isRestoring,
      isAuthenticated: Boolean(user),
      isAdmin: user ? ADMIN_ROLES.includes(user.role) : false,
      login,
      logout,
      refreshUser,
      setUser,
    }),
    [user, isRestoring, login, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth phải nằm trong <AuthProvider>')
  return context
}
