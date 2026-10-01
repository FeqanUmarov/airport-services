import {create} from 'zustand'

export type ToastKind='success'|'error'|'info'|'warning'
export type Toast={id:string;title:string;message?:string;kind:ToastKind}
type ToastState={items:Toast[];notify:(toast:Omit<Toast,'id'>)=>void;dismiss:(id:string)=>void}
export const useNotificationStore=create<ToastState>(set=>({
 items:[],notify:toast=>{
  const id=crypto.randomUUID();set(state=>({items:[...state.items,{...toast,id}]}))
  window.setTimeout(()=>set(state=>({items:state.items.filter(item=>item.id!==id)})),4500)
 },dismiss:id=>set(state=>({items:state.items.filter(item=>item.id!==id)}))
}))
