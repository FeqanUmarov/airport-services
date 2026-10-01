export type Standard={standard_id:number;standard_type_id:number;standard_type_code:string;standard_type_name:string;code:string;aze_name:string;eng_name:string;edition:string|null;amendment:string|null;effective_date:string;description:string|null;status_id:number;status:string;created_date:string;last_edited_date:string}
export type StandardList={items:Standard[];total:number;page:number;page_size:number}
export type StandardPayload={standard_type_id:number;code:string;aze_name:string;eng_name:string;edition:string|null;amendment:string|null;effective_date:string;description:string|null}
export type StandardParameter={param_value_id:number;parameter_id:number;parameter_code:string;parameter_name:string;section_no:number;numeric_value:string|null;boolean_value:boolean|null;unit_id:number;unit_code:string;unit_symbol:string|null;description:string|null;status_id:number;status:string}
export type StandardSurface={standard_ols_id:number;standard_id:number;surface_type_id:number;surface_type_code:string;surface_type_name:string;description:string|null;status_id:number;status:string;parameters:StandardParameter[]}
export type StandardSurfaceList={items:StandardSurface[];total:number}
export type ParameterPayload={parameter_id:number;section_no:number;numeric_value:number|null;boolean_value:boolean|null;description:string|null}
