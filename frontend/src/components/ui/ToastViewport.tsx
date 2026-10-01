import {AlertTriangle,CheckCircle2,Info,X,XCircle} from 'lucide-react'
import {useNotificationStore,type ToastKind} from '../../features/notifications/notification.store'
const icons:Record<ToastKind,typeof Info>={success:CheckCircle2,error:XCircle,warning:AlertTriangle,info:Info}
export function ToastViewport(){
 const {items,dismiss}=useNotificationStore()
 return <div className="toast-viewport" aria-live="polite">{items.map(item=>{const Icon=icons[item.kind];return <div className={`toast toast-${item.kind}`} key={item.id}><Icon/><div><b>{item.title}</b>{item.message&&<p>{item.message}</p>}</div><button onClick={()=>dismiss(item.id)} aria-label="Bildirişi bağla"><X/></button></div>})}</div>
}
