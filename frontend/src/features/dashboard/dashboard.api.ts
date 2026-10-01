import {apiClient} from '../../api/client'
import type {DashboardOverview} from './dashboard.types'
export const getDashboardOverview=async()=> (await apiClient.get<DashboardOverview>('/dashboard/overview')).data
