import type {BoundaryGeometry,PointGeometry} from '../airports/airports.types'

export type LineGeometry={type:'LineString';coordinates:[number,number][]}
export type Runway={run_id:number;air_id:number;airport_name:string;aze_name:string;eng_name:string;designator_1:string;designator_2:string;length_m:string;width_m:string;geom:BoundaryGeometry;centerline_geom:LineGeometry;status_id:number;status:string;created_date:string;last_edited_date:string}
export type RunwayPayload={aze_name:string;eng_name:string;designator_1:string;designator_2:string;length_m:number;width_m:number;geom:BoundaryGeometry;centerline_geom:LineGeometry}
export type Direction={run_dir_id:number;run_id:number;designator:string;true_bearing_deg:string;threshold_elevation_m:string;threshold_geom:PointGeometry;slope_pct:string;status_id:number;status:string;created_date:string;last_edited_date:string}
export type DirectionPayload={designator:string;true_bearing_deg:number;threshold_elevation_m:number;threshold_geom:PointGeometry;slope_pct:number}
export type DeclaredDistance={declared_distance_id:number;run_dir_id:number;run_id:number;designator:string;tora_m:string;toda_m:string;asda_m:string;lda_m:string;status_id:number;status:string;created_date:string;last_edited_date:string}
export type Strip={strip_id:number;run_id:number;length_m:string;width_m:string;geom:BoundaryGeometry;status_id:number;status:string;created_date:string;last_edited_date:string}
export type RunwayArea={runway_area_id:number;run_id:number;run_dir_id:number;area_type_id:number;area_type_code:string;length_m:string;width_m:string;geom:BoundaryGeometry;status_id:number;status:string;created_date:string;last_edited_date:string}
