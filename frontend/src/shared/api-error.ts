import axios from 'axios'
type ApiErrorBody={detail?:string|Array<{msg?:string}>}
export function getApiErrorMessage(error:unknown,fallback='Əməliyyat zamanı xəta baş verdi.'){
 if(!axios.isAxiosError<ApiErrorBody>(error))return fallback
 if(!error.response)return 'Serverlə əlaqə yaratmaq mümkün olmadı.'
 const detail=error.response.data?.detail
 if(typeof detail==='string')return detail
 if(Array.isArray(detail))return detail.map(item=>item.msg).filter(Boolean).join(', ')||fallback
 if(error.response.status===403)return 'Bu əməliyyat üçün icazəniz yoxdur.'
 if(error.response.status===404)return 'Axtarılan məlumat tapılmadı.'
 return fallback
}
