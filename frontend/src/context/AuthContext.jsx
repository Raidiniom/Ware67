import { createContext, useContext, useEffect, useState, useCallback } from "react"
import { login as loginRequest, getCurrentUser } from "../api/auth"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null)
    const [loading, setLoading] = useState(true)

    const loadUser = useCallback(async () => {
        const token = localStorage.getItem("ware67_token")
        if (!token) {
            setUser(null)
            setLoading(false)
            return
        }
        try {
            const currentUser = await getCurrentUser()
            setUser(currentUser)
        } catch {
            setUser(null)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        loadUser()
    }, [loadUser])

    const login = async (email, password) => {
        const tokens = await loginRequest(email, password)
        localStorage.setItem("ware67_token", tokens.access_token)
        localStorage.setItem("ware67_refresh_token", tokens.refresh_token)
        const currentUser = await getCurrentUser()
        setUser(currentUser)
        return currentUser
    }

    const logout = () => {
        localStorage.removeItem("ware67_token")
        localStorage.removeItem("ware67_refresh_token")
        setUser(null)
    }

    return (
        <AuthContext.Provider value={{ user, loading, login, logout, refreshUser: loadUser }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) {
        throw new Error("useAuth must be used within an AuthProvider")
    }
    return ctx
}
