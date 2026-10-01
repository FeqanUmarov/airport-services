import {create} from 'zustand'
import {getCurrentUser,login as loginRequest,logout as logoutRequest} from './auth.api'
import {clearSession,getRefreshToken,getSession,saveSession} from './auth-storage'
import type {CurrentUser,LoginCredentials} from './auth.types'

type AuthState={user:CurrentUser|null;status:'loading'|'authenticated'|'anonymous';error:string|null;initialize:()=>Promise<void>;login:(data:LoginCredentials)=>Promise<void>;logout:()=>Promise<void>}

export const useAuthStore=create<AuthState>((set)=>({
 user:null,status:'loading',error:null,
 initialize:async()=>{
  if(!getSession()){set({status:'anonymous',user:null});return}
  try{set({user:await getCurrentUser(),status:'authenticated',error:null})}
  catch{clearSession();set({user:null,status:'anonymous'})}
 },
 login:async(credentials)=>{
  set({status:'loading',error:null})
  try{const tokens=await loginRequest(credentials);saveSession(tokens,credentials.remember);const user=await getCurrentUser();set({user,status:'authenticated'})}
  catch{clearSession();set({status:'anonymous',error:'İstifadəçi adı və ya şifrə yanlışdır.'});throw new Error('login-failed')}
 },
 logout:async()=>{
  const refreshToken=getRefreshToken();clearSession();set({user:null,status:'anonymous',error:null})
  if(refreshToken)try{await logoutRequest(refreshToken)}catch{/* Local session is already closed. */}
 }
}))
