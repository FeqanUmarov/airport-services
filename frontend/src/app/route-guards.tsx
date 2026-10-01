import {Navigate,Outlet,useLocation} from 'react-router-dom'
import {LoadingScreen} from '../components/ui/LoadingScreen'
import {useAuthStore} from '../features/auth/auth.store'
import type {AppRole} from './routes'

export function ProtectedRoute(){
 const status=useAuthStore(state=>state.status);const location=useLocation()
 if(status==='loading')return <LoadingScreen label="Sessiya yoxlanılır..."/>
 if(status==='anonymous')return <Navigate to="/login" state={{from:location.pathname}} replace/>
 return <Outlet/>
}
export function RoleRoute({roles,children}:{roles?:AppRole[];children:React.ReactNode}){
 const userRoles=useAuthStore(state=>state.user?.roles??[])
 if(roles?.length&&!roles.some(role=>userRoles.includes(role)))return <Navigate to="/" replace/>
 return children
}
