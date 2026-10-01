import {ArrowLeft,Clock3} from 'lucide-react'
import {Link} from 'react-router-dom'
import type {AppRoute} from '../../app/routes'
export function PlaceholderPage({route}:{route:AppRoute}){return <div className="placeholder-page"><div className="placeholder-orbit"><span><route.icon/></span><i/><i/><i/></div><small><Clock3/> Hazırlanma növbəsindədir</small><h1>{route.label}</h1><p>{route.description} modulu növbəti mərhələlərdə mövcud backend API-lərinə qoşulacaq.</p><Link to="/"><ArrowLeft/> İdarə panelinə qayıt</Link></div>}
