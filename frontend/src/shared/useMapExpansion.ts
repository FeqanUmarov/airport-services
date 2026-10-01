import {useEffect,useState,type RefObject} from 'react'
import type Map from 'ol/Map'

export function useMapExpansion(mapRef:RefObject<Map|null>){
 const [expanded,setExpanded]=useState(false)
 useEffect(()=>{
  const previousOverflow=document.body.style.overflow
  if(expanded)document.body.style.overflow='hidden'
  const close=(event:KeyboardEvent)=>{if(event.key==='Escape')setExpanded(false)}
  window.addEventListener('keydown',close)
  const frame=requestAnimationFrame(()=>mapRef.current?.updateSize())
  const timer=window.setTimeout(()=>mapRef.current?.updateSize(),220)
  return()=>{cancelAnimationFrame(frame);window.clearTimeout(timer);window.removeEventListener('keydown',close);if(expanded)document.body.style.overflow=previousOverflow}
 },[expanded,mapRef])
 return {expanded,toggleExpanded:()=>setExpanded(value=>!value)}
}
