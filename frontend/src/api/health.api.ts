import {apiClient} from './client'
export type HealthResponse={status:string;database:string;postgis:string}
export const getHealth=async()=> (await apiClient.get<HealthResponse>('/health/ready')).data
