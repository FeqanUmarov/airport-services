import {lazy,Suspense,useEffect} from 'react'
import {Navigate,Route,Routes} from 'react-router-dom'
import {AppErrorBoundary} from '../components/ui/AppErrorBoundary'
import {ConfirmDialogProvider} from '../components/ui/ConfirmDialog'
import {ToastViewport} from '../components/ui/ToastViewport'
import {LoginPage} from '../features/auth/LoginPage'
import {useAuthStore} from '../features/auth/auth.store'
import {DashboardPage} from '../features/dashboard/DashboardPage'
import {PlaceholderPage} from '../features/dashboard/PlaceholderPage'
import {LoadingScreen} from '../components/ui/LoadingScreen'
import {ThemeInitializer} from '../features/theme/ThemeInitializer'
import {AppLayout} from '../layouts/AppLayout'
import {ProtectedRoute,RoleRoute} from './route-guards'
import {appRoutes} from './routes'

const AirportsPage=lazy(()=>import('../features/airports/pages/AirportsPage').then(module=>({default:module.AirportsPage})))
const AirportDetailPage=lazy(()=>import('../features/airports/pages/AirportDetailPage').then(module=>({default:module.AirportDetailPage})))
const AirportFormPage=lazy(()=>import('../features/airports/pages/AirportFormPage').then(module=>({default:module.AirportFormPage})))
const RunwaysPage=lazy(()=>import('../features/runways/pages/RunwaysPage').then(module=>({default:module.RunwaysPage})))
const RunwayDetailPage=lazy(()=>import('../features/runways/pages/RunwayDetailPage').then(module=>({default:module.RunwayDetailPage})))
const RunwayFormPage=lazy(()=>import('../features/runways/pages/RunwayFormPage').then(module=>({default:module.RunwayFormPage})))
const StandardsPage=lazy(()=>import('../features/standards/pages/StandardsPage').then(module=>({default:module.StandardsPage})))
const StandardDetailPage=lazy(()=>import('../features/standards/pages/StandardDetailPage').then(module=>({default:module.StandardDetailPage})))
const StandardFormPage=lazy(()=>import('../features/standards/pages/StandardFormPage').then(module=>({default:module.StandardFormPage})))
const MapPage=lazy(()=>import('../features/map/pages/MapPage').then(module=>({default:module.MapPage})))
const AutomaticOlsPage=lazy(()=>import('../features/ols/pages/AutomaticOlsPage').then(module=>({default:module.AutomaticOlsPage})))
const deferred=(page:React.ReactNode)=><Suspense fallback={<LoadingScreen label="Modul yüklənir..."/>}>{page}</Suspense>

export function RootApp(){
 const initialize=useAuthStore(state=>state.initialize)
 useEffect(()=>{
  void initialize()
  const expired=()=>void initialize()
  window.addEventListener('auth:expired',expired)
  return()=>window.removeEventListener('auth:expired',expired)
 },[initialize])
 return <AppErrorBoundary><ThemeInitializer/><ConfirmDialogProvider><Routes>
  <Route path="/login" element={<LoginPage/>}/>
  <Route element={<ProtectedRoute/>}><Route element={<AppLayout/>}>
   <Route index element={<DashboardPage/>}/>
   <Route path="airports" element={deferred(<AirportsPage/>)}/>
   <Route path="airports/new" element={<RoleRoute roles={['ADMIN','EDITOR']}>{deferred(<AirportFormPage/>)}</RoleRoute>}/>
   <Route path="airports/:airId" element={deferred(<AirportDetailPage/>)}/>
   <Route path="airports/:airId/edit" element={<RoleRoute roles={['ADMIN','EDITOR']}>{deferred(<AirportFormPage/>)}</RoleRoute>}/>
   <Route path="runways" element={deferred(<RunwaysPage/>)}/>
   <Route path="runways/new" element={<RoleRoute roles={['ADMIN','EDITOR']}>{deferred(<RunwayFormPage/>)}</RoleRoute>}/>
   <Route path="runways/:runId" element={deferred(<RunwayDetailPage/>)}/>
   <Route path="runways/:runId/edit" element={<RoleRoute roles={['ADMIN','EDITOR']}>{deferred(<RunwayFormPage/>)}</RoleRoute>}/>
   <Route path="standards" element={deferred(<StandardsPage/>)}/>
   <Route path="standards/new" element={<RoleRoute roles={['ADMIN','EDITOR']}>{deferred(<StandardFormPage/>)}</RoleRoute>}/>
   <Route path="standards/:standardId" element={deferred(<StandardDetailPage/>)}/>
   <Route path="standards/:standardId/edit" element={<RoleRoute roles={['ADMIN','EDITOR']}>{deferred(<StandardFormPage/>)}</RoleRoute>}/>
   <Route path="map" element={deferred(<MapPage/>)}/>
   <Route path="ols" element={deferred(<AutomaticOlsPage/>)}/>
   {appRoutes.filter(route=>route.path!=='/'&&route.path!=='/airports'&&route.path!=='/runways'&&route.path!=='/standards'&&route.path!=='/map'&&route.path!=='/ols').map(route=><Route key={route.path} path={route.path.slice(1)} element={<RoleRoute roles={route.roles}><PlaceholderPage route={route}/></RoleRoute>}/>) }
  </Route></Route>
  <Route path="*" element={<Navigate to="/" replace/>}/>
 </Routes><ToastViewport/></ConfirmDialogProvider></AppErrorBoundary>
}
