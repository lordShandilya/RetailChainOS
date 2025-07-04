require("dotenv").config();
const express = require("express");
const cors = require("cors");
const { Pool } = require("pg");
const http = require("http");
const socketIo = require("socket.io");
const axios = require("axios");
const _ = require("lodash");

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "http://localhost:3000",
    methods: ["GET", "POST"],
    credentials: true,
  },
});
const pool = new Pool({
  user: process.env.DB_USER || "walmart_user",
  host: process.env.DB_HOST || "localhost",
  database: process.env.DB_NAME || "walmart_db",
  password: process.env.DB_PASSWORD,
  port: process.env.DB_PORT || 5432,
});

app.use(cors({ origin: "http://localhost:3000", credentials: true }));
app.use(express.json());

// Simple DBSCAN for clustering stores within 10 km
function dbscan(stops, epsKm = 10, minPts = 2) {
  const clusters = [];
  const visited = new Set();
  const toRadians = (deg) => (deg * Math.PI) / 180;
  const haversine = (p1, p2) => {
    const R = 6371;
    const dLat = toRadians(p2.lat - p1.lat);
    const dLng = toRadians(p2.lng - p1.lng);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRadians(p1.lat)) *
        Math.cos(toRadians(p2.lat)) *
        Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  };

  stops.forEach((point, i) => {
    if (visited.has(i)) return;
    visited.add(i);
    const neighbors = stops.reduce((acc, p, j) => {
      if (i !== j && haversine(point, p) <= epsKm) acc.push(j);
      return acc;
    }, []);

    if (neighbors.length >= minPts - 1) {
      const cluster = [point];
      neighbors.forEach((j) => {
        if (!visited.has(j)) {
          visited.add(j);
          cluster.push(stops[j]);
        }
      });
      clusters.push(cluster);
    }
  });

  const noise = stops.filter((_, i) => !visited.has(i));
  return { clusters, noise };
}

// Optimize routes
app.get("/optimize-routes", async (req, res) => {
  try {
    const { rows: alerts } = await pool.query(`
      SELECT ra.*, s.store_location, s.store_address, s.lat, s.lng
      FROM reorder_alerts ra
      JOIN stores s ON ra.store_id = s.store_id
      WHERE ra.reorder_threshold > ra.current_stock
    `);
    if (!alerts.length) {
      console.error("No reorder alerts found");
      return res.status(400).json({
        error: "No reorder alerts found, ensure seed_data.py ran successfully",
      });
    }
    const stops = alerts.map((alert) => ({
      store_id: alert.store_id,
      store_location: alert.store_location,
      store_address: alert.store_address,
      lat: alert.lat,
      lng: alert.lng,
      demand: alert.reorder_threshold - alert.current_stock,
      priority: alert.priority_score,
    }));

    // Cluster stores within 10 km
    const { clusters, noise } = dbscan(stops, 10, 2);

    // Calculate routes for clusters and isolated stops
    const routes = [];
    let totalDistance = 0;
    let totalTime = 0;
    const origin = { lat: 13.1, lng: 77.6 }; // Bengaluru DC

    // Process clusters
    for (const cluster of clusters) {
      const coordinates = [
        [origin.lng, origin.lat],
        ...cluster.map((s) => [s.lng, s.lat]),
      ];
      try {
        const response = await axios.post(
          "https://api.openrouteservice.org/v2/directions/driving-hgv",
          { coordinates, units: "km", geometry: true },
          {
            headers: {
              Authorization: `Bearer ${process.env.ORS_API_KEY}`,
              "Content-Type": "application/json",
              Accept: "application/json",
            },
          },
        );
        const path = response.data.routes[0];
        totalDistance += path.summary.distance;
        totalTime += path.summary.duration / 3600;
        routes.push({
          stops: cluster,
          distance_km: path.summary.distance,
          time_hours: path.summary.duration / 3600,
          geometry: path.geometry,
          priority: _.mean(cluster.map((s) => s.priority)),
        });
      } catch (error) {
        console.error(`ORS error for cluster: ${error.message}`);
      }
    }

    // Process isolated stops
    for (const stop of noise) {
      const coordinates = [
        [origin.lng, origin.lat],
        [stop.lng, stop.lat],
      ];
      try {
        const response = await axios.post(
          "https://api.openrouteservice.org/v2/directions/driving-hgv",
          { coordinates, units: "km", geometry: true },
          {
            headers: {
              Authorization: `Bearer ${process.env.ORS_API_KEY}`,
              "Content-Type": "application/json",
              Accept: "application/json",
            },
          },
        );
        const path = response.data.routes[0];
        totalDistance += path.summary.distance;
        totalTime += path.summary.duration / 3600;
        routes.push({
          stops: [stop],
          distance_km: path.summary.distance,
          time_hours: path.summary.duration / 3600,
          geometry: path.geometry,
          priority: stop.priority,
        });
      } catch (error) {
        console.error(
          `ORS error for stop ${stop.store_location}: ${error.message}`,
        );
      }
    }

    // Clear previous routes
    await pool.query("DELETE FROM delivery_routes WHERE vehicle_id = $1", [2]);

    // Insert routes into database
    for (const [i, route] of routes.entries()) {
      for (const [j, stop] of route.stops.entries()) {
        await pool.query(
          "INSERT INTO delivery_routes (vehicle_id, sku_id, store_id, sequence, distance_km, estimated_time, eta_days, priority_score, lat, lng) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
          [
            2,
            1,
            stop.store_id,
            i * 10 + j,
            route.distance_km,
            route.time_hours,
            Math.ceil(route.time_hours / 24),
            route.priority,
            stop.lat,
            stop.lng,
          ],
        );
      }
    }

    // Insert tracking log
    await pool.query(
      "INSERT INTO tracking_logs (vehicle_id, latitude, longitude, timestamp) VALUES ($1, $2, $3, NOW())",
      [2, origin.lat, origin.lng],
    );

    // Calculate metrics
    await pool.query(
      "INSERT INTO logistics_metrics (run_date, total_distance_km, total_fuel_cost, total_co2_kg) VALUES ($1, $2, $3, $4)",
      [new Date(), totalDistance, totalDistance * 0.1, totalDistance * 0.2],
    );

    res.json({
      vehicleId: 2,
      routes,
      total_distance_km: totalDistance,
      total_fuel_cost: totalDistance * 0.1,
      total_co2_kg: totalDistance * 0.2,
      eta_days: Math.ceil(totalTime / 24),
    });
  } catch (error) {
    console.error("Optimize routes error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// Route details
app.get("/route/:vehicleId", async (req, res) => {
  const { vehicleId } = req.params;
  try {
    const { rows } = await pool.query(
      `
      SELECT dr.*, s.store_location
      FROM delivery_routes dr
      JOIN stores s ON dr.store_id = s.store_id
      WHERE dr.vehicle_id = $1
      ORDER BY dr.sequence
    `,
      [vehicleId],
    );
    if (!rows.length) {
      console.error("No routes found for vehicle:", vehicleId);
      return res.status(404).json({ error: "No routes found for vehicle" });
    }
    res.json({
      route: {
        geometry: {
          type: "LineString",
          coordinates: rows.map((r) => [r.lng, r.lat]),
        },
      },
      vehicle: { lat: rows[0].lat, lng: rows[0].lng },
      eta_days: rows[0].eta_days,
    });
  } catch (error) {
    console.error("Route details error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// Track store
app.get("/track/:storeId", async (req, res) => {
  const { storeId } = req.params;
  try {
    const { rows: routes } = await pool.query(
      `
      SELECT dr.*, s.store_location, s.lat, s.lng
      FROM delivery_routes dr
      JOIN stores s ON dr.store_id = s.store_id
      WHERE s.store_location = $1
      ORDER BY dr.created_at DESC LIMIT 1
    `,
      [storeId],
    );
    if (!routes.length) {
      console.error("No delivery routes found for store:", storeId);
      return res
        .status(404)
        .json({ error: `No delivery routes found for store: ${storeId}` });
    }
    const { rows: tracking } = await pool.query(
      "SELECT latitude, longitude FROM tracking_logs WHERE vehicle_id = $1 ORDER BY timestamp DESC LIMIT 1",
      [routes[0].vehicle_id],
    );
    if (!tracking.length) {
      console.error(
        "No tracking logs found for vehicle:",
        routes[0].vehicle_id,
      );
      return res.status(404).json({
        error: `No tracking logs found for vehicle: ${routes[0].vehicle_id}`,
      });
    }
    res.json({
      route: {
        geometry: {
          type: "LineString",
          coordinates: routes.map((r) => [r.lng, r.lat]),
        },
      },
      vehicle: {
        lat: tracking[0].latitude,
        lng: tracking[0].longitude,
      },
      eta_days: routes[0].eta_days,
    });
  } catch (error) {
    console.error("Track store error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

io.on("connection", (socket) => {
  console.log("Socket.IO client connected");
  socket.on("update-location", async (data) => {
    const { vehicleId, lat, lng } = data;
    try {
      await pool.query(
        "INSERT INTO tracking_logs (vehicle_id, latitude, longitude, timestamp) VALUES ($1, $2, $3, NOW())",
        [vehicleId, lat, lng],
      );
      const { rows } = await pool.query(
        `
        SELECT s.store_location
        FROM delivery_routes dr
        JOIN stores s ON dr.store_id = s.store_id
        WHERE dr.vehicle_id = $1
        ORDER BY dr.sequence DESC LIMIT 1
      `,
        [vehicleId],
      );
      io.emit("location-update", {
        storeId: rows[0]?.store_location,
        lat,
        lng,
        vehicleId,
      });
    } catch (error) {
      console.error("Socket update-location error:", error.message);
    }
  });
});

server.listen(3001, () =>
  console.log(
    `Server running on ${process.env.BACKEND_URL || "http://localhost:3001"}`,
  ),
);
