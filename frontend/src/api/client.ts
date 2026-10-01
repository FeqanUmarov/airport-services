import axios, {AxiosError, type InternalAxiosRequestConfig} from 'axios'
import {clearSession, getAccessToken, getRefreshToken, saveSession} from '../features/auth/auth-storage'

export const apiClient=axios.create({baseURL:import.meta.env.VITE_API_URL??'/api/v1',timeout:15000})

type RetryableConfig=InternalAxiosRequestConfig&{_retry?:boolean}
let refreshRequest:Promise<string>|null=null

apiClient.interceptors.request.use((config)=>{
 const token=getAccessToken()
 if(token) config.headers.Authorization=`Bearer ${token}`
 return config
})

apiClient.interceptors.response.use(
 response=>response,
 async(error:AxiosError)=>{
  const original=error.config as RetryableConfig|undefined
  const refreshToken=getRefreshToken()
  const isAuthRequest=original?.url?.includes('/auth/login')||original?.url?.includes('/auth/refresh')
  if(error.response?.status!==401||!original||original._retry||!refreshToken||isAuthRequest) return Promise.reject(error)
  original._retry=true
  refreshRequest??=axios.post(`${apiClient.defaults.baseURL}/auth/refresh`,{refresh_token:refreshToken})
   .then(({data})=>{saveSession(data);return data.access_token as string})
   .catch(refreshError=>{clearSession();window.dispatchEvent(new Event('auth:expired'));throw refreshError})
   .finally(()=>{refreshRequest=null})
  const accessToken=await refreshRequest
  original.headers.Authorization=`Bearer ${accessToken}`
  return apiClient(original)
 }
)
