import type {AppRole} from '../app/routes'
import {useAuthStore} from '../features/auth/auth.store'

export type Permission='view'|'edit'|'manage'
const permissions:Record<AppRole,Permission[]>={ADMIN:['view','edit','manage'],EDITOR:['view','edit'],VIEWER:['view']}
export const hasPermission=(roles:string[],permission:Permission)=>roles.some(role=>permissions[role as AppRole]?.includes(permission))
export const usePermission=(permission:Permission)=>useAuthStore(state=>hasPermission(state.user?.roles??[],permission))
export function Can({permission,children,fallback=null}:{permission:Permission;children:React.ReactNode;fallback?:React.ReactNode}){return usePermission(permission)?children:fallback}
