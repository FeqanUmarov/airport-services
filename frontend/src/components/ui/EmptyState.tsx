import {Inbox,type LucideIcon} from 'lucide-react'
export function EmptyState({title,description,icon:Icon=Inbox,action}:{title:string;description:string;icon?:LucideIcon;action?:React.ReactNode}){return <div className="ui-empty-state"><span><Icon/></span><h3>{title}</h3><p>{description}</p>{action}</div>}
