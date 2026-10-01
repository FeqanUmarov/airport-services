export type PointGeometry={type:'Point';coordinates:[number,number]}
export type BoundaryGeometry={type:'Polygon'|'MultiPolygon';coordinates:number[][][]|number[][][][]}
export type Airport={air_id:number;icao_id:number;icao_code:string;iata_code:string|null;aze_name:string;eng_name:string;country_id:number;country_name:string;city_id:number;city_name:string;elevation_m:string;arp_geom:PointGeometry;boundary_geom:BoundaryGeometry;status_id:number;status:string;created_date:string;last_edited_date:string}
export type AirportList={items:Airport[];total:number;page:number;page_size:number}
export type AirportPayload={icao_id:number;iata_code:string|null;aze_name:string;eng_name:string;country_id:number;city_id:number;elevation_m:number;arp_geom:PointGeometry;boundary_geom:BoundaryGeometry}
export type DictionaryItem={id:number;code:string|null;aze_name:string|null;eng_name:string|null;description:string|null;status_id:number|null;parent_id:number|null;symbol:string|null}
export type DictionaryList={items:DictionaryItem[];total:number}
export type AirportFilters={page:number;page_size:number;search?:string;country_id?:number;city_id?:number;status_id?:number}
