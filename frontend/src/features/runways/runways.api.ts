import {apiClient} from '../../api/client'
import type {BoundaryGeometry} from '../airports/airports.types'
import type {DeclaredDistance,Direction,DirectionPayload,Runway,RunwayArea,RunwayPayload,Strip} from './runways.types'

export const listRunways=async(airId:number,params?:{search?:string;status_id?:number})=>(await apiClient.get<{items:Runway[];total:number}>(`/airports/${airId}/runways`,{params})).data
export const getRunway=async(id:number)=>(await apiClient.get<Runway>(`/runways/${id}`)).data
export const createRunway=async(airId:number,payload:RunwayPayload)=>(await apiClient.post<Runway>(`/airports/${airId}/runways`,payload)).data
export const updateRunway=async(id:number,payload:Partial<RunwayPayload>)=>(await apiClient.patch<Runway>(`/runways/${id}`,payload)).data
export const setRunwayStatus=(id:number,status_id:number)=>apiClient.patch(`/runways/${id}/status`,{status_id})
export const archiveRunway=(id:number)=>apiClient.delete(`/runways/${id}`)
export const listDirections=async(id:number)=>(await apiClient.get<Direction[]>(`/runways/${id}/directions`)).data
export const createDirection=async(id:number,payload:DirectionPayload)=>(await apiClient.post<Direction>(`/runways/${id}/directions`,payload)).data
export const regenerateDirections=async(id:number)=>(await apiClient.post<Direction[]>(`/runways/${id}/directions/regenerate`)).data
export const updateDirection=async(id:number,payload:Partial<DirectionPayload>)=>(await apiClient.patch<Direction>(`/runway-directions/${id}`,payload)).data
export const setDirectionStatus=(id:number,status_id:number)=>apiClient.patch(`/runway-directions/${id}/status`,{status_id})
export const archiveDirection=(id:number)=>apiClient.delete(`/runway-directions/${id}`)
export const getDistances=async(id:number)=>(await apiClient.get<DeclaredDistance>(`/runway-directions/${id}/declared-distances`)).data
export const saveDistances=async(id:number,payload:{tora_m:number;toda_m:number;asda_m:number;lda_m:number})=>(await apiClient.put<DeclaredDistance>(`/runway-directions/${id}/declared-distances`,payload)).data
export const getStrip=async(id:number)=>(await apiClient.get<Strip>(`/runways/${id}/strip`)).data
export const saveStrip=async(id:number,payload:{length_m:number;width_m:number;geom:BoundaryGeometry})=>(await apiClient.put<Strip>(`/runways/${id}/strip`,payload)).data
export const generateStrip=async(id:number,payload:{length_m:number;centerline_offset_m:number})=>(await apiClient.post<Strip>(`/runways/${id}/strip/generate`,payload)).data
export const archiveStrip=(id:number)=>apiClient.delete(`/runways/${id}/strip`)
export const listAreas=async(id:number)=>(await apiClient.get<RunwayArea[]>(`/runway-directions/${id}/areas`)).data
export const createArea=async(id:number,payload:{area_type_id:number;length_m:number;width_m:number;geom:BoundaryGeometry})=>(await apiClient.post<RunwayArea>(`/runway-directions/${id}/areas`,payload)).data
export const regenerateClearway=async(id:number,payload:{length_m:number;width_m?:number})=>(await apiClient.post<RunwayArea>(`/runway-directions/${id}/areas/regenerate-clearway`,payload)).data
export const updateArea=async(id:number,payload:{area_type_id?:number;length_m?:number;width_m?:number;geom?:BoundaryGeometry})=>(await apiClient.patch<RunwayArea>(`/runway-areas/${id}`,payload)).data
export const archiveArea=(id:number)=>apiClient.delete(`/runway-areas/${id}`)
