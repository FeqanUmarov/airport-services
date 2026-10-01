import {useEffect,useRef,useState} from 'react'
import Feature from 'ol/Feature'
import GeoJSON from 'ol/format/GeoJSON'
import Map from 'ol/Map'
import View from 'ol/View'
import Draw from 'ol/interaction/Draw'
import Modify from 'ol/interaction/Modify'
import Snap from 'ol/interaction/Snap'
import VectorLayer from 'ol/layer/Vector'
import {fromLonLat} from 'ol/proj'
import VectorSource from 'ol/source/Vector'
import {Circle as CircleStyle,Fill,Stroke,Style} from 'ol/style'
import {MapPin,Maximize2,Minimize2,MousePointer2,Pentagon,Trash2} from 'lucide-react'
import type {BoundaryGeometry,PointGeometry} from '../airports.types'
import {useMapExpansion} from '../../../shared/useMapExpansion'
import {createBaseMapLayers,MapLayerControl} from '../../../shared/map-controls'

const format=new GeoJSON()
export function AirportGeometryMap({point,boundary,onPointChange,onBoundaryChange,readOnly=false}:{point:PointGeometry|null;boundary:BoundaryGeometry|null;onPointChange?:(value:PointGeometry|null)=>void;onBoundaryChange?:(value:BoundaryGeometry|null)=>void;readOnly?:boolean}){
 const target=useRef<HTMLDivElement>(null);const mapRef=useRef<Map|null>(null);const sourceRef=useRef(new VectorSource()),dataLayer=useRef<VectorLayer<VectorSource>|null>(null),baseMaps=useRef(createBaseMapLayers()).current;const [mode,setMode]=useState<'point'|'polygon'|'modify'|null>(null),[dataVisible,setDataVisible]=useState(true)
 const {expanded,toggleExpanded}=useMapExpansion(mapRef)
 useEffect(()=>{if(!target.current)return;const source=sourceRef.current;const layer=new VectorLayer({source,style:feature=>new Style({fill:new Fill({color:feature.getGeometry()?.getType()==='Point'?'#fff':'rgba(22,131,229,.18)'}),stroke:new Stroke({color:'#1683e5',width:2.5}),image:new CircleStyle({radius:7,fill:new Fill({color:'#0878e8'}),stroke:new Stroke({color:'#fff',width:3})})})});dataLayer.current=layer;const map=new Map({target:target.current,layers:[...baseMaps.layers,layer],view:new View({center:fromLonLat(point?.coordinates??[46.75,39.11]),zoom:point?13:6})});mapRef.current=map;return()=>{map.setTarget(undefined);mapRef.current=null}},[])
 useEffect(()=>{const source=sourceRef.current;source.clear();if(boundary)source.addFeature(format.readFeature(boundary,{featureProjection:'EPSG:3857'}) as Feature);if(point)source.addFeature(format.readFeature(point,{featureProjection:'EPSG:3857'}) as Feature);if(source.getFeatures().length&&mapRef.current){const extent=source.getExtent();if(extent)mapRef.current.getView().fit(extent,{padding:[55,55,55,55],maxZoom:15,duration:250})}},[point,boundary])
 useEffect(()=>{const map=mapRef.current;if(!map||readOnly)return;const source=sourceRef.current;let interaction:Draw|Modify|null=null;if(mode==='point'||mode==='polygon'){interaction=new Draw({source,type:mode==='point'?'Point':'Polygon'});interaction.on('drawstart',()=>source.getFeatures().filter(f=>f.getGeometry()?.getType()===(mode==='point'?'Point':'Polygon')).forEach(f=>source.removeFeature(f)));interaction.on('drawend',event=>{const geometry=format.writeGeometryObject(event.feature.getGeometry()!,{featureProjection:'EPSG:3857',dataProjection:'EPSG:4326'});if(mode==='point')onPointChange?.(geometry as PointGeometry);else onBoundaryChange?.(geometry as BoundaryGeometry);setMode(null)})}else if(mode==='modify'){interaction=new Modify({source});interaction.on('modifyend',()=>{for(const feature of source.getFeatures()){const geometry=format.writeGeometryObject(feature.getGeometry()!,{featureProjection:'EPSG:3857',dataProjection:'EPSG:4326'});if(geometry.type==='Point')onPointChange?.(geometry as PointGeometry);else onBoundaryChange?.(geometry as BoundaryGeometry)}})}if(interaction){map.addInteraction(interaction);const snap=new Snap({source});map.addInteraction(snap);return()=>{map.removeInteraction(interaction!);map.removeInteraction(snap)}}},[mode,readOnly,onPointChange,onBoundaryChange])
 return <div className={`airport-geometry expandable-map${expanded?' map-expanded':''}`}><div ref={target} className="airport-geometry-map"/><MapLayerControl osm={baseMaps.osm} google={baseMaps.google} layers={[{id:'geometry',label:'Airport geometriyası',visible:dataVisible,onChange:value=>{setDataVisible(value);dataLayer.current?.setVisible(value)}}]}/><button type="button" className="map-expand-control" onClick={toggleExpanded} title={expanded?'Xəritəni kiçilt (Esc)':'Xəritəni böyüt'} aria-label={expanded?'Xəritəni kiçilt':'Xəritəni böyüt'}>{expanded?<Minimize2/>:<Maximize2/>}</button>{!readOnly&&<div className="geometry-tools"><button className={mode==='point'?'active':''} type="button" onClick={()=>setMode('point')}><MapPin/>ARP nöqtəsi</button><button className={mode==='polygon'?'active':''} type="button" onClick={()=>setMode('polygon')}><Pentagon/>Sərhəd çək</button><button className={mode==='modify'?'active':''} type="button" onClick={()=>setMode('modify')}><MousePointer2/>Redaktə</button><button type="button" onClick={()=>{sourceRef.current.clear();onPointChange?.(null);onBoundaryChange?.(null)}}><Trash2/>Təmizlə</button></div>}<div className="map-coordinates">WGS 84 · baza xəritəsi dəyişdirilə bilər</div></div>
}
