// components/DeliveryMap.jsx
"use client";
import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import io from "socket.io-client";
import "mapbox-gl/dist/mapbox-gl.css";

const DeliveryMap = ({ vehicleId }) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [routeData, setRouteData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
      setError("Mapbox access token is missing");
      console.error("Error: NEXT_PUBLIC_MAPBOX_TOKEN is not set in .env.local");
      return;
    }

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: [80.2707, 13.0827], // Chennai
      zoom: 10,
    });

    map.current.on("load", () => {
      console.log("Map loaded");
      map.current.resize();
    });
    map.current.on("error", (e) => {
      console.error("Map error:", JSON.stringify(e));
      setError("Map failed to load: " + e.message);
    });

    const fetchRouteData = async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001"}/route/${vehicleId}`,
        );
        const data = await response.json();
        console.log("Fetched data:", JSON.stringify(data, null, 2));
        if (data.error) {
          setError(data.error);
          return;
        }
        if (!data.vehicle || !data.vehicle.lat || !data.vehicle.lng) {
          setError("Invalid vehicle data received");
          return;
        }
        setRouteData(data);
        setError(null);

        if (map.current.isStyleLoaded()) {
          addMapLayers(data);
        } else {
          map.current.on("load", () => addMapLayers(data));
        }
      } catch (error) {
        console.error("Error fetching route:", error.message);
        setError("Failed to fetch route data: " + error.message);
      }
    };

    const addMapLayers = (data) => {
      if (!map.current.getSource("route")) {
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
      } else {
        map.current.getSource("route").setData({
          type: "Feature",
          properties: {},
          geometry: data.route.geometry,
        });
      }

      if (!map.current.getSource("vehicle")) {
        map.current.addSource("vehicle", {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: {
              type: "Point",
              coordinates: [data.vehicle.lng, data.vehicle.lat],
            },
          },
        });
        map.current.addLayer({
          id: "vehicle",
          type: "circle",
          source: "vehicle",
          paint: { "circle-radius": 8, "circle-color": "#ff0000" },
        });
      } else {
        map.current.getSource("vehicle").setData({
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [data.vehicle.lng, data.vehicle.lat],
          },
        });
      }
      map.current.setCenter([data.vehicle.lng, data.vehicle.lat]);
      map.current.resize();
    };

    fetchRouteData();

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
      setError("Socket.IO connection failed: " + err.message);
    });
    socket.on("location-update", (data) => {
      console.log("Location update:", data);
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
          map.current.resize();
        }
      }
    });

    return () => {
      socket.disconnect();
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [vehicleId]);

  return (
    <div>
      <h1>Delivery Route for Vehicle {vehicleId}</h1>
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      <div style={{ height: "600px", width: "100%" }} ref={mapContainer} />
      {routeData && routeData.vehicle && (
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
