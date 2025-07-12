require("dotenv").config();
const express = require("express");
const cors = require("cors");
const { Pool } = require("pg");
const http = require("http");
const socketIo = require("socket.io");
const axios = require("axios");

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
  password: process.env.DB_PASSWORD || "securepassword",
  port: process.env.DB_PORT || 5432,
});

// const fulfillPool = new Pool({
//   user: process.env.DB_USER || "postgres",
//   host: process.env.DB_HOST || "localhost",
//   database: "postgres",
//   password: process.env.DB_PASSWORD || "220502",
//   port: process.env.DB_PORT || 5432,
// });

pool.connect((err, client, release) => {
  if (err)
    console.error("Database connection error (walmart_db):", err.message);
  else console.log("Database connected successfully (walmart_db)");
  release();
});

// fulfillPool.connect((err, client, release) => {
//   if (err) console.error("Database connection error (postgres):", err.message);
//   else console.log("Database connected successfully (postgres)");
//   release();
// });

app.use(cors({ origin: "http://localhost:3000", credentials: true }));
app.use(express.json());

// SupplySync: Get order list
app.get("/inventory/:storeId", async (req, res) => {
  const { storeId } = req.params;
  try {
    const { rows } = await pool.query(
      `
      SELECT ra.store_id, ra.sku_id, p.name, ra.current_stock, ra.reorder_threshold,
             f.predicted_demand, (f.predicted_demand - ra.current_stock) as quantity
      FROM reorder_alerts ra
      JOIN products p ON ra.sku_id = p.sku_id
      JOIN forecasts f ON ra.store_id = f.store_id AND ra.sku_id = f.sku_id
      JOIN stores s ON ra.store_id = s.store_id
      WHERE (s.store_id::text = $1 OR LOWER(s.store_location) = LOWER($1))
        AND ra.current_stock < ra.reorder_threshold
    `,
      [storeId],
    );
    if (!rows.length) {
      return res
        .status(404)
        .json({ error: `No order list for store: ${storeId}` });
    }
    res.json({
      store_id: rows[0].store_id,
      items: rows.map((r) => ({
        sku_id: r.sku_id,
        name: r.name,
        quantity: Math.ceil(r.quantity),
      })),
    });
  } catch (error) {
    console.error("Inventory error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// SupplySync: Submit verified order
app.post("/submit-order/:storeId", async (req, res) => {
  const { storeId } = req.params;
  const { items } = req.body;
  try {
    const { rows: store } = await pool.query(
      `
      SELECT store_id, lat, lng
      FROM stores
      WHERE store_id::text = $1 OR LOWER(store_location) = LOWER($1)
    `,
      [storeId],
    );
    if (!store.length) {
      return res.status(404).json({ error: `No store found for: ${storeId}` });
    }
    const { store_id, lat, lng } = store[0];

    const assignments = [];
    for (const item of items) {
      const skuMap = {
        1: "SKU001",
        2: "SKU002",
        3: "SKU003",
        4: "SKU004",
        5: "SKU005",
      };
      const response = await axios.post(
        "http://localhost:8000/fulfillment/assign",
        {
          latitude: lat,
          longitude: lng,
          sku: skuMap[item.sku_id],
          quantity: item.quantity,
        },
        { headers: { "Content-Type": "application/json" } },
      );
      const { fulfillment_center_id } = response.data;
      assignments.push({ ...item, dc_id: fulfillment_center_id });

      await pool.query(
        "UPDATE inventory SET current_stock = current_stock - $1 WHERE dc_id = $2 AND sku_id = $3",
        [item.quantity, fulfillment_center_id, item.sku_id],
      );
      await pool.query(
        "INSERT INTO delivery_routes (vehicle_id, dc_id, store_id, sku_id, sequence, distance_km, estimated_time, eta_days, priority_score) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
        [2, fulfillment_center_id, store_id, item.sku_id, 1, 10, 0.5, 1, 0.9],
      );
    }
    res.json({ store_id, assignments });
  } catch (error) {
    console.error("Submit order error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// TrackX: Track store

app.get("/track/:storeId", async (req, res) => {
  const { storeId } = req.params;
  try {
    const { rows: store } = await pool.query(
      `
      SELECT store_id, store_location, lat, lng
      FROM stores
      WHERE LOWER(store_location) = LOWER($1) OR store_id::text = $1
    `,
      [storeId],
    );
    if (!store.length) {
      return res.status(404).json({ error: `No store found for: ${storeId}` });
    }
    const store_id = store[0].store_id;

    const { rows: routes } = await pool.query(
      `
      SELECT dr.vehicle_id, dr.eta_days, dc.latitude as dc_lat, dc.longitude as dc_lng
      FROM delivery_routes dr
      JOIN FulfillmentCenter dc ON dr.dc_id = dc.id
      WHERE dr.store_id = $1
      ORDER BY dr.created_at DESC LIMIT 1
    `,
      [store_id],
    );
    if (!routes.length) {
      return res
        .status(404)
        .json({
          error: `No delivery routes found for store: ${store[0].store_location}`,
        });
    }

    // Proxy to RouteAI for road-based geometry
    const vehicleId = routes[0].vehicle_id;
    let routeData;
    try {
      const response = await axios.get(
        `http://localhost:3002/route/${vehicleId}`,
      );
      routeData = response.data;
      console.log(
        "Track route coordinates count:",
        routeData.route.geometry.coordinates.length,
      );
    } catch (error) {
      console.error(
        "Proxy track error:",
        error.response?.data?.message || error.message,
      );
      // Fallback to basic route
      routeData = {
        route: {
          geometry: {
            type: "LineString",
            coordinates: [
              [routes[0].dc_lng, routes[0].dc_lat],
              [store[0].lng, store[0].lat],
            ],
          },
        },
        vehicle: { lat: store[0].lat, lng: store[0].lng },
        eta_days: routes[0].eta_days,
      };
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
      route: { geometry: routeData.route.geometry },
      vehicle: {
        lat: tracking.length ? tracking[0].latitude : routeData.vehicle.lat,
        lng: tracking.length ? tracking[0].longitude : routeData.vehicle.lng,
      },
      dc: { lat: routes[0].dc_lat, lng: routes[0].dc_lng },
      eta_days: routeData.eta_days,
    });
  } catch (error) {
    console.error("Track store error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// Proxy RouteAI: Optimize routes
app.get("/optimize-routes", async (req, res) => {
  try {
    const response = await axios.get("http://localhost:3002/optimize-routes", {
      headers: { Authorization: `Bearer ${process.env.ORS_API_KEY}` },
    });
    res.json(response.data);
  } catch (error) {
    console.error("Proxy optimize-routes error:", error.message);
    res.status(error.response?.status || 500).json({ error: error.message });
  }
});

// Proxy RouteAI: Get route details
app.get("/route/:vehicleId", async (req, res) => {
  const { vehicleId } = req.params;
  try {
    const response = await axios.get(
      `http://localhost:3002/route/${vehicleId}`,
    );
    res.json(response.data);
  } catch (error) {
    console.error("Proxy route details error:", error.message);
    res.status(error.response?.status || 500).json({ error: error.message });
  }
});

io.on("connection", (socket) => {
  console.log("Socket.IO client connected");
  socket.on("update-location", async (data) => {
    const { vehicleId, storeId, lat, lng } = data;
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
        storeId: storeId || rows[0]?.store_location,
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
  console.log(`SupplySync server running on http://localhost:3001`),
);
