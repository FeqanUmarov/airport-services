import {useEffect} from 'react'
import {resolveTheme,useThemeStore} from './theme.store'

export function ThemeInitializer(){
 const mode=useThemeStore(state=>state.mode)
 useEffect(()=>{
  const media=window.matchMedia('(prefers-color-scheme: dark)')
  const apply=()=>{const theme=resolveTheme(mode);document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme}
  apply();media.addEventListener('change',apply);return()=>media.removeEventListener('change',apply)
 },[mode])
 return null
}
