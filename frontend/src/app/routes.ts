import {BookOpen,Building2,FileBarChart,LayoutDashboard,Layers3,Map,Mountain,RadioTower,Route,Settings,ShieldAlert,Users,type LucideIcon} from 'lucide-react'

export type AppRole='ADMIN'|'EDITOR'|'VIEWER'
export type AppRoute={path:string;label:string;description:string;icon:LucideIcon;group:'main'|'management'|'system';roles?:AppRole[]}

export const appRoutes:AppRoute[]=[
 {path:'/',label:'İdarə paneli',description:'Sistemə ümumi baxış',icon:LayoutDashboard,group:'main'},
 {path:'/airports',label:'Hava limanları',description:'Hava limanı məlumatlarının idarəsi',icon:Building2,group:'main'},
 {path:'/map',label:'Xəritə',description:'Məkan məlumatları və GIS alətləri',icon:Map,group:'main'},
 {path:'/runways',label:'Uçuş-enmə zolaqları',description:'Runway və əlaqəli sahələr',icon:Route,group:'main'},
 {path:'/ols',label:'OLS səthləri',description:'Avtomatik və manual OLS idarəsi',icon:Layers3,group:'main'},
 {path:'/dtm',label:'DTM',description:'Relyef mənbələri və yüksəklik',icon:Mountain,group:'management'},
 {path:'/obstacles',label:'Maneələr',description:'Maneələrin qeydiyyatı və analizi',icon:RadioTower,group:'management'},
 {path:'/violations',label:'Pozuntular',description:'OLS pozuntularının izlənməsi',icon:ShieldAlert,group:'management'},
 {path:'/standards',label:'Standartlar',description:'Standart və OLS parametrləri',icon:BookOpen,group:'management'},
 {path:'/reports',label:'Hesabatlar',description:'Analitik hesabat və ixrac',icon:FileBarChart,group:'management'},
 {path:'/users',label:'İstifadəçilər',description:'İstifadəçi və rol idarəetməsi',icon:Users,group:'system',roles:['ADMIN']},
 {path:'/settings',label:'Tənzimləmələr',description:'Profil və sistem seçimləri',icon:Settings,group:'system'},
]

export const routeByPath=(pathname:string)=>appRoutes.find(route=>route.path==='/'?pathname==='/':pathname.startsWith(route.path))??appRoutes[0]
