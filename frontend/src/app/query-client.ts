import {MutationCache,QueryCache,QueryClient} from '@tanstack/react-query'
import {useNotificationStore} from '../features/notifications/notification.store'
import {getApiErrorMessage} from '../shared/api-error'

const notifyError=(error:unknown)=>useNotificationStore.getState().notify({kind:'error',title:'Sorğu tamamlanmadı',message:getApiErrorMessage(error)})
export const queryClient=new QueryClient({
 queryCache:new QueryCache({onError:notifyError}),
 mutationCache:new MutationCache({onError:notifyError}),
 defaultOptions:{queries:{staleTime:120_000,gcTime:1_800_000,retry:(count,error)=>count<1&&!String(error).includes('401'),refetchOnWindowFocus:false,refetchOnReconnect:true},mutations:{retry:false}}
})
