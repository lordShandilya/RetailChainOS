"use client";
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import io from "socket.io-client";
import "maplibre-gl/dist/maplibre-gl.css";

const TrackPortal = ({ storeId }) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [vehicleData, setVehicleData] = useState(null);

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          osm_roads: {
            type: "vector",
            tiles: [
              "http://localhost:7800/public.planet_osm_roads/{z}/{x}/{y}.pbf",
            ],
            minzoom: 0,
            maxzoom: 14,
          },
          osm_polygons: {
            type: "vector",
            tiles: [
              "http://localhost:7800/public.planet_osm_polygon/{z}/{x}/{y}.pbf",
            ],
            minzoom: 0,
            maxzoom: 14,
          },
          osm_points: {
            type: "vector",
            tiles: [
              "http://localhost:7800/public.planet_osm_point/{z}/{x}/{y}.pbf",
            ],
            minzoom: 0,
            maxzoom: 14,
          },
        },
        layers: [
          {
            id: "background",
            type: "background",
            paint: {
              "background-color": "#f0f0f0",
            },
          },
          {
            id: "polygons",
            type: "fill",
            source: "osm_polygons",
            "source-layer": "planet_osm_polygon",
            filter: ["all"],
            paint: {
              "fill-color": "#d1d5db",
              "fill-opacity": 0.4,
            },
          },
          {
            id: "roads",
            type: "line",
            source: "osm_roads",
            "source-layer": "planet_osm_roads",
            filter: ["all"],
            paint: {
              "line-color": "#3388ff",
              "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1, 14, 3],
            },
          },
          {
            id: "points",
            type: "circle",
            source: "osm_points",
            "source-layer": "planet_osm_point",
            filter: ["all"],
            paint: {
              "circle-radius": 4,
              "circle-color": "#ff5555",
            },
          },
        ],
      },
      center: [77.5946, 12.9716], // Bengaluru
      zoom: 12,
    });

    // Debug map and tile loading
    map.current.on("load", () => {
      console.log("Map loaded");
      // Log available source data
      const sources = map.current.getStyle().sources;
      Object.keys(sources).forEach((sourceId) => {
        const source = map.current.getSource(sourceId);
        if (source && source.vectorLayerIds) {
          console.log(`Source ${sourceId} layers:`, source.vectorLayerIds);
        }
      });
    });
    map.current.on("error", (e) => {
      console.error("Map error:", JSON.stringify(e));
    });
    map.current.on("sourcedataerror", (e) => {
      console.error("Source error:", JSON.stringify(e));
    });
    map.current.on("sourcedataloading", (e) => {
      console.log("Loading source:", e.sourceId);
    });
    map.current.on("sourcedata", (e) => {
      console.log("Source loaded:", e.sourceId, e.isSourceLoaded);
    });

    const fetchDeliveryData = async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL}/track/${storeId}`,
        );
        const data = await response.json();
        console.log("Fetched data:", data);
        setVehicleData(data);

        map.current.on("load", () => {
          map.current.addSource("route", {
            type: "geojson",
            data: {
              type: "Feature",
              properties: {},
              geometry: data.route.geometry,
            },
          });
          map.current.addLayer({
            id: "route",
            type: "line",
            source: "route",
            layout: { "line-join": "round", "line-cap": "round" },
            paint: { "line-color": "#3b82f6", "line-width": 4 },
          });

          const marker = new maplibregl.Marker()
            .setLngLat([data.vehicle.lng, data.vehicle.lat])
            .addTo(map.current);
          map.current.setCenter([data.vehicle.lng, data.vehicle.lat]);
        });
      } catch (error) {
        console.error("Error fetching delivery data:", error);
      }
    };

    fetchDeliveryData();

    const socket = io(
      process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001",
      {
        transports: ["websocket", "polling"],
      },
    );
    socket.on("connect", () => {
      console.log("Socket.IO connected");
    });
    socket.on("connect_error", (err) => {
      console.error("Socket.IO error:", err.message);
    });
    socket.on("location-update", (data) => {
      console.log("Location update:", data);
      if (data.storeId === storeId) {
        setVehicleData((prev) => ({
          ...prev,
          vehicle: { lat: data.lat, lng: data.lng },
        }));
        if (map.current.getSource("vehicle")) {
          map.current.getSource("vehicle").setData({
            type: "Feature",
            geometry: { type: "Point", coordinates: [data.lng, data.lat] },
          });
        } else {
          map.current.addSource("vehicle", {
            type: "geojson",
            data: {
              type: "Feature",
              geometry: { type: "Point", coordinates: [data.lng, data.lat] },
            },
          });
          map.current.addLayer({
            id: "vehicle",
            type: "circle",
            source: "vehicle",
            paint: { "circle-radius": 8, "circle-color": "#ff0000" },
          });
        }
      }
    });

    return () => {
      socket.disconnect();
      if (map.current) map.current.remove();
    };
  }, [storeId]);

  return (
    <div>
      <h1>Track Delivery for Store {storeId}</h1>
      <div style={{ height: "600px", width: "100%" }} ref={mapContainer} />
      {vehicleData && (
        <div>
          <p>
            Vehicle Location: {vehicleData.vehicle.lat},{" "}
            {vehicleData.vehicle.lng}
          </p>
          <p>ETA: {vehicleData.eta_days} day(s)</p>
        </div>
      )}
    </div>
  );
};

export default TrackPortal;
