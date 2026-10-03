import type {BoundaryGeometry} from '../airports/airports.types'

export type ImportedFeature={type:'Feature';id:number;geometry:BoundaryGeometry;properties:Record<string,unknown>}
export type ShapefilePreview={file_name:string;source_crs:string;feature_count:number;geometry_types:string[];fields:string[];bbox:number[]|null;feature_collection:{type:'FeatureCollection';features:ImportedFeature[]}}
export type ImportTarget='OLS'|'RUNWAY'|'STRIP'|'RUNWAY_AREA'
export type ShapefileImportMetadata={target:ImportTarget;air_id:number;run_id?:number|null;run_dir_id?:number|null;standard_ols_id?:number|null;area_type_id?:number|null;aze_name?:string|null;eng_name?:string|null;designator_1?:string|null;designator_2?:string|null;length_m?:number|null;width_m?:number|null;default_elevation_m?:number|null}
export type ShapefileImportResult={target:ImportTarget;imported_count:number;object_ids:number[];source_crs:string;geometry_types:string[]}
export type GisLayerKey='runways'|'strips'|'areas'|'preview'|'draft'|`ols:${string}`
export type LayerSetting={key:GisLayerKey;label:string;visible:boolean;opacity:number;order:number;color:string}
export type MapTool='pan'|'identify'|'measure-line'|'measure-area'|'draw-point'|'draw-line'|'draw-polygon'|'edit'
export type MeasureUnit='cm'|'m'|'km'
