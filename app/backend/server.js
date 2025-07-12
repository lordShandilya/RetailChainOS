const express = require("express");
const jwt = require("jsonwebtoken");
const bcrypt = require("bcrypt");
const { Pool } = require("pg");
const dotenv = require("dotenv");
const axios = require("axios");
const cors = require("cors");
const socketIo = require("socket.io");
const http = require("http");

dotenv.config();

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: { origin: "http://localhost:3000", methods: ["GET", "POST"] },
});

const pool = new Pool({
  user: "walmart_user",
  host: "localhost",
  database: "walmart_db",
  password: process.env.DB_USER_PASSWORD || "securepassword",
  port: 5432,
});

app.use(cors());
app.use(express.json());

function authenticate(allowedRoles) {
  return async (req, res, next) => {
    const token = req.headers.authorization?.split(" ")[1];
    if (!token) {
      console.error("Authentication error: No token provided");
      return res.status(401).json({ error: "No token provided" });
    }
    try {
      const decoded = jwt.verify(
        token,
        process.env.JWT_SECRET || "your_jwt_secret",
      );
      console.log("Decoded token:", decoded);
      const { rows } = await pool.query(
        "SELECT * FROM users WHERE username = $1",
        [decoded.username],
      );
      if (!rows.length) {
        console.error(
          "Authentication error: User not found for username:",
          decoded.username,
        );
        return res.status(401).json({ error: "Invalid token" });
      }
      const user = rows[0];
      if (!allowedRoles.includes(user.role)) {
        console.error("Authentication error: Unauthorized role:", user.role);
        return res.status(403).json({ error: "Unauthorized role" });
      }
      req.user = user;
      next();
    } catch (error) {
      console.error("Authentication error:", error.message);
      return res.status(401).json({ error: "Invalid token" });
    }
  };
}

app.post("/login", async (req, res) => {
  const { username, password } = req.body;
  try {
    const { rows } = await pool.query(
      "SELECT * FROM users WHERE username = $1",
      [username],
    );
    if (!rows.length) {
      console.error("Login error: User not found:", username);
      return res.status(401).json({ error: "Invalid credentials" });
    }
    const user = rows[0];
    const match = await bcrypt.compare(password, user.password);
    if (!match) {
      console.error("Login error: Password mismatch for user:", username);
      return res.status(401).json({ error: "Invalid credentials" });
    }
    const token = jwt.sign(
      {
        username: user.username,
        role: user.role,
        store_id: user.store_id,
        vehicle_id: user.vehicle_id,
      },
      process.env.JWT_SECRET || "your_jwt_secret",
      { expiresIn: "1h" },
    );
    console.log("Generated token for user:", username);
    res.json({
      token,
      role: user.role,
      store_id: user.store_id,
      vehicle_id: user.vehicle_id,
    });
  } catch (error) {
    console.error("Login error:", error.message);
    res.status(500).json({ error: error.message });
  }
});
// SupplySync: Get order list

app.get(
  "/inventory/:storeId",
  authenticate(["store_owner"]),
  async (req, res) => {
    const { storeId } = req.params;
    try {
      const { rows } = await pool.query(
        `
      SELECT DISTINCT ra.store_id, ra.sku_id, p.name, ra.current_stock, ra.reorder_threshold,
             f.predicted_demand, GREATEST(0, LEAST(f.predicted_demand, ra.reorder_threshold) - ra.current_stock) as quantity
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
          verified: false,
        })),
      });
    } catch (error) {
      console.error("Inventory error:", error.message);
      res.status(500).json({ error: error.message });
    }
  },
);

// SupplySync: Submit verified order
app.post(
  "/submit-order/:storeId",
  authenticate(["store_owner"]),
  async (req, res) => {
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
        return res
          .status(404)
          .json({ error: `No store found for: ${storeId}` });
      }
      const { store_id, lat, lng } = store[0];

      const assignments = [];
      for (const item of items) {
        if (!item.verified) continue; // Only process verified items
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
          "INSERT INTO delivery_routes (vehicle_id, dc_id, store_id, sku_id, sequence, distance_km, estimated_time, eta_days, priority_score) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (vehicle_id, store_id, sku_id) DO UPDATE SET sequence = EXCLUDED.sequence",
          [2, fulfillment_center_id, store_id, item.sku_id, 1, 10, 0.5, 1, 0.9],
        );
      }
      res.json({ store_id, assignments });
    } catch (error) {
      console.error("Submit order error:", error.message);
      res.status(500).json({ error: error.message });
    }
  },
);

// TrackX: Track store

app.get("/track/:storeId", authenticate(["store_owner"]), async (req, res) => {
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
      console.error(`No store found for: ${storeId}`);
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
      console.error(`No delivery routes found for store_id: ${store_id}`);
      return res
        .status(404)
        .json({
          error: `No delivery routes found for store: ${store[0].store_location}`,
        });
    }

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

// RouteAI: Get route details

app.get(
  "/route/:vehicleId",
  authenticate(["delivery_partner"]),
  async (req, res) => {
    const { vehicleId } = req.params;
    try {
      const { rows } = await pool.query(
        `
      SELECT dr.*, s.lat, s.lng, dc.latitude as dc_lat, dc.longitude as dc_lng
      FROM delivery_routes dr
      JOIN stores s ON dr.store_id = s.store_id
      JOIN FulfillmentCenter dc ON dr.dc_id = dc.id
      WHERE dr.vehicle_id = $1
      ORDER BY dr.sequence
    `,
        [vehicleId],
      );
      if (!rows.length) {
        console.error(`No routes for vehicle ${vehicleId}`);
        return res
          .status(404)
          .json({ error: `No routes for vehicle ${vehicleId}` });
      }

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
      let etaDays = rows[0].eta_days || 2;

      if (!process.env.ORS_API_KEY) {
        console.warn("Mapbox access token missing, using linear route");
      } else {
        console.log(
          "Using Mapbox token:",
          process.env.ORS_API_KEY.substring(0, 10) + "...",
        );
        const mapboxUrl = `https://api.mapbox.com/directions/v5/mapbox/driving/${coordinates.map((c) => c.join(",")).join(";")}?geometries=geojson&access_token=${process.env.ORS_API_KEY}`;
        console.log("Mapbox URL:", mapboxUrl);
        try {
          const mapboxResponse = await axios.get(mapboxUrl);
          console.log(
            "Mapbox response:",
            JSON.stringify(mapboxResponse.data, null, 2),
          );
          if (!mapboxResponse.data.routes || !mapboxResponse.data.routes[0]) {
            console.error(
              "Mapbox API returned no routes:",
              mapboxResponse.data,
            );
            throw new Error("No routes returned by Mapbox");
          }
          routeGeometry = mapboxResponse.data.routes[0].geometry;
          const durationSeconds = mapboxResponse.data.routes[0].duration || 0;
          etaDays = Math.max(1, Math.ceil(durationSeconds / (24 * 3600)));
        } catch (error) {
          console.error(
            "Mapbox API error:",
            error.response?.data?.message || error.message,
          );
          console.warn("Falling back to linear route");
        }
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
          lat: tracking.length ? tracking[0].latitude : rows[0].lat,
          lng: tracking.length ? tracking[0].longitude : rows[0].lng,
        },
        eta_days: etaDays,
      });
    } catch (error) {
      console.error("Route error:", error.message);
      res.status(500).json({ error: `Route error: ${error.message}` });
    }
  },
);

// SupplySync Admin: Optimize routes
app.get("/optimize-routes", authenticate(["admin"]), async (req, res) => {
  try {
    const response = await axios.get("http://localhost:3002/optimize-routes");
    res.json(response.data);
  } catch (error) {
    console.error(
      "Proxy optimize-routes error:",
      error.response?.data?.message || error.message,
    );
    res
      .status(error.response?.status || 500)
      .json({ error: error.response?.data?.message || error.message });
  }
});

// Socket.IO for location updates
io.on("connection", (socket) => {
  console.log("Socket.IO client connected");
  socket.on("update-location", async (data) => {
    const { vehicleId, storeId, lat, lng, token } = data;
    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET || "secret_key");
      if (
        decoded.role !== "delivery_partner" ||
        decoded.vehicle_id !== parseInt(vehicleId)
      ) {
        socket.emit("error", { error: "Unauthorized location update" });
        return;
      }
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
      socket.emit("error", { error: error.message });
    }
  });
});

server.listen(3001, () =>
  console.log(`SupplySync server running on http://localhost:3001`),
);
