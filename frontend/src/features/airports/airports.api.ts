import {apiClient} from '../../api/client'
import type {Airport,AirportFilters,AirportList,AirportPayload,DictionaryList} from './airports.types'

export const listAirports=async(filters:AirportFilters)=>(await apiClient.get<AirportList>('/airports',{params:filters})).data
export const getAirport=async(id:number)=>(await apiClient.get<Airport>(`/airports/${id}`)).data
export const createAirport=async(payload:AirportPayload)=>(await apiClient.post<Airport>('/airports',payload)).data
export const updateAirport=async(id:number,payload:Partial<AirportPayload>)=>(await apiClient.patch<Airport>(`/airports/${id}`,payload)).data
export const updateAirportStatus=async(id:number,statusId:number)=>(await apiClient.patch<Airport>(`/airports/${id}/status`,{status_id:statusId})).data
export const archiveAirport=async(id:number)=>apiClient.delete(`/airports/${id}`)
export const getDictionary=async(name:string,params?:Record<string,unknown>)=>(await apiClient.get<DictionaryList>(`/dictionaries/${name}`,{params})).data
export const getAirportRunways=async(id:number)=>(await apiClient.get<{total:number}>(`/airports/${id}/runways`)).data
export const getAirportOlsSummary=async(id:number)=>(await apiClient.get<{total:number}>(`/airports/${id}/ols-surfaces/summary`)).data
export const getAirportObstacles=async(id:number)=>(await apiClient.get<{total:number}>(`/airports/${id}/obstacles`,{params:{page:1,page_size:1}})).data
export const getAirportViolations=async(id:number)=>(await apiClient.get<{total_violations:number}>(`/airports/${id}/reports/violations/summary`)).data
