"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import axios from "axios";
import io from "socket.io-client";
import { useRouter } from "next/navigation";
import "mapbox-gl/dist/mapbox-gl.css";

const DeliveryMap = ({ vehicleId }) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [vehicleLocation, setVehicleLocation] = useState(null);
  const [eta, setEta] = useState(null);
  const [distance, setDistance] = useState(null);
  const [error, setError] = useState(null);
  const router = useRouter();

  const fetchRouteData = async (mapInstance, token) => {
    try {
      if (
        !mapInstance ||
        !mapInstance.getSource("route") ||
        !mapInstance.getSource("vehicle")
      ) {
        console.error("Map or sources not ready, retrying in 500ms");
        setTimeout(() => fetchRouteData(mapInstance, token), 500);
        return;
      }
      const response = await axios.get(
        `http://localhost:3001/route/${vehicleId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      console.log(
        "DeliveryMap fetchRouteData response:",
        JSON.stringify(response.data, null, 2),
      );
      const { vehicle, route, eta_days, distance_km } = response.data;
      if (
        !route?.geometry?.coordinates ||
        route.geometry.coordinates.length < 2
      ) {
        throw new Error("Invalid route geometry");
      }
      setVehicleLocation([vehicle.lng, vehicle.lat]);
      setEta(eta_days);
      setDistance(distance_km);
      console.log("Setting route geometry:", route.geometry);
      mapInstance.getSource("route").setData({
        type: "Feature",
        properties: {},
        geometry: route.geometry,
      });
      mapInstance.getSource("vehicle").setData({
        type: "Feature",
        properties: {},
        geometry: { type: "Point", coordinates: [vehicle.lng, vehicle.lat] },
      });
      try {
        mapInstance.fitBounds(route.geometry.coordinates, {
          padding: 50,
          maxZoom: 10,
        });
      } catch (boundsError) {
        console.error("fitBounds error:", boundsError.message);
        mapInstance.flyTo({ center: [vehicle.lng, vehicle.lat], zoom: 8 });
      }
    } catch (err) {
      console.error(
        "DeliveryMap fetch error:",
        err.response?.data || err.message,
      );
      setError(err.response?.data?.error || "Failed to fetch route");
    }
  };

  const handleStart = () => {
    console.log(
      `Start button clicked for vehicle_id=${vehicleId}. Stocks are out for delivery.`,
    );
    // Placeholder for future backend integration
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    if (!process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
      setError("Mapbox token missing in frontend");
      console.error("NEXT_PUBLIC_MAPBOX_TOKEN is not set");
      return;
    }

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    try {
      map.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: "mapbox://styles/mapbox/streets-v12",
        center: [80.2707, 13.0827], // Default: Chennai
        zoom: 5,
      });
    } catch (mapError) {
      setError("Failed to initialize map");
      console.error("Map initialization error:", mapError.message);
      return;
    }

    map.current.on("load", () => {
      console.log("Map loaded, adding sources and layers");
      try {
        map.current.addSource("route", {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: { type: "LineString", coordinates: [] },
          },
        });
        map.current.addSource("vehicle", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "Point", coordinates: [] },
          },
        });
        map.current.addLayer({
          id: "route",
          type: "line",
          source: "route",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": "#FF4500",
            "line-width": 8,
            "line-opacity": 0.9,
          },
        });
        map.current.loadImage("/truck.png", (error, image) => {
          if (error || !map.current) {
            console.error("Error loading truck icon:", error);
            setError("Failed to load vehicle icon, using default");
            map.current.addLayer({
              id: "vehicle",
              type: "symbol",
              source: "vehicle",
              layout: {
                "icon-image": "marker-15",
                "icon-size": 1.5,
                "icon-allow-overlap": true,
              },
            });
            fetchRouteData(map.current, token);
            return;
          }
          map.current.addImage("truck-icon", image);
          map.current.addLayer({
            id: "vehicle",
            type: "symbol",
            source: "vehicle",
            layout: {
              "icon-image": "truck-icon",
              "icon-size": 0.8,
              "icon-allow-overlap": true,
            },
          });
          fetchRouteData(map.current, token);
        });
      } catch (layerError) {
        console.error("Error adding sources/layers:", layerError.message);
        setError("Failed to initialize map layers");
      }
    });

    map.current.on("error", (e) => {
      console.error("Mapbox error:", e.error.message);
      setError("Mapbox error: " + e.error.message);
    });

    const socket = io("http://localhost:3001");
    socket.on("connect", () => {
      socket.emit("join", { vehicleId, token });
    });
    socket.on("location-update", (data) => {
      if (data.vehicleId === vehicleId && map.current.getSource("vehicle")) {
        console.log("Socket location-update:", data);
        map.current.getSource("vehicle").setData({
          type: "Feature",
          properties: {},
          geometry: { type: "Point", coordinates: [data.lng, data.lat] },
        });
        setVehicleLocation([data.lng, data.lat]);
        map.current.panTo([data.lng, data.lat]);
      }
    });
    socket.on("error", (err) => setError(err.error));

    return () => {
      socket.disconnect();
      if (map.current) map.current.remove();
    };
  }, [vehicleId, router]);

  return (
    <div className="min-h-screen p-6" data-theme="nord">
      {error && <div className="alert alert-error glass mb-4">{error}</div>}
      <div className="card bg-base-100 shadow-xl glass">
        <div className="card-body">
          <h2 className="card-title">Delivery Route for Vehicle {vehicleId}</h2>
          {eta && <p className="text-lg">Estimated Delivery: {eta} days</p>}
          {distance && <p className="text-lg">Distance: {distance} km</p>}
          <button className="btn btn-primary btn-sm mb-4" onClick={handleStart}>
            Start
          </button>
          <div ref={mapContainer} className="h-[600px] w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
};

export default DeliveryMap;
