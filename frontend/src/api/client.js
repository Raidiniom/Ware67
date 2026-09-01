import axios from "axios"

const client = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
})

client.interceptors.request.use((config) => {
    const token = localStorage.getItem("ware67_token")
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

export default client;