import {useState} from 'react'
import {Bell,ChevronDown,Command,LogOut,Menu,Moon,Plane,Search,Sun,X} from 'lucide-react'
import {NavLink,Outlet,useLocation} from 'react-router-dom'
import {appRoutes,routeByPath} from '../app/routes'
import {useConfirm} from '../components/ui/ConfirmDialog'
import {useAuthStore} from '../features/auth/auth.store'
import {useThemeStore,resolveTheme} from '../features/theme/theme.store'

const groupNames={main:'Əsas',management:'İdarəetmə',system:'Sistem'}
export function AppLayout(){
 const [mobileOpen,setMobileOpen]=useState(false);const [profileOpen,setProfileOpen]=useState(false)
 const location=useLocation();const current=routeByPath(location.pathname)
 const {user,logout}=useAuthStore();const {mode,toggle}=useThemeStore();const confirm=useConfirm()
 const allowed=appRoutes.filter(route=>!route.roles?.length||route.roles.some(role=>user?.roles.includes(role)))
 const signOut=async()=>{if(await confirm({title:'Hesabdan çıxış',message:'Cari sessiyanı bitirmək istədiyinizə əminsiniz?',confirmLabel:'Hesabdan çıx',danger:true}))await logout()}
 return <div className="app-shell">
  {mobileOpen&&<button className="nav-scrim" aria-label="Menyunu bağla" onClick={()=>setMobileOpen(false)}/>}
  <aside className={`app-sidebar ${mobileOpen?'is-open':''}`}>
   <div className="sidebar-brand"><span><Plane/></span><div><b>Airport GIS</b><small>Məkan təhlükəsizliyi platforması</small></div><button onClick={()=>setMobileOpen(false)}><X/></button></div>
   <nav>{(['main','management','system'] as const).map(group=><div className="nav-group" key={group}><p>{groupNames[group]}</p>{allowed.filter(route=>route.group===group).map(route=><NavLink end={route.path==='/'} to={route.path} key={route.path} onClick={()=>setMobileOpen(false)}><route.icon/><span>{route.label}</span></NavLink>)}</div>)}</nav>
   <div className="sidebar-foot"><span className="live-dot"/> Sistem aktivdir <small>v1.0.0</small></div>
  </aside>
  <section className="app-workspace">
   <header className="app-header"><button className="mobile-menu" onClick={()=>setMobileOpen(true)}><Menu/></button><div className="page-heading"><span>{current.label}</span><small>{current.description}</small></div><div className="header-search"><Search/><input placeholder="Sistemdə axtar..."/><kbd><Command/> K</kbd></div><button className="header-icon theme-toggle" onClick={toggle} title="Görünüşü dəyiş"><Sun className={resolveTheme(mode)==='light'?'visible':''}/><Moon className={resolveTheme(mode)==='dark'?'visible':''}/></button><button className="header-icon notification-button"><Bell/><i>2</i></button><div className="profile-wrap"><button className="profile-trigger" onClick={()=>setProfileOpen(value=>!value)}><span>{initials(user?.first_name,user?.last_name,user?.username)}</span><div><b>{displayName(user?.first_name,user?.last_name,user?.username)}</b><small>{user?.roles.join(', ')}</small></div><ChevronDown/></button>{profileOpen&&<div className="profile-menu"><div><b>{displayName(user?.first_name,user?.last_name,user?.username)}</b><small>{user?.email}</small></div><button onClick={()=>void signOut()}><LogOut/>Hesabdan çıx</button></div>}</div></header>
   <main className="app-content"><Outlet/></main>
  </section>
 </div>
}
const displayName=(first?:string,last?:string,username?:string)=>`${first??''} ${last??''}`.trim()||username||'İstifadəçi'
const initials=(first?:string,last?:string,username?:string)=>(`${first?.[0]??''}${last?.[0]??''}`||username?.slice(0,2)||'İ').toUpperCase()
