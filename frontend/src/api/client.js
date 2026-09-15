import axios from "axios"

const client = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
})

client.interceptors.request.use((config) => {
    const token = localStorage.getItem("ware67_token")
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

// --- 401 -> refresh-token retry -----------------------------------------
//
// If a request comes back 401 (expired access token) we transparently try
// to exchange the stored refresh token for a new pair and replay the
// original request once. Concurrent 401s while a refresh is already in
// flight get queued and resolved together once the new token arrives.

let isRefreshing = false
let pendingQueue = []

function processQueue(error, token = null) {
    pendingQueue.forEach(({ resolve, reject }) => {
        if (error) reject(error)
        else resolve(token)
    })
    pendingQueue = []
}

client.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config
        const isAuthEndpoint =
            originalRequest?.url?.includes("/auth/login") ||
            originalRequest?.url?.includes("/auth/refresh") ||
            originalRequest?.url?.includes("/auth/register")

        if (error.response?.status !== 401 || originalRequest?._retry || isAuthEndpoint) {
            return Promise.reject(error)
        }

        const refreshToken = localStorage.getItem("ware67_refresh_token")
        if (!refreshToken) {
            return Promise.reject(error)
        }

        if (isRefreshing) {
            return new Promise((resolve, reject) => {
                pendingQueue.push({ resolve, reject })
            }).then((token) => {
                originalRequest.headers.Authorization = `Bearer ${token}`
                return client(originalRequest)
            })
        }

        originalRequest._retry = true
        isRefreshing = true

        try {
            const { data } = await axios.post(
                `${import.meta.env.VITE_API_BASE_URL}/auth/refresh`,
                { refresh_token: refreshToken }
            )
            localStorage.setItem("ware67_token", data.access_token)
            localStorage.setItem("ware67_refresh_token", data.refresh_token)
            processQueue(null, data.access_token)

            originalRequest.headers.Authorization = `Bearer ${data.access_token}`
            return client(originalRequest)
        } catch (refreshError) {
            processQueue(refreshError, null)
            localStorage.removeItem("ware67_token")
            localStorage.removeItem("ware67_refresh_token")
            if (typeof window !== "undefined") {
                window.location.href = "/login"
            }
            return Promise.reject(refreshError)
        } finally {
            isRefreshing = false
        }
    }
)

export default client
