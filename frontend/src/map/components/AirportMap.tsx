import {useEffect,useRef,useState} from 'react'
import {Maximize2,Minimize2} from 'lucide-react'
import Map from 'ol/Map'
import View from 'ol/View'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import Feature from 'ol/Feature'
import {fromLonLat} from 'ol/proj'
import {LineString,Point,Polygon} from 'ol/geom'
import {Circle as CircleStyle,Fill,Stroke,Style} from 'ol/style'
import {useMapExpansion} from '../../shared/useMapExpansion'
import {createBaseMapLayers,MapLayerControl} from '../../shared/map-controls'
const project=(coords:number[][])=>coords.map(c=>fromLonLat(c))
export function AirportMap(){const target=useRef<HTMLDivElement>(null),mapRef=useRef<Map|null>(null),dataLayer=useRef<VectorLayer<VectorSource>|null>(null),baseMaps=useRef(createBaseMapLayers()).current;const [dataVisible,setDataVisible]=useState(true);const {expanded,toggleExpanded}=useMapExpansion(mapRef);useEffect(()=>{if(!target.current)return
 const center=[46.7428,39.112]; const source=new VectorSource();
 const runway=new Feature(new LineString(project([[46.7338,39.1016],[46.7519,39.1247]])));runway.setStyle(new Style({stroke:new Stroke({color:'#11e091',width:7})}));source.addFeature(runway)
 const rings=[{r:.035,c:'rgba(42,167,247,.26)',s:'#20a8e8'},{r:.055,c:'rgba(61,190,91,.24)',s:'#39b65d'},{r:.078,c:'rgba(255,220,28,.20)',s:'#dbca2d'}]
 rings.forEach(({r,c,s})=>{const pts=Array.from({length:65},(_,i)=>{const a=i/64*Math.PI*2;return [center[0]+Math.cos(a)*r,center[1]+Math.sin(a)*r]});const f=new Feature(new Polygon([project(pts)]));f.setStyle(new Style({fill:new Fill({color:c}),stroke:new Stroke({color:s,width:2})}));source.addFeature(f)})
 const approach=(flip=false)=>{const d=flip?-1:1;const pts=project([[46.744,39.113],[46.744+d*.014,39.113+d*.018],[46.744+d*.045,39.113+d*.062],[46.744+d*.065,39.113+d*.052],[46.748,39.116],[46.744,39.113]]);const f=new Feature(new Polygon([pts]));f.setStyle(new Style({fill:new Fill({color:'rgba(255,80,103,.28)'}),stroke:new Stroke({color:'#ff536c',width:2})}));source.addFeature(f)};approach();approach(true)
 ;[[46.69,39.10],[46.78,39.08],[46.81,39.15],[46.67,39.16]].forEach(p=>{const f=new Feature(new Point(fromLonLat(p)));f.setStyle(new Style({image:new CircleStyle({radius:6,fill:new Fill({color:'#f52237'}),stroke:new Stroke({color:'#fff',width:2})})}));source.addFeature(f)})
 const vectors=new VectorLayer({source});dataLayer.current=vectors;const map=new Map({target:target.current,layers:[...baseMaps.layers,vectors],view:new View({center:fromLonLat(center),zoom:12.2})});mapRef.current=map;return()=>{map.setTarget(undefined);mapRef.current=null}},[]);return <div className={`map expandable-map${expanded?' map-expanded':''}`}><div ref={target} className="map-canvas"/><MapLayerControl osm={baseMaps.osm} google={baseMaps.google} layers={[{id:'airport-data',label:'Airport məlumatları',visible:dataVisible,onChange:value=>{setDataVisible(value);dataLayer.current?.setVisible(value)}}]}/><button type="button" className="map-expand-control map-expand-main" onClick={toggleExpanded} title={expanded?'Xəritəni kiçilt (Esc)':'Xəritəni böyüt'} aria-label={expanded?'Xəritəni kiçilt':'Xəritəni böyüt'}>{expanded?<Minimize2/>:<Maximize2/>}</button></div>}
