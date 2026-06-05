import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import {
  ENERGY_FLOW_SOURCE_ID,
  ENERGY_FLOW_LAYER_ID,
  ENERGY_FLOW_DESTINATION_ID,
  FLOW_LINE_PAINT,
  FLOW_DESTINATION_PAINT,
} from "../layers/energyFactoryLayer";

interface Props {
  map: maplibregl.Map | null;
  geoJSON: GeoJSON.FeatureCollection | null;
  layersReady: boolean;
}

export default function EnergyFlowLayer({ map, geoJSON, layersReady }: Props) {
  const addedRef = useRef(false);

  useEffect(() => {
    if (!map || !layersReady) return;
    return () => {
      if (map.getLayer(ENERGY_FLOW_LAYER_ID)) map.removeLayer(ENERGY_FLOW_LAYER_ID);
      if (map.getLayer(ENERGY_FLOW_DESTINATION_ID)) map.removeLayer(ENERGY_FLOW_DESTINATION_ID);
      if (map.getSource(ENERGY_FLOW_SOURCE_ID)) map.removeSource(ENERGY_FLOW_SOURCE_ID);
      addedRef.current = false;
    };
  }, [map, layersReady]);

  useEffect(() => {
    if (!map || !layersReady || !geoJSON) return;

    if (!addedRef.current) {
      map.addSource(ENERGY_FLOW_SOURCE_ID, { type: "geojson", data: geoJSON });
      map.addLayer({
        id: ENERGY_FLOW_LAYER_ID,
        type: "line",
        source: ENERGY_FLOW_SOURCE_ID,
        paint: FLOW_LINE_PAINT,
        filter: ["!=", ["get", "destination_type"], "candidate_site"],
      });
      map.addLayer({
        id: ENERGY_FLOW_DESTINATION_ID,
        type: "circle",
        source: ENERGY_FLOW_SOURCE_ID,
        paint: FLOW_DESTINATION_PAINT,
      });
      addedRef.current = true;
    } else {
      try {
        (map.getSource(ENERGY_FLOW_SOURCE_ID) as maplibregl.GeoJSONSource).setData(geoJSON);
      } catch {
        // source may not exist if map was recreated
      }
    }
  }, [map, layersReady, geoJSON]);

  return null;
}
