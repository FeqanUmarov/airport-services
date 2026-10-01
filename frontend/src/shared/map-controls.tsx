import {useState} from 'react'
import TileLayer from 'ol/layer/Tile'
import OSM from 'ol/source/OSM'
import XYZ from 'ol/source/XYZ'
import Control from 'ol/control/Control'
import type BaseLayer from 'ol/layer/Base'
import {Layers3,Map as MapIcon,X} from 'lucide-react'

export type MapLayerOption={id:string;label:string;visible:boolean;onChange:(visible:boolean)=>void}

export function createBaseMapLayers(){
 const osm=new TileLayer({source:new OSM(),visible:true,properties:{title:'OpenStreetMap'}})
 const google=new TileLayer({source:new XYZ({url:'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',crossOrigin:'anonymous',attributions:'© Google'}),visible:false,properties:{title:'Google Satellite'}})
 return {osm,google,layers:[osm,google]}
}

export function MapLayerControl({osm,google,layers=[]}:{osm:TileLayer<OSM>;google:TileLayer<XYZ>;layers?:MapLayerOption[]}){
 const [open,setOpen]=useState(false),[base,setBase]=useState<'osm'|'google'>('osm')
 const selectBase=(value:'osm'|'google')=>{setBase(value);osm.setVisible(value==='osm');google.setVisible(value==='google')}
 return <div className="map-layer-control"><button type="button" className={open?'active':''} onClick={()=>setOpen(value=>!value)} title="Xəritə layları"><Layers3/></button>{open&&<section><header><b>Laylar</b><button type="button" onClick={()=>setOpen(false)}><X/></button></header><fieldset><legend><MapIcon/>Baza xəritəsi</legend><label><input type="radio" name="base-map" checked={base==='osm'} onChange={()=>selectBase('osm')}/>OpenStreetMap</label><label><input type="radio" name="base-map" checked={base==='google'} onChange={()=>selectBase('google')}/>Google Satellite</label></fieldset>{layers.length>0&&<fieldset><legend><Layers3/>Məlumat layları</legend>{layers.map(layer=><label key={layer.id}><input type="checkbox" checked={layer.visible} onChange={event=>layer.onChange(event.target.checked)}/>{layer.label}</label>)}</fieldset>}</section>}</div>
}

export function createMapLayerControl(osm:TileLayer<OSM>,google:TileLayer<XYZ>,dataLayer:BaseLayer,dataLabel:string){
 const root=document.createElement('div');root.className='map-layer-control ol-unselectable'
 const trigger=document.createElement('button');trigger.type='button';trigger.title='Xəritə layları';trigger.textContent='☷'
 const panel=document.createElement('section');panel.hidden=true
 panel.innerHTML='<header><b>Laylar</b></header><fieldset><legend>Baza xəritəsi</legend><label><input type="radio" name="base-map-native" value="osm" checked>OpenStreetMap</label><label><input type="radio" name="base-map-native" value="google">Google Satellite</label></fieldset><fieldset><legend>Məlumat layları</legend><label><input type="checkbox" name="data-layer" checked><span data-layer-label></span></label></fieldset>'
 const label=panel.querySelector<HTMLElement>('[data-layer-label]');if(label)label.textContent=dataLabel
 trigger.addEventListener('click',()=>{panel.hidden=!panel.hidden;trigger.classList.toggle('active',!panel.hidden)})
 panel.querySelectorAll<HTMLInputElement>('input[name="base-map-native"]').forEach(input=>input.addEventListener('change',()=>{osm.setVisible(input.value==='osm');google.setVisible(input.value==='google')}))
 panel.querySelector<HTMLInputElement>('input[name="data-layer"]')?.addEventListener('change',event=>dataLayer.setVisible((event.currentTarget as HTMLInputElement).checked))
 root.append(trigger,panel)
 return new Control({element:root})
}
