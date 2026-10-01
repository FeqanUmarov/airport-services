export type DashboardTotals={airports:number;runways:number;ols_surfaces:number;obstacles:number;violations:number;standards:number}
export type DashboardAirport={air_id:number;icao_code:string;name:string;city:string;status:string;runway_count:number;ols_surface_count:number;obstacle_count:number;violation_count:number}
export type DashboardObstacle={obstacle_id:number;air_id:number;airport_name:string;name:string|null;obstacle_type:string;top_elevation_m:string|null;status:string;created_date:string}
export type DashboardViolation={violation_id:number;air_id:number;obstacle_id:number;obstacle_name:string|null;surface_type:string;penetration_m:string|null;status:string;checked_date:string}
export type DashboardOverview={totals:DashboardTotals;airports:DashboardAirport[];ols_by_type:Record<string,number>;obstacles_by_type:Record<string,number>;violations_by_status:Record<string,number>;recent_obstacles:DashboardObstacle[];recent_violations:DashboardViolation[];generated_at:string}
