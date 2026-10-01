export interface TokenPair {access_token:string;refresh_token:string;token_type:string;expires_in:number}
export interface CurrentUser {user_id:number;username:string;email:string;first_name:string;last_name:string;roles:string[]}
export interface LoginCredentials {username:string;password:string;remember:boolean}
