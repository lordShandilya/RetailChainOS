const express = require("express");
const axios = require("axios");
const { Pool } = require("pg");
const cors = require("cors");
require("dotenv").config();

const app = express();
app.use(
  cors({
    origin: ["http://localhost:3000", "http://localhost:3001"],
    methods: ["GET", "POST"],
    credentials: true,
  }),
);
app.use(express.json());

const pool = new Pool({
  user: process.env.DB_USER || "walmart_user",
  host: process.env.DB_HOST || "localhost",
  database: process.env.DB_NAME || "walmart_db",
  password: process.env.DB_PASSWORD || "securepassword",
  port: process.env.DB_PORT || 5432,
});

const haversineDistance = (lat1, lon1, lat2, lon2) => {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

app.get("/route/:vehicleId", async (req, res) => {
  const { vehicleId } = req.params;
  try {
    const { rows } = await pool.query(
      `
         SELECT dr.*, s.lat, s.lng, dc.latitude as dc_lat, dc.longitude as dc_lng
         FROM delivery_routes dr
         JOIN stores s ON dr.store_id = s.store_id
         LEFT JOIN FulfillmentCenter dc ON dr.dc_id = dc.id
         WHERE dr.vehicle_id = $1
         ORDER BY dr.sequence
       `,
      [vehicleId],
    );
    if (!rows.length) {
      console.error(`No routes found for vehicle ${vehicleId}`);
      return res
        .status(404)
        .json({ error: `No routes for vehicle ${vehicleId}` });
    }

    // Build coordinates: DC -> stores
    const coordinates = [
      [rows[0].dc_lng || 77.5946, rows[0].dc_lat || 12.9716], // Fallback to Bengaluru
      ...rows.map((r) => [r.lng, r.lat]),
    ];
    const validCoords = coordinates.every(
      ([lng, lat]) =>
        typeof lng === "number" &&
        typeof lat === "number" &&
        lng >= -180 &&
        lng <= 180 &&
        lat >= -90 &&
        lat <= 90,
    );
    if (!validCoords) {
      console.error("Invalid coordinates:", coordinates);
      return res
        .status(422)
        .json({ error: "Invalid coordinates in route data" });
    }

    let routeGeometry = { type: "LineString", coordinates };
    let etaDays = rows[0].eta_days || 1;
    let distanceKm = 0;

    const mapboxToken = process.env.MAPBOX_TOKEN;
    if (!mapboxToken) {
      console.warn("Mapbox access token missing, using linear route");
      return res.status(200).json({
        route: routeGeometry,
        vehicle: { lat: coordinates[0][1], lng: coordinates[0][0] },
        eta_days: etaDays,
        distance_km: distanceKm,
      });
    }

    const mapboxUrl = `https://api.mapbox.com/directions/v5/mapbox/driving/${coordinates.map((c) => c.join(",")).join(";")}?geometries=geojson&access_token=${mapboxToken}`;
    console.log("Mapbox URL:", mapboxUrl);
    try {
      const mapboxResponse = await axios.get(mapboxUrl);
      console.log(
        "Mapbox response:",
        JSON.stringify(mapboxResponse.data, null, 2),
      );
      if (!mapboxResponse.data.routes || !mapboxResponse.data.routes[0]) {
        console.error("Mapbox API returned no routes:", mapboxResponse.data);
        throw new Error("No routes returned by Mapbox");
      }
      routeGeometry = mapboxResponse.data.routes[0].geometry;
      const durationSeconds = mapboxResponse.data.routes[0].duration || 0;
      distanceKm = (mapboxResponse.data.routes[0].distance || 0) / 1000; // Convert meters to km
      etaDays = Math.max(1, Math.ceil(durationSeconds / (24 * 3600)));
    } catch (error) {
      console.error(
        "Mapbox API error:",
        error.response?.data?.message || error.message,
      );
      console.warn("Falling back to linear route due to Mapbox error");
    }

    const { rows: tracking } = await pool.query(
      `
         SELECT latitude, longitude
         FROM tracking_logs
         WHERE vehicle_id = $1
         ORDER BY timestamp DESC LIMIT 1
       `,
      [vehicleId],
    );

    res.json({
      route: { geometry: routeGeometry },
      vehicle: {
        lat: tracking.length ? tracking[0].latitude : coordinates[0][1],
        lng: tracking.length ? tracking[0].longitude : coordinates[0][0],
      },
      eta_days: etaDays,
      distance_km: distanceKm,
    });
  } catch (error) {
    console.error("Route error:", error.message);
    res.status(500).json({ error: `Route error: ${error.message}` });
  }
});

app.get("/optimize-routes", async (req, res) => {
  try {
    const { rows: alerts } = await pool.query(`
         SELECT ra.store_id, ra.priority_score, s.lat, s.lng
         FROM reorder_alerts ra
         JOIN stores s ON ra.store_id = s.store_id
         WHERE ra.current_stock < ra.reorder_threshold
       `);
    const { rows: dc } = await pool.query(`
         SELECT id, latitude as lat, longitude as lng
         FROM FulfillmentCenter
         WHERE id = 1
       `);

    const clusters = [];
    const visited = new Set();
    for (const alert of alerts) {
      if (visited.has(alert.store_id)) continue;
      const cluster = [alert];
      visited.add(alert.store_id);
      for (const other of alerts) {
        if (visited.has(other.store_id)) continue;
        const distance = haversineDistance(
          alert.lat,
          alert.lng,
          other.lat,
          other.lng,
        );
        if (distance <= 50) {
          cluster.push(other);
          visited.add(other.store_id);
        }
      }
      clusters.push(cluster);
    }

    clusters.sort((a, b) => {
      const maxPriorityA = Math.max(...a.map((alert) => alert.priority_score));
      const maxPriorityB = Math.max(...b.map((alert) => alert.priority_score));
      return maxPriorityB - maxPriorityA;
    });

    const route = [];
    let current = { lat: dc[0].lat, lng: dc[0].lng };
    for (const cluster of clusters) {
      for (const store of cluster) {
        route.push({
          store_id: store.store_id,
          lat: store.lat,
          lng: store.lng,
        });
      }
    }

    const coordinates = [
      [current.lng, current.lat],
      ...route.map((r) => [r.lng, r.lat]),
    ];
    const mapboxToken = process.env.MAPBOX_TOKEN;
    let routeGeometry = { type: "LineString", coordinates };
    let distanceKm = 0;

    if (mapboxToken) {
      const mapboxUrl = `https://api.mapbox.com/directions/v5/mapbox/driving/${coordinates.map((c) => c.join(",")).join(";")}?geometries=geojson&access_token=${mapboxToken}`;
      console.log("Mapbox optimize-routes URL:", mapboxUrl);
      try {
        const mapboxResponse = await axios.get(mapboxUrl);
        console.log(
          "Mapbox optimize-routes response:",
          JSON.stringify(mapboxResponse.data, null, 2),
        );
        routeGeometry =
          mapboxResponse.data.routes[0]?.geometry || routeGeometry;
        distanceKm = (mapboxResponse.data.routes[0]?.distance || 0) / 1000;
      } catch (error) {
        console.error(
          "Mapbox API error:",
          error.response?.data?.message || error.message,
        );
        console.warn("Falling back to linear route for optimize-routes");
      }
    } else {
      console.warn(
        "Mapbox access token missing, using linear route for optimize-routes",
      );
    }

    res.json({
      routes: route.map((r, index) => ({
        store_id: r.store_id,
        sequence: index + 1,
        geometry: routeGeometry,
        distance_km: distanceKm,
      })),
    });
  } catch (error) {
    console.error("Optimize routes error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

app.listen(3002, () =>
  console.log("RouteAI server running on http://localhost:3002"),
);
