import {useEffect,useMemo,useRef,useState} from 'react'
import Map from 'ol/Map'
import View from 'ol/View'
import GeoJSON from 'ol/format/GeoJSON'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import {Fill,Stroke,Style,Text} from 'ol/style'
import {fromLonLat} from 'ol/proj'
import {Layers3,Maximize2,Minimize2} from 'lucide-react'
import {createBaseMapLayers} from '../../../shared/map-controls'
import {useMapExpansion} from '../../../shared/useMapExpansion'
import type {Runway} from '../../runways/runways.types'

type Props={runway:Runway|null;geojson:Record<string,unknown>|null;loading:boolean}
const surfaceColors:Record<string,string>={INNER_HORIZONTAL:'#2785e8',CONICAL:'#75a823',APPROACH:'#ef5265',TAKE_OFF_CLIMB:'#8b5cf6',TAKEOFF_CLIMB:'#8b5cf6',TRANSITIONAL:'#f0b429',INNER_APPROACH:'#ec4899',INNER_TRANSITIONAL:'#14b8a6',BALKED_LANDING:'#f97316'}

export function OlsGenerationMap({runway,geojson,loading}:Props){
 const target=useRef<HTMLDivElement>(null),mapRef=useRef<Map|null>(null)
 const [base,setBase]=useState<'osm'|'google'>('osm'),[showRunway,setShowRunway]=useState(true),[showOls,setShowOls]=useState(true),[layersOpen,setLayersOpen]=useState(false)
 const baseMaps=useMemo(()=>createBaseMapLayers(),[])
 const runwaySource=useRef(new VectorSource()),olsSource=useRef(new VectorSource())
 const runwayLayer=useRef(new VectorLayer({source:runwaySource.current,style:new Style({fill:new Fill({color:'rgba(15,105,190,.24)'}),stroke:new Stroke({color:'#0878e8',width:3})})}))
 const olsLayer=useRef(new VectorLayer({source:olsSource.current,style:feature=>{const code=String(feature.get('surface_type')??'OLS');const color=surfaceColors[code]??'#7757d9';return new Style({fill:new Fill({color:`${color}2e`}),stroke:new Stroke({color,width:2}),text:new Text({text:code.replaceAll('_',' '),font:'600 11px Inter, sans-serif',fill:new Fill({color:'#11233f'}),stroke:new Stroke({color:'#fff',width:3})})})}}))
 const {expanded,toggleExpanded}=useMapExpansion(mapRef)
 useEffect(()=>{if(!target.current)return;const map=new Map({target:target.current,layers:[...baseMaps.layers,runwayLayer.current,olsLayer.current],view:new View({center:fromLonLat([47.3,40.3]),zoom:7})});mapRef.current=map;return()=>{map.setTarget(undefined);mapRef.current=null}},[baseMaps.layers])
 useEffect(()=>{baseMaps.osm.setVisible(base==='osm');baseMaps.google.setVisible(base==='google')},[base,baseMaps])
 useEffect(()=>runwayLayer.current.setVisible(showRunway),[showRunway])
 useEffect(()=>olsLayer.current.setVisible(showOls),[showOls])
 useEffect(()=>{runwaySource.current.clear();if(!runway)return;const format=new GeoJSON();runwaySource.current.addFeatures(format.readFeatures({type:'FeatureCollection',features:[{type:'Feature',geometry:runway.geom,properties:{}}]},{featureProjection:'EPSG:3857'}));const extent=runwaySource.current.getExtent();if(extent)mapRef.current?.getView().fit(extent,{padding:[90,90,90,90],maxZoom:15,duration:350})},[runway])
 useEffect(()=>{olsSource.current.clear();if(!geojson)return;const format=new GeoJSON();olsSource.current.addFeatures(format.readFeatures(geojson,{featureProjection:'EPSG:3857'}));const extent=olsSource.current.getExtent();if(olsSource.current.getFeatures().length&&extent)mapRef.current?.getView().fit(extent,{padding:[60,60,60,60],maxZoom:13,duration:500})},[geojson])
 return <div className={`ols-generation-map expandable-map${expanded?' map-expanded':''}`}>
  <div ref={target} className="map-canvas"/>
  <div className="ols-map-tools"><button type="button" className={layersOpen?'active':''} onClick={()=>setLayersOpen(v=>!v)} aria-label="Xəritə layları"><Layers3/></button><button type="button" onClick={toggleExpanded} aria-label={expanded?'Kiçilt':'Tam ekran'}>{expanded?<Minimize2/>:<Maximize2/>}</button></div>
  {layersOpen&&<aside className="ols-map-layers"><header><b>Xəritə layları</b></header><small>Baza xəritəsi</small><label><input type="radio" checked={base==='osm'} onChange={()=>setBase('osm')}/>OpenStreetMap</label><label><input type="radio" checked={base==='google'} onChange={()=>setBase('google')}/>Google Satellite</label><small>Məlumat layları</small><label><input type="checkbox" checked={showRunway} onChange={e=>setShowRunway(e.target.checked)}/>Runway</label><label><input type="checkbox" checked={showOls} onChange={e=>setShowOls(e.target.checked)}/>Yaradılmış OLS</label></aside>}
  {loading&&<div className="ols-map-loading"><span/><b>Xəritə yenilənir...</b></div>}
  {!loading&&!geojson&&<div className="ols-map-empty"><Layers3/><b>OLS nəticəsi xəritədə burada göstəriləcək</b><span>Seçimləri tamamlayıb generasiyanı başladın.</span></div>}
 </div>
}
