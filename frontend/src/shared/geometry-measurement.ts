import type Geometry from 'ol/geom/Geometry'
import type LineString from 'ol/geom/LineString'
import type Polygon from 'ol/geom/Polygon'
import {toLonLat} from 'ol/proj'
import proj4 from 'proj4'

type Coordinate=[number,number]

// WGS84 ellipsoid constants. OpenLayers' ol/sphere helpers use a sphere,
// which can differ from ArcGIS Pro's WGS84 geodesic result by several metres.
const WGS84_A=6378137
const WGS84_F=1/298.257223563
const WGS84_B=(1-WGS84_F)*WGS84_A

function vincentyDistance(first:Coordinate,second:Coordinate):number{
 const [lon1,lat1]=first,[lon2,lat2]=second
 if(lon1===lon2&&lat1===lat2)return 0
 const phi1=lat1*Math.PI/180,phi2=lat2*Math.PI/180
 const reduced1=Math.atan((1-WGS84_F)*Math.tan(phi1)),reduced2=Math.atan((1-WGS84_F)*Math.tan(phi2))
 const sin1=Math.sin(reduced1),cos1=Math.cos(reduced1),sin2=Math.sin(reduced2),cos2=Math.cos(reduced2)
 const longitudeDelta=(lon2-lon1)*Math.PI/180
 let lambda=longitudeDelta
 let sinSigma=0,cosSigma=0,sigma=0,sinAlpha=0,cosSqAlpha=0,cos2SigmaM=0
 for(let iteration=0;iteration<100;iteration++){
  const sinLambda=Math.sin(lambda),cosLambda=Math.cos(lambda)
  sinSigma=Math.sqrt((cos2*sinLambda)**2+(cos1*sin2-sin1*cos2*cosLambda)**2)
  if(sinSigma===0)return 0
  cosSigma=sin1*sin2+cos1*cos2*cosLambda
  sigma=Math.atan2(sinSigma,cosSigma)
  sinAlpha=cos1*cos2*sinLambda/sinSigma
  cosSqAlpha=1-sinAlpha*sinAlpha
  cos2SigmaM=cosSqAlpha===0?0:cosSigma-2*sin1*sin2/cosSqAlpha
  const coefficient=WGS84_F/16*cosSqAlpha*(4+WGS84_F*(4-3*cosSqAlpha))
  const previous=lambda
  lambda=longitudeDelta+(1-coefficient)*WGS84_F*sinAlpha*(sigma+coefficient*sinSigma*(cos2SigmaM+coefficient*cosSigma*(-1+2*cos2SigmaM*cos2SigmaM)))
  if(Math.abs(lambda-previous)<1e-12)break
 }
 const uSq=cosSqAlpha*(WGS84_A*WGS84_A-WGS84_B*WGS84_B)/(WGS84_B*WGS84_B)
 const coefficientA=1+uSq/16384*(4096+uSq*(-768+uSq*(320-175*uSq)))
 const coefficientB=uSq/1024*(256+uSq*(-128+uSq*(74-47*uSq)))
 const deltaSigma=coefficientB*sinSigma*(cos2SigmaM+coefficientB/4*(cosSigma*(-1+2*cos2SigmaM*cos2SigmaM)-coefficientB/6*cos2SigmaM*(-3+4*sinSigma*sinSigma)*(-3+4*cos2SigmaM*cos2SigmaM)))
 return WGS84_B*coefficientA*(sigma-deltaSigma)
}

export function wgs84LineLength(geometry:LineString):number{
 const coordinates=geometry.getCoordinates().map(value=>toLonLat(value) as Coordinate)
 return coordinates.slice(1).reduce((total,coordinate,index)=>total+vincentyDistance(coordinates[index],coordinate),0)
}

function ringArea(coordinates:Coordinate[],projection:string):number{
 const projected=coordinates.map(coordinate=>proj4('EPSG:4326',projection,coordinate) as Coordinate)
 return Math.abs(projected.reduce((sum,point,index)=>{const next=projected[(index+1)%projected.length];return sum+point[0]*next[1]-next[0]*point[1]},0)/2)
}

export function localUtmArea(geometry:Geometry):number{
 if(geometry.getType()!=='Polygon')return 0
 const rings=(geometry as Polygon).getCoordinates().map(ring=>ring.map(value=>toLonLat(value) as Coordinate))
 const all=rings.flat()
 if(!all.length)return 0
 const longitude=all.reduce((sum,coordinate)=>sum+coordinate[0],0)/all.length
 const latitude=all.reduce((sum,coordinate)=>sum+coordinate[1],0)/all.length
 const zone=Math.floor((longitude+180)/6)+1
 const projection=`+proj=utm +zone=${zone} ${latitude<0?'+south ':''}+datum=WGS84 +units=m +no_defs`
 const outer=ringArea(rings[0],projection)
 return Math.max(0,outer-rings.slice(1).reduce((sum,ring)=>sum+ringArea(ring,projection),0))
}
