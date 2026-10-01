import {useEffect,useState,type FormEvent} from 'react'
import {useQuery} from '@tanstack/react-query'
import {ChevronRight,MapPin,Plus,Route,Search} from 'lucide-react'
import {Link,useSearchParams} from 'react-router-dom'
import {Can} from '../../../shared/permissions'
import {EmptyState} from '../../../components/ui/EmptyState'
import {listAirports,getDictionary} from '../../airports/airports.api'
import {listRunways} from '../runways.api'

export function RunwaysPage(){
 const [params,setParams]=useSearchParams();const initial=Number(params.get('air_id'))||0;const [airId,setAirId]=useState(initial);const [draft,setDraft]=useState('');const [search,setSearch]=useState('');const [status,setStatus]=useState(0)
 const airports=useQuery({queryKey:['airports','runway-selector'],queryFn:()=>listAirports({page:1,page_size:100})});const statuses=useQuery({queryKey:['dic','statuses'],queryFn:()=>getDictionary('statuses')})
 useEffect(()=>{if(!airId&&airports.data?.items[0])setAirId(airports.data.items[0].air_id)},[airId,airports.data])
 const runways=useQuery({queryKey:['runways',airId,search,status],queryFn:()=>listRunways(airId,{search:search||undefined,status_id:status||undefined}),enabled:airId>0})
 const submit=(e:FormEvent)=>{e.preventDefault();setSearch(draft.trim())}
 return <div className="runways-page"><div className="module-page-head"><div><span><small>Uçuş əməliyyatları</small><h1>Runway idarəetməsi</h1><p>Zolaqları, istiqamətləri və əməliyyat məsafələrini idarə edin.</p></span></div><Can permission="edit">{airId?<Link className="primary-action" to={`/runways/new?air_id=${airId}`}><Plus/>Yeni runway</Link>:null}</Can></div>
 <section className="runway-toolbar"><label><span>Hava limanı</span><select value={airId} onChange={e=>{const id=Number(e.target.value);setAirId(id);setParams(id?{air_id:String(id)}:{})}}><option value={0}>Hava limanı seçin</option>{airports.data?.items.map(a=><option key={a.air_id} value={a.air_id}>{a.icao_code} — {a.aze_name}</option>)}</select></label><form onSubmit={submit}><Search/><input value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Ad və ya designator..."/><button>Axtar</button></form><label><span>Status</span><select value={status} onChange={e=>setStatus(Number(e.target.value))}><option value={0}>Hamısı</option>{statuses.data?.items.map(x=><option key={x.id} value={x.id}>{x.aze_name}</option>)}</select></label></section>
 <section className="runway-list-card"><header><div><Route/><span><b>{runways.data?.total??0} runway</b><small>Seçilmiş hava limanında</small></span></div></header>{!airId?<EmptyState icon={MapPin} title="Hava limanı seçilməyib" description="Runway-ləri görmək üçün hava limanı seçin."/>:runways.isLoading?<div className="runway-loading">Məlumatlar yüklənir...</div>:runways.data?.items.length?<div className="runway-grid">{runways.data.items.map(r=><Link key={r.run_id} to={`/runways/${r.run_id}`}><div className="runway-designator"><Route/><b>{r.designator_1}</b><i/><b>{r.designator_2}</b></div><h3>{r.aze_name}</h3><p>{r.eng_name}</p><dl><div><dt>Uzunluq</dt><dd>{Number(r.length_m).toLocaleString('az-AZ')} m</dd></div><div><dt>En</dt><dd>{Number(r.width_m)} m</dd></div></dl><footer><span className={`data-status ${r.status.toLowerCase()==='active'?'active':''}`}>{r.status}</span><small>Ətraflı bax <ChevronRight/></small></footer></Link>)}</div>:<EmptyState icon={Route} title="Runway tapılmadı" description="Bu hava limanı üçün ilk runway-i yaradın."/>}</section></div>
}
