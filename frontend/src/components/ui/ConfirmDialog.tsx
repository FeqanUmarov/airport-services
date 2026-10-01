import {createContext,useCallback,useContext,useState} from 'react'
import {AlertCircle} from 'lucide-react'

type ConfirmOptions={title:string;message:string;confirmLabel?:string;cancelLabel?:string;danger?:boolean}
type Pending=ConfirmOptions&{resolve:(value:boolean)=>void}
const ConfirmContext=createContext<(options:ConfirmOptions)=>Promise<boolean>>(()=>Promise.resolve(false))
export const useConfirm=()=>useContext(ConfirmContext)
export function ConfirmDialogProvider({children}:{children:React.ReactNode}){
 const [pending,setPending]=useState<Pending|null>(null)
 const confirm=useCallback((options:ConfirmOptions)=>new Promise<boolean>(resolve=>setPending({...options,resolve})),[])
 const finish=(answer:boolean)=>{pending?.resolve(answer);setPending(null)}
 return <ConfirmContext.Provider value={confirm}>{children}{pending&&<div className="dialog-backdrop" role="presentation" onMouseDown={()=>finish(false)}><div className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" onMouseDown={event=>event.stopPropagation()}><span className={pending.danger?'danger':''}><AlertCircle/></span><h2 id="confirm-title">{pending.title}</h2><p>{pending.message}</p><footer><button onClick={()=>finish(false)}>{pending.cancelLabel??'İmtina et'}</button><button className={pending.danger?'danger':''} onClick={()=>finish(true)}>{pending.confirmLabel??'Təsdiqlə'}</button></footer></div></div>}</ConfirmContext.Provider>
}
