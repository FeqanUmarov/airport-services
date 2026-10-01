import type {TokenPair} from './auth.types'

const SESSION_KEY='airport_gis_auth'
const REMEMBER_KEY='airport_gis_remember'

function storage(){return localStorage.getItem(REMEMBER_KEY)==='true'?localStorage:sessionStorage}
export function getSession():TokenPair|null{
 const raw=sessionStorage.getItem(SESSION_KEY)??localStorage.getItem(SESSION_KEY)
 if(!raw)return null
 try{return JSON.parse(raw) as TokenPair}catch{clearSession();return null}
}
export function saveSession(tokens:TokenPair,remember?:boolean){
 const shouldRemember=remember??localStorage.getItem(REMEMBER_KEY)==='true'
 localStorage.removeItem(SESSION_KEY);sessionStorage.removeItem(SESSION_KEY)
 if(shouldRemember){localStorage.setItem(REMEMBER_KEY,'true');localStorage.setItem(SESSION_KEY,JSON.stringify(tokens))}
 else{localStorage.removeItem(REMEMBER_KEY);sessionStorage.setItem(SESSION_KEY,JSON.stringify(tokens))}
}
export function clearSession(){localStorage.removeItem(SESSION_KEY);localStorage.removeItem(REMEMBER_KEY);sessionStorage.removeItem(SESSION_KEY)}
export function getAccessToken(){return getSession()?.access_token??null}
export function getRefreshToken(){return getSession()?.refresh_token??null}
