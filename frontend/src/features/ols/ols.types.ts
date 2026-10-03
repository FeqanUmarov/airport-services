export type GeneratedOlsSurface={
 ols_surface_id:number
 standard_ols_id:number
 surface_type:string
 run_id:number
 run_dir_id:number|null
 generation_method:string
 reference_geometry:string|null
 topology_status:'PASSED'|'WARNING'|'NOT_APPLICABLE'
 topology_message:string|null
 gap_m:number|null
 overlap_m:number|null
}

export type AutomaticOlsResult={
 air_id:number
 run_id:number
 standard_id:number
 generated_count:number
 surfaces:GeneratedOlsSurface[]
}

export type OlsSurface={
 ols_surface_id:number
 standard_id:number
 standard_code:string
 surface_type:string
 generation_method:string
 run_id:number|null
 run_dir_id:number|null
 status:string
 created_date:string
}

export type OlsSurfaceList={items:OlsSurface[];total:number;page:number;page_size:number}
