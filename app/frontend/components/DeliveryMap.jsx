"use client";
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import io from "socket.io-client";
import "maplibre-gl/dist/maplibre-gl.css";

const DeliveryMap = ({ vehicleId }) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [routeData, setRouteData] = useState(null);

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "vector",
            tiles: [
              "http://localhost:7800/public.planet_osm_roads/{z}/{x}/{y}.pbf",
            ], // Adjust to public.planet_osm_roads if needed
            minzoom: 0,
            maxzoom: 14,
          },
        },
        layers: [
          {
            id: "roads",
            type: "line",
            source: "osm",
            "source-layer": "osm_roads", // Adjust to planet_osm_roads if needed
            paint: {
              "line-color": "#3388ff",
              "line-width": 2,
            },
          },
        ],
      },
      center: [77.5946, 12.9716], // Bengaluru
      zoom: 10,
    });

    // Fetch route data
    const fetchRouteData = async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_URL}/api/route/vehicle/${vehicleId}`,
        );
        const data = await response.json();
        setRouteData(data);

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
            layout: { "line-join": "round", "line-cap": "Round" },
            paint: { "line-color": "#3b82f6", "line-width": 4 },
          });

          const marker = new maplibregl.Marker()
            .setLngLat([data.vehicle.lng, data.vehicle.lat])
            .addTo(map.current);
          map.current.setCenter([data.vehicle.lng, data.vehicle.lat]);
        });
      } catch (error) {
        console.error("Error fetching route:", error);
      }
    };

    fetchRouteData();

    const socket = io(
      process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001",
      {
        transports: ["websocket", "polling"],
      },
    );
    socket.on("location-update", (data) => {
      if (data.vehicleId === vehicleId) {
        setRouteData((prev) => ({
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
  }, [vehicleId]);

  return (
    <div>
      <h1>Delivery Route for Vehicle {vehicleId}</h1>
      <div style={{ height: "600px", width: "100%" }} ref={mapContainer} />
      {routeData && (
        <div>
          <p>
            Vehicle Location: {routeData.vehicle.lat}, {routeData.vehicle.lng}
          </p>
          <p>ETA: {routeData.eta_days} day(s)</p>
        </div>
      )}
    </div>
  );
};

export default DeliveryMap;
