const express = require("express");
const { Pool } = require("pg");
const jwt = require("jsonwebtoken");
const bcrypt = require("bcrypt");
const cors = require("cors");
const socketIo = require("socket.io");
const http = require("http");
const axios = require("axios");
require("dotenv").config();

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
  user: "walmart_user",
  host: "localhost",
  database: "walmart_db",
  password: process.env.DB_USER_PASSWORD || "securepassword",
  port: 5432,
});

app.use(cors({ origin: "http://localhost:3000", credentials: true }));
app.use(express.json());

function authenticateToken(req, res, next) {
  const authHeader = req.headers["authorization"];
  const token = authHeader && authHeader.split(" ")[1];
  if (!token) return res.status(401).json({ error: "Access token required" });
  try {
    const user = jwt.verify(token, process.env.JWT_SECRET || "your_jwt_secret");
    req.user = user;
    next();
  } catch (err) {
    res.status(403).json({ error: "Invalid or expired token" });
  }
}

app.post("/login", async (req, res) => {
  const { username, password } = req.body;
  try {
    const result = await pool.query("SELECT * FROM users WHERE username = $1", [
      username,
    ]);
    const user = result.rows[0];
    if (!user) {
      return res.status(401).json({ error: "Invalid credentials" });
    }
    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
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
    res.json({
      token,
      role: user.role,
      store_id: user.store_id,
      vehicle_id: user.vehicle_id,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/stores", authenticateToken, async (req, res) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ error: "Access denied" });
  }
  try {
    const result = await pool.query("SELECT * FROM stores");
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/stores/verified", authenticateToken, async (req, res) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ error: "Access denied" });
  }
  try {
    const result = await pool.query(
      "SELECT * FROM stores WHERE verified = true",
    );
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get(
  "/api/stores/:storeId/inventory",
  authenticateToken,
  async (req, res) => {
    if (req.user.role !== "admin") {
      return res.status(403).json({ error: "Access denied" });
    }
    try {
      const result = await pool.query(
        `
      SELECT i.*, p.name AS sku_name, f.latitude, f.longitude
      FROM inventory i
      JOIN products p ON i.sku_id = p.sku_id
      JOIN FulfillmentCenter f ON i.dc_id = f.id
      WHERE i.store_id = $1
    `,
        [req.params.storeId],
      );
      res.json(result.rows);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  },
);

app.get("/inventory/:storeId", authenticateToken, async (req, res) => {
  const { storeId } = req.params;
  if (req.user.role === "store_owner" && req.user.store_id != storeId) {
    return res.status(403).json({ error: "Unauthorized" });
  }
  if (req.user.role !== "admin" && req.user.role !== "store_owner") {
    return res.status(403).json({ error: "Unauthorized" });
  }
  try {
    // Find store coordinates
    const storeQuery = await pool.query(
      "SELECT lat, lng FROM stores WHERE store_id = $1",
      [storeId],
    );
    if (storeQuery.rows.length === 0) {
      console.log(`No store found for store_id=${storeId}`);
      return res.status(404).json({ error: "Store not found" });
    }
    const { lat, lng } = storeQuery.rows[0];

    // Find nearest fulfillment center
    const fcQuery = await pool.query(
      "SELECT id, latitude, longitude FROM fulfillmentcenter",
    );
    let nearestFcId = null;
    let minDistance = Infinity;
    for (const fc of fcQuery.rows) {
      const distance = Math.sqrt(
        Math.pow(parseFloat(fc.latitude) - parseFloat(lat), 2) +
          Math.pow(parseFloat(fc.longitude) - parseFloat(lng), 2),
      );
      if (distance < minDistance) {
        minDistance = distance;
        nearestFcId = fc.id;
      }
    }
    console.log(
      `Nearest fulfillment center for store_id=${storeId}: fc_id=${nearestFcId}`,
    );

    // Fetch inventory with corrected join
    const inventoryQuery = await pool.query(
      `SELECT i.fulfillment_center_id AS store_id, p.sku_id AS sku_id,
              i.quantity AS current_stock, p.name, p.category
       FROM inventoryitem i
       JOIN products p ON i.sku = p.name
       WHERE i.fulfillment_center_id = $1`,
      [nearestFcId],
    );

    if (inventoryQuery.rows.length === 0) {
      console.log(
        `No inventory found for fulfillment_center_id=${nearestFcId}`,
      );
      return res.status(404).json({ error: "No inventory found for store" });
    }
    console.log(
      `Inventory for store_id=${storeId} (fc_id=${nearestFcId}):`,
      inventoryQuery.rows,
    );
    res.json({ items: inventoryQuery.rows });
  } catch (err) {
    console.error("Inventory error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.post("/submit-order/:storeId", authenticateToken, async (req, res) => {
  if (
    req.user.role !== "store_owner" ||
    parseInt(req.user.store_id) !== parseInt(req.params.storeId)
  ) {
    return res.status(403).json({ error: "Access denied" });
  }
  const { items } = req.body;
  try {
    await pool.query("BEGIN");
    for (const item of items) {
      await pool.query(
        "UPDATE inventory SET current_stock = $1 WHERE store_id = $2 AND sku_id = $3",
        [item.quantity, req.params.storeId, item.sku_id],
      );
    }
    await pool.query("COMMIT");
    res.json({ message: "Order submitted successfully" });
  } catch (err) {
    await pool.query("ROLLBACK");
    res.status(500).json({ error: err.message });
  }
});

app.get("/stores", authenticateToken, async (req, res) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ error: "Unauthorized" });
  }
  try {
    const storesQuery = await pool.query(
      "SELECT store_id, store_location FROM stores",
    );
    if (storesQuery.rows.length === 0) {
      return res.status(404).json({ error: "No stores found" });
    }
    res.json(storesQuery.rows);
    console.log("Fetched stores:", storesQuery.rows);
  } catch (err) {
    console.error("Stores error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.get("/track/:storeId", authenticateToken, async (req, res) => {
  try {
    // Find the vehicle serving the store
    const routeResult = await pool.query(
      `
      SELECT dr.vehicle_id, dr.dc_id, dr.eta_days
      FROM delivery_routes dr
      WHERE dr.store_id = $1
      ORDER BY dr.sequence
      LIMIT 1
    `,
      [req.params.storeId],
    );
    if (routeResult.rows.length === 0) {
      return res.status(404).json({ error: "No route found for store" });
    }
    const { vehicle_id, dc_id, eta_days } = routeResult.rows[0];

    // Fetch route from RouteAI
    const routeResponse = await axios.get(
      `http://localhost:3002/route/${vehicle_id}`,
    );
    const { route, vehicle } = routeResponse.data;

    // Fetch vehicle location from tracking_logs
    const tracking = await pool.query(
      "SELECT latitude AS lat, longitude AS lng, timestamp FROM tracking_logs WHERE vehicle_id = $1 ORDER BY timestamp DESC LIMIT 1",
      [vehicle_id],
    );
    console.log(
      "Track /track/:storeId:",
      req.params.storeId,
      "Tracking result:",
      tracking.rows,
    );

    res.json({
      vehicle: tracking.rows[0] || vehicle, // Fallback to RouteAI vehicle location
      route: route,
      eta_days: eta_days || routeResponse.data.eta_days,
    });
  } catch (err) {
    console.error("Error in /track/:storeId:", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get("/route/:vehicleId", authenticateToken, async (req, res) => {
  if (
    req.user.role !== "delivery_partner" ||
    req.user.vehicle_id !== parseInt(req.params.vehicleId)
  ) {
    return res.status(403).json({ error: "Access denied" });
  }
  try {
    // Fetch route from RouteAI
    const routeResponse = await axios.get(
      `http://localhost:3002/route/${req.params.vehicleId}`,
    );
    const { route, vehicle, eta_days } = routeResponse.data;

    // Fetch vehicle location from tracking_logs
    const tracking = await pool.query(
      "SELECT latitude AS lat, longitude AS lng, timestamp FROM tracking_logs WHERE vehicle_id = $1 ORDER BY timestamp DESC LIMIT 1",
      [req.params.vehicleId],
    );
    console.log(
      "Track /route/:vehicleId:",
      req.params.vehicleId,
      "Tracking result:",
      tracking.rows,
    );

    res.json({
      vehicle: tracking.rows[0] || vehicle, // Fallback to RouteAI vehicle location
      route: route,
      eta_days,
    });
  } catch (err) {
    console.error("Error in /route/:vehicleId:", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get("/optimize-routes", authenticateToken, async (req, res) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ error: "Access denied" });
  }
  try {
    // Forward to RouteAI
    const routeResponse = await axios.get(
      "http://localhost:3002/optimize-routes",
    );
    res.json(routeResponse.data);
  } catch (err) {
    console.error("Error in /optimize-routes:", err.message);
    res.status(500).json({ error: err.message });
  }
});

io.on("connection", (socket) => {
  socket.on("update-location", async (data) => {
    const { vehicleId, lat, lng, token } = data;
    try {
      const user = jwt.verify(
        token,
        process.env.JWT_SECRET || "your_jwt_secret",
      );
      if (user.vehicle_id !== parseInt(vehicleId)) {
        socket.emit("error", { error: "Unauthorized" });
        return;
      }
      await pool.query(
        "INSERT INTO tracking_logs (vehicle_id, latitude, longitude, timestamp) VALUES ($1, $2, $3, NOW())",
        [vehicleId, lat, lng],
      );
      io.emit("location-update", {
        vehicleId,
        lat,
        lng,
        storeId: data.storeId,
      });
    } catch (err) {
      socket.emit("error", { error: err.message });
    }
  });
});

server.listen(3001, () => {
  console.log("Server running on port 3001");
});
