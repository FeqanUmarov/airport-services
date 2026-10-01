import {apiClient} from '../../api/client'
import type {CurrentUser,LoginCredentials,TokenPair} from './auth.types'

export async function login({username,password}:LoginCredentials){
 const body=new URLSearchParams({username,password})
 return (await apiClient.post<TokenPair>('/auth/login',body,{headers:{'Content-Type':'application/x-www-form-urlencoded'}})).data
}
export async function getCurrentUser(){return (await apiClient.get<CurrentUser>('/auth/me')).data}
export async function logout(refreshToken:string){await apiClient.post('/auth/logout',{refresh_token:refreshToken})}
