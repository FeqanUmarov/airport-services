import {apiClient} from '../../api/client'
import type {Standard,StandardList,StandardPayload,StandardSurfaceList,ParameterPayload} from './standards.types'

export const listStandards=async(params:Record<string,unknown>)=>(await apiClient.get<StandardList>('/standards',{params})).data
export const getStandard=async(id:number)=>(await apiClient.get<Standard>(`/standards/${id}`)).data
export const createStandard=async(payload:StandardPayload)=>(await apiClient.post<Standard>('/standards',payload)).data
export const updateStandard=async(id:number,payload:Partial<StandardPayload>)=>(await apiClient.patch<Standard>(`/standards/${id}`,payload)).data
export const updateStandardStatus=async(id:number,statusId:number)=>apiClient.patch(`/standards/${id}/status`,{status_id:statusId})
export const archiveStandard=async(id:number)=>apiClient.delete(`/standards/${id}`)
export const getStandardSurfaces=async(id:number)=>(await apiClient.get<StandardSurfaceList>(`/standards/${id}/ols-configurations`)).data
export const addStandardSurface=async(id:number,surfaceTypeId:number,description:string|null)=>(await apiClient.post<StandardSurfaceList>(`/standards/${id}/ols-configurations`,{surface_type_id:surfaceTypeId,description})).data
export const updateStandardSurface=async(id:number,configurationId:number,payload:{description?:string|null;status_id?:number})=>(await apiClient.patch<StandardSurfaceList>(`/standards/${id}/ols-configurations/${configurationId}`,payload)).data
export const archiveStandardSurface=async(id:number,configurationId:number)=>apiClient.delete(`/standards/${id}/ols-configurations/${configurationId}`)
export const upsertStandardParameter=async(id:number,configurationId:number,payload:ParameterPayload)=>(await apiClient.put<StandardSurfaceList>(`/standards/${id}/ols-configurations/${configurationId}/parameters`,payload)).data
export const archiveStandardParameter=async(id:number,configurationId:number,paramValueId:number)=>apiClient.delete(`/standards/${id}/ols-configurations/${configurationId}/parameters/${paramValueId}`)
