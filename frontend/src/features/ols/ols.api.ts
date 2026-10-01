import {apiClient} from '../../api/client'
import type {AutomaticOlsResult,OlsSurfaceList} from './ols.types'

export const generateAutomaticOls=async(payload:{standard_id:number;run_id:number;replace_existing:boolean;revision_note:string|null})=>(await apiClient.post<AutomaticOlsResult>('/ols/generate',payload,{timeout:120000})).data

export const listAutomaticOls=async(airId:number,params:{run_id:number;standard_id:number})=>(await apiClient.get<OlsSurfaceList>(`/airports/${airId}/ols-surfaces`,{params:{...params,generation_method:'AUTOMATIC',page:1,page_size:100}})).data

export const getGeneratedOlsGeojson=async(airId:number,params:{run_id:number;standard_id:number})=>(await apiClient.get<Record<string,unknown>>(`/airports/${airId}/ols-surfaces/geojson`,{params:{...params,generation_method:'AUTOMATIC'}})).data
export const archiveOlsSurface=async(surfaceId:number)=>{await apiClient.delete(`/ols/surfaces/${surfaceId}`)}
