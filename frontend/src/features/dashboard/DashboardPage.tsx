import {useState} from 'react'
import {useQuery} from '@tanstack/react-query'
import {Activity,ArrowRight,BookOpen,Building2,CalendarDays,CheckCircle2,Database,Layers3,MapPinned,Plane,RadioTower,RefreshCw,Route,Server,ShieldAlert,Sparkles} from 'lucide-react'
import {Link} from 'react-router-dom'
import {getHealth} from '../../api/health.api'
import {EmptyState} from '../../components/ui/EmptyState'
import {ErrorState} from '../../components/ui/ErrorState'
import {useAuthStore} from '../auth/auth.store'
import {getDashboardOverview} from './dashboard.api'
import type {DashboardObstacle,DashboardTotals,DashboardViolation} from './dashboard.types'

const totalCards:[keyof DashboardTotals,string,typeof Building2,string,string][]=[
 ['airports','Hava limanları',Building2,'/airports','blue'],['runways','Runway-lər',Route,'/runways','violet'],['ols_surfaces','OLS səthləri',Layers3,'/ols','cyan'],
 ['obstacles','Maneələr',RadioTower,'/obstacles','amber'],['violations','Pozuntular',ShieldAlert,'/violations','rose'],['standards','Standartlar',BookOpen,'/standards','green'],
]
const surfaceNames:Record<string,string>={INNER_HORIZONTAL:'Daxili horizontal',CONICAL:'Konik',APPROACH:'Yanaşma',TAKE_OFF_CLIMB:'Uçuşa qalxma',TRANSITIONAL:'Keçid'}

export function DashboardPage(){
 const user=useAuthStore(state=>state.user);const [activityTab,setActivityTab]=useState<'obstacles'|'violations'>('obstacles')
 const dashboard=useQuery({queryKey:['dashboard','overview'],queryFn:getDashboardOverview,refetchInterval:60_000})
 const health=useQuery({queryKey:['health'],queryFn:getHealth,refetchInterval:30_000})
 const refresh=()=>void Promise.all([dashboard.refetch(),health.refetch()])
 if(dashboard.isLoading)return <DashboardSkeleton/>
 if(dashboard.isError)return <ErrorState title="Dashboard məlumatları yüklənmədi" description="Backend-dən ümumi göstəriciləri almaq mümkün olmadı." onRetry={()=>void dashboard.refetch()}/>
 const data=dashboard.data!
 return <div className="dashboard-page dashboard-complete">
  <section className="dashboard-top"><div><span><Sparkles/> Canlı idarəetmə paneli</span><h1>Salam, {user?.first_name||user?.username}</h1><p>Airport GIS məlumatlarının cari vəziyyəti və son əməliyyatlar.</p></div><div className="dashboard-top-actions"><small><CalendarDays/> {formatDate(data.generated_at)}</small><button onClick={refresh} disabled={dashboard.isFetching}><RefreshCw className={dashboard.isFetching?'spinning':''}/> Yenilə</button><Link to="/map"><MapPinned/> Xəritəni aç</Link></div></section>
  <section className="dashboard-stat-grid">{totalCards.map(([key,label,Icon,to,tone])=><Link to={to} className={`dashboard-stat ${tone}`} key={key}><span><Icon/></span><div><small>{label}</small><strong>{data.totals[key].toLocaleString('az-AZ')}</strong></div><ArrowRight/></Link>)}</section>
  <section className="dashboard-main-grid">
   <article className="dashboard-card airport-overview"><CardHeader eyebrow="Əhatə dairəsi" title="Hava limanlarına ümumi baxış" action={<Link to="/airports">Hamısına bax <ArrowRight/></Link>}/>{data.airports.length?<div className="airport-dashboard-table"><div className="airport-table-head"><span>Hava limanı</span><span>Runway</span><span>OLS</span><span>Maneə</span><span>Pozuntu</span><span>Status</span></div>{data.airports.map(airport=><Link to={`/airports/${airport.air_id}`} className="airport-table-row" key={airport.air_id}><div><b>{airport.icao_code}</b><span><strong>{airport.name}</strong><small>{airport.city}</small></span></div><em>{airport.runway_count}</em><em>{airport.ols_surface_count}</em><em>{airport.obstacle_count}</em><em className={airport.violation_count?'has-alert':''}>{airport.violation_count}</em><Status value={airport.status}/></Link>)}</div>:<EmptyState title="Hava limanı yoxdur" description="Sistemə ilk hava limanı əlavə edildikdən sonra burada göstəriləcək." icon={Building2}/>}</article>
   <article className="dashboard-card distribution-card"><CardHeader eyebrow="Məkan modeli" title="OLS səthlərinin bölgüsü" action={<Link to="/ols">Detallar</Link>}/><Distribution data={data.ols_by_type}/></article>
  </section>
  <section className="dashboard-bottom-grid">
   <article className="dashboard-card activity-card"><div className="activity-header"><div><span>Son məlumatlar</span><h2>Operativ fəaliyyət</h2></div><div><button className={activityTab==='obstacles'?'active':''} onClick={()=>setActivityTab('obstacles')}>Maneələr</button><button className={activityTab==='violations'?'active':''} onClick={()=>setActivityTab('violations')}>Pozuntular</button></div></div>{activityTab==='obstacles'?<ObstacleActivity items={data.recent_obstacles}/>:<ViolationActivity items={data.recent_violations}/>}</article>
   <article className="dashboard-card health-card"><CardHeader eyebrow="İnfrastruktur" title="Sistem vəziyyəti"/><div className="dashboard-health-list"><HealthItem icon={Server} label="Backend API" detail={health.isSuccess?'Sorğular qəbul edilir':'Bağlantı yoxlanılır'} online={health.isSuccess}/><HealthItem icon={Database} label="PostgreSQL / PostGIS" detail={health.data?.database==='connected'?'Database qoşulub':'Bağlantı yoxlanılır'} online={health.isSuccess}/><HealthItem icon={CheckCircle2} label="Autentifikasiya" detail="JWT sessiyası aktivdir" online/><HealthItem icon={Activity} label="Frontend" detail="Production build işləyir" online/></div><div className="health-footer"><span className={health.isSuccess?'online':''}/><p><b>{health.isSuccess?'Bütün sistemlər işləyir':'Sistem yoxlanılır'}</b><small>Avtomatik olaraq hər 30 saniyədə yenilənir</small></p></div></article>
  </section>
 </div>
}

function CardHeader({eyebrow,title,action}:{eyebrow:string;title:string;action?:React.ReactNode}){return <header className="dashboard-card-header"><div><span>{eyebrow}</span><h2>{title}</h2></div>{action}</header>}
function Status({value}:{value:string}){const active=['aktiv','active'].includes(value.toLowerCase());return <span className={`data-status ${active?'active':''}`}>{value}</span>}
function Distribution({data}:{data:Record<string,number>}){const entries=Object.entries(data);const total=entries.reduce((sum,[,count])=>sum+count,0);if(!total)return <EmptyState title="OLS səthi yoxdur" description="Generasiya olunmuş səthlərin bölgüsü burada göstəriləcək." icon={Layers3}/>;const max=Math.max(...entries.map(([,count])=>count));return <div className="distribution"><div className="distribution-total"><span><Plane/></span><strong>{total}</strong><small>Ümumi səth</small></div><div className="distribution-bars">{entries.map(([type,count],index)=><div key={type}><label><span><i className={`surface-color color-${index%5}`}/>{surfaceNames[type]??type.replaceAll('_',' ')}</span><b>{count}</b></label><span><i className={`color-${index%5}`} style={{width:`${count/max*100}%`}}/></span></div>)}</div></div>}
function ObstacleActivity({items}:{items:DashboardObstacle[]}){if(!items.length)return <EmptyState title="Maneə məlumatı yoxdur" description="Yeni maneələr burada tarix sırası ilə görünəcək." icon={RadioTower}/>;return <div className="activity-list">{items.map(item=><Link to={`/obstacles?id=${item.obstacle_id}`} key={item.obstacle_id}><span className="activity-icon obstacle"><RadioTower/></span><div><b>{item.name||`Maneə #${item.obstacle_id}`}</b><small>{item.airport_name} · {item.obstacle_type}</small></div><div className="activity-value"><strong>{item.top_elevation_m?`${Number(item.top_elevation_m).toFixed(1)} m`:'—'}</strong><small>{relativeDate(item.created_date)}</small></div><Status value={item.status}/></Link>)}</div>}
function ViolationActivity({items}:{items:DashboardViolation[]}){if(!items.length)return <EmptyState title="Pozuntu yoxdur" description="Aşkarlanan OLS pozuntuları burada göstəriləcək." icon={ShieldAlert}/>;return <div className="activity-list">{items.map(item=><Link to={`/violations?id=${item.violation_id}`} key={item.violation_id}><span className="activity-icon violation"><ShieldAlert/></span><div><b>{item.obstacle_name||`Maneə #${item.obstacle_id}`}</b><small>{surfaceNames[item.surface_type]??item.surface_type}</small></div><div className="activity-value danger"><strong>{item.penetration_m?`+${Number(item.penetration_m).toFixed(2)} m`:'—'}</strong><small>{relativeDate(item.checked_date)}</small></div><Status value={item.status}/></Link>)}</div>}
function HealthItem({icon:Icon,label,detail,online}:{icon:typeof Server;label:string;detail:string;online:boolean}){return <div><span><Icon/></span><p><b>{label}</b><small>{detail}</small></p><i className={online?'online':''}/></div>}
function DashboardSkeleton(){return <div className="dashboard-skeleton"><div className="skeleton hero"/><div className="skeleton-row">{Array.from({length:6},(_,i)=><div className="skeleton" key={i}/>)}</div><div className="skeleton-panels"><div className="skeleton"/><div className="skeleton"/></div></div>}
const formatDate=(value:string)=>new Intl.DateTimeFormat('az-AZ',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(value))
function relativeDate(value:string){const minutes=Math.max(0,Math.floor((Date.now()-new Date(value).getTime())/60000));if(minutes<1)return 'İndi';if(minutes<60)return `${minutes} dəq əvvəl`;const hours=Math.floor(minutes/60);if(hours<24)return `${hours} saat əvvəl`;return `${Math.floor(hours/24)} gün əvvəl`}
