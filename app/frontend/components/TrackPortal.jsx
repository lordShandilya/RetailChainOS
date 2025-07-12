"use client";
import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import io from "socket.io-client";
import "mapbox-gl/dist/mapbox-gl.css";
import { useRouter } from "next/navigation";

const TrackPortal = ({ storeId }) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const popupRef = useRef(null);
  const [routeData, setRouteData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    if (!process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
      setError("Mapbox access token is missing in frontend");
      console.error("Error: NEXT_PUBLIC_MAPBOX_TOKEN is not set in .env.local");
      setLoading(false);
      return;
    }
    console.log(
      "Frontend Mapbox token:",
      process.env.NEXT_PUBLIC_MAPBOX_TOKEN.substring(0, 10) + "...",
    );

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: [80.2707, 13.0827], // Chennai
      zoom: 10,
    });

    map.current.on("load", () => {
      console.log("Map loaded");
      // Initialize sources
      if (!map.current.getSource("vehicle")) {
        map.current.addSource("vehicle", {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: { type: "Point", coordinates: [0, 0] }, // Placeholder
          },
        });
      }
      if (!map.current.getSource("route")) {
        map.current.addSource("route", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: [] },
          },
        });
      }

      map.current.loadImage("/truck.png", (error, image) => {
        if (error) {
          console.error("Error loading truck icon:", error.message);
          setError("Failed to load truck icon, using fallback");
          map.current.addLayer({
            id: "vehicle",
            type: "circle",
            source: "vehicle",
            paint: {
              "circle-radius": 8,
              "circle-color": "#ff0000",
              "circle-opacity": 0.9,
              "circle-stroke-width": 2,
              "circle-stroke-color": "#ffffff",
            },
          });
          return;
        }
        map.current.addImage("truck", image);
        map.current.addLayer({
          id: "vehicle",
          type: "symbol",
          source: "vehicle",
          layout: {
            "icon-image": "truck",
            "icon-size": 0.8,
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
            "icon-anchor": "bottom",
          },
        });
        map.current.getCanvas().style.cursor = "pointer";
        map.current.on("mouseenter", "vehicle", () => {
          map.current.setLayoutProperty("vehicle", "icon-size", 0.9);
        });
        map.current.on("mouseleave", "vehicle", () => {
          map.current.setLayoutProperty("vehicle", "icon-size", 0.8);
        });
      });
      map.current.addLayer({
        id: "route",
        type: "line",
        source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": "#1e90ff",
          "line-width": 8,
          "line-opacity": 0.9,
        },
      });
      map.current.addControl(new mapboxgl.NavigationControl());
      map.current.resize();
    });

    map.current.on("error", (e) => {
      console.error("Map error:", e.error?.message || JSON.stringify(e));
      setError(`Map failed to load: ${e.error?.message || e.message}`);
      setLoading(false);
    });

    const fetchRouteData = async (retryCount = 3, delay = 1000) => {
      try {
        setLoading(true);
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001"}/track/${storeId}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        const data = await response.json();
        console.log("Fetched track data:", JSON.stringify(data, null, 2));
        if (data.error) {
          setError(data.error);
          setLoading(false);
          return;
        }
        if (!data.vehicle || !data.vehicle.lat || !data.vehicle.lng) {
          setError("Invalid vehicle data received");
          setLoading(false);
          return;
        }
        console.log(
          "Route coordinates count:",
          data.route.geometry.coordinates.length,
        );
        setRouteData(data);
        setError(null);
        setLoading(false);

        if (map.current.isStyleLoaded()) {
          addMapLayers(data);
        } else {
          map.current.on("load", () => addMapLayers(data));
        }
      } catch (error) {
        console.error("Error fetching track:", error.message);
        if (retryCount > 0) {
          console.log(`Retrying fetch (${retryCount} attempts left)...`);
          setTimeout(() => fetchRouteData(retryCount - 1, delay * 2), delay);
        } else {
          setError("Failed to fetch track data: " + error.message);
          setLoading(false);
        }
      }
    };

    const addMapLayers = (data) => {
      // Update route source
      map.current.getSource("route").setData({
        type: "Feature",
        properties: {},
        geometry: data.route.geometry,
      });

      // Update vehicle source
      map.current.getSource("vehicle").setData({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [data.vehicle.lng, data.vehicle.lat],
        },
      });

      if (popupRef.current) {
        popupRef.current.remove();
      }
      popupRef.current = new mapboxgl.Popup({ closeOnClick: false, offset: 25 })
        .setLngLat([data.vehicle.lng, data.vehicle.lat])
        .setHTML(
          `<div style="background: rgba(255, 255, 255, 0.95); padding: 10px; border-radius: 6px; box-shadow: 0 0 10px rgba(0,0,0,0.3); font-family: Arial;">
             <h3 style="margin: 0; font-size: 16px; color: #111;">Store ${storeId}</h3>
             <p style="margin: 5px 0; font-size: 14px; color: #111;">ETA: ${data.eta_days} day(s)</p>
             <p style="margin: 0; font-size: 14px; color: #111;">Lat: ${data.vehicle.lat.toFixed(4)}, Lng: ${data.vehicle.lng.toFixed(4)}</p>
           </div>`,
        )
        .addTo(map.current);

      map.current.setCenter([data.vehicle.lng, data.vehicle.lat]);
      map.current.setZoom(10);
      map.current.resize();

      if (data.route.geometry.coordinates.length > 1) {
        animateVehicle(data.route.geometry.coordinates);
      }
    };

    const animateVehicle = (coordinates) => {
      let step = 0;
      const steps = coordinates.length;
      const animate = () => {
        if (step < steps) {
          const [lng, lat] = coordinates[step];
          map.current.getSource("vehicle").setData({
            type: "Feature",
            geometry: { type: "Point", coordinates: [lng, lat] },
          });
          if (popupRef.current) {
            popupRef.current.setLngLat([lng, lat]);
          }
          map.current.setCenter([lng, lat]);
          step++;
          setTimeout(animate, 1000);
        }
      };
      animate();
    };

    fetchRouteData();

    const socket = io(
      process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001",
      {
        transports: ["websocket", "polling"],
        auth: { token },
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
      if (data.storeId === storeId || data.storeId === String(storeId)) {
        setRouteData((prev) => ({
          ...prev,
          vehicle: { lat: data.lat, lng: data.lng },
        }));
        map.current.getSource("vehicle").setData({
          type: "Feature",
          geometry: { type: "Point", coordinates: [data.lng, data.lat] },
        });
        map.current.setCenter([data.lng, data.lat]);
        if (popupRef.current) {
          popupRef.current.setLngLat([data.lng, data.lat]).setHTML(
            `<div style="background: rgba(255, 255, 255, 0.95); padding: 10px; border-radius: 6px; box-shadow: 0 0 10px rgba(0,0,0,0.3); font-family: Arial;">
               <h3 style="margin: 0; font-size: 16px; color: #111;">Store ${storeId}</h3>
               <p style="margin: 5px 0; font-size: 14px; color: #111;">ETA: ${routeData?.eta_days || "N/A"} day(s)</p>
               <p style="margin: 0; font-size: 14px; color: #111;">Lat: ${data.lat.toFixed(4)}, Lng: ${data.lng.toFixed(4)}</p>
             </div>`,
          );
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
  }, [storeId, router]);

  return (
    <div>
      <h1>Track Delivery for Store {storeId}</h1>
      {loading && <p>Loading map...</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      <div style={{ height: "600px", width: "100%" }} ref={mapContainer} />
      {routeData && routeData.vehicle && !loading && (
        <div>
          <p>
            Vehicle Location: {routeData.vehicle.lat.toFixed(4)},{" "}
            {routeData.vehicle.lng.toFixed(4)}
          </p>
          <p>ETA: {routeData.eta_days} day(s)</p>
        </div>
      )}
    </div>
  );
};

export default TrackPortal;
