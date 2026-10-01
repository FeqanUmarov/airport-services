import {apiClient} from '../../api/client'
import type {ShapefilePreview} from './map.types'
import type {Runway,RunwayArea,Strip} from '../runways/runways.types'

export const previewShapefile=async(file:File)=>{const body=new FormData();body.append('file',file);return (await apiClient.post<ShapefilePreview>('/gis-import/shapefile/preview',body,{headers:{'Content-Type':'multipart/form-data'},timeout:60000})).data}
export const getAirportOlsGeojson=async(airId:number)=>(await apiClient.get<Record<string,unknown>>(`/airports/${airId}/ols-surfaces/geojson`)).data
export const createImportedOls=async(payload:Record<string,unknown>)=>(await apiClient.post('/ols/manual',payload)).data
export const archiveOlsSurface=async(surfaceId:number)=>{await apiClient.delete(`/ols/surfaces/${surfaceId}`)}

export type OperationalLayers={runways:Runway[];strips:Strip[];areas:RunwayArea[]}
export const getOperationalLayers=async(airId:number):Promise<OperationalLayers>=>{const runways=(await apiClient.get<{items:Runway[]}>(`/airports/${airId}/runways`)).data.items;const strips:Strip[]=[];const areas:RunwayArea[]=[];await Promise.all(runways.map(async runway=>{try{strips.push((await apiClient.get<Strip>(`/runways/${runway.run_id}/strip`)).data)}catch{/* Strip is optional. */}const directions=(await apiClient.get<Array<{run_dir_id:number}>>(`/runways/${runway.run_id}/directions`)).data;await Promise.all(directions.map(async direction=>{const rows=(await apiClient.get<RunwayArea[]>(`/runway-directions/${direction.run_dir_id}/areas`)).data;areas.push(...rows)}))}));return {runways,strips,areas}}
