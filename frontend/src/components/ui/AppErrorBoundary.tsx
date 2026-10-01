import {Component,type ErrorInfo,type ReactNode} from 'react'
import {AlertOctagon} from 'lucide-react'

export class AppErrorBoundary extends Component<{children:ReactNode},{failed:boolean}>{
 state={failed:false}
 static getDerivedStateFromError(){return{failed:true}}
 componentDidCatch(error:Error,info:ErrorInfo){console.error('Unhandled UI error',error,info)}
 render(){if(this.state.failed)return <div className="fatal-error"><AlertOctagon/><h1>Səhifə göstərilə bilmədi</h1><p>Gözlənilməz interfeys xətası baş verdi.</p><button onClick={()=>window.location.reload()}>Səhifəni yenilə</button></div>;return this.props.children}
}
