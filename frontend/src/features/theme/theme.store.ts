import {create} from 'zustand'
import {persist} from 'zustand/middleware'

export type ThemeMode='light'|'dark'|'system'
type ThemeState={mode:ThemeMode;setMode:(mode:ThemeMode)=>void;toggle:()=>void}
const systemDark=()=>window.matchMedia?.('(prefers-color-scheme: dark)').matches??false
export const resolveTheme=(mode:ThemeMode):'light'|'dark'=>mode==='system'?(systemDark()?'dark':'light'):mode
export const useThemeStore=create<ThemeState>()(persist((set,get)=>({
 mode:'system',setMode:mode=>set({mode}),toggle:()=>set({mode:resolveTheme(get().mode)==='dark'?'light':'dark'})
}),{name:'airport-gis-theme'}))
