import type {BoundaryGeometry} from '../airports/airports.types'

export type ImportedFeature={type:'Feature';id:number;geometry:BoundaryGeometry;properties:Record<string,unknown>}
export type ShapefilePreview={file_name:string;source_crs:string;feature_count:number;geometry_types:string[];fields:string[];bbox:number[]|null;feature_collection:{type:'FeatureCollection';features:ImportedFeature[]}}
export type ImportTarget='OLS'|'RUNWAY'|'STRIP'|'RUNWAY_AREA'
export type GisLayerKey='runways'|'strips'|'areas'|'preview'|'draft'|`ols:${string}`
export type LayerSetting={key:GisLayerKey;label:string;visible:boolean;opacity:number;order:number;color:string}
export type MapTool='pan'|'identify'|'measure-line'|'measure-area'|'draw-point'|'draw-line'|'draw-polygon'|'edit'
export type MeasureUnit='cm'|'m'|'km'
