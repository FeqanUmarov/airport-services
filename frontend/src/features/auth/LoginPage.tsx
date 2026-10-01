import {useState,type FormEvent} from 'react'
import {ArrowRight,Eye,EyeOff,LockKeyhole,Moon,Plane,Sun,UserRound} from 'lucide-react'
import {Navigate,useLocation,useNavigate} from 'react-router-dom'
import {useAuthStore} from './auth.store'
import {resolveTheme,useThemeStore} from '../theme/theme.store'

export function LoginPage(){
 const [username,setUsername]=useState('');const [password,setPassword]=useState('');const [remember,setRemember]=useState(false);const [showPassword,setShowPassword]=useState(false)
 const {login,status,error}=useAuthStore();const navigate=useNavigate();const location=useLocation()
 const {mode,toggle}=useThemeStore();const activeTheme=resolveTheme(mode)
 if(status==='authenticated')return <Navigate to="/" replace/>
 const submit=async(e:FormEvent)=>{e.preventDefault();try{await login({username,password,remember});navigate((location.state as {from?:string}|null)?.from??'/',{replace:true})}catch{/* Error is rendered by the store. */}}
 return <main className="login-page">
  <section className="login-visual" aria-label="Airport GIS təqdimat şəkli"><img src="/images/airport-gis-login-az-v2.png" alt="Airport GIS — Zəngilan Beynəlxalq Hava Limanı və OLS səthləri"/></section>
  <section className="login-panel">
   <div className="login-actions"><button onClick={toggle} aria-label="Görünüşü dəyiş">{activeTheme==='dark'?<Sun/>:<Moon/>}</button><div className="language">AZ <span>⌄</span></div></div>
   <form className="login-form" onSubmit={submit}>
    <div className="mobile-login-brand"><Plane/><strong>Airport GIS</strong></div>
    <h2>Yenidən xoş gəlmisiniz</h2><p className="login-subtitle">Airport GIS hesabınıza daxil olun</p>
    <label htmlFor="username">İstifadəçi adı</label><div className="field"><UserRound/><input id="username" name="username" autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} placeholder="İstifadəçi adınızı daxil edin" required autoFocus/></div>
    <label htmlFor="password">Şifrə</label><div className="field"><LockKeyhole/><input id="password" name="password" type={showPassword?'text':'password'} autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Şifrənizi daxil edin" required/><button type="button" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?'Şifrəni gizlət':'Şifrəni göstər'}>{showPassword?<EyeOff/>:<Eye/>}</button></div>
    <div className="login-options"><label><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/> <span>Məni xatırla</span></label><span className="forgot" title="Şifrə bərpası növbəti mərhələdə əlavə ediləcək">Şifrəni unutmusunuz?</span></div>
    {error&&<div className="login-error" role="alert">{error}</div>}
    <button className="login-submit" disabled={status==='loading'}>{status==='loading'?'Yoxlanılır...':<>Daxil ol <ArrowRight/></>}</button>
   </form>
   <div className="airport-line"><Plane/><span/><i/><b/></div><small className="login-version">Versiya 1.0.0</small>
 </section>
 </main>
}
