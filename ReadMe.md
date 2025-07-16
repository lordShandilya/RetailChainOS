

# Description

RetailChain OS is an innovative web application which streamlines retail inventory management and delivery optimization. Built with a modern tech stack, it automates stock tracking and delivery routing for large-scale retail chains, reducing costs and improving efficiency.

[Demo link](https://youtu.be/3MSGv4h3k3M?si=0fi504BbnzT6Ikg6)

# What is the main problem this project is solving?

RetailChain OS solves the critical problem of inefficient inventory management and delivery optimization in large-scale retail chains. Retail operations often suffer from delayed restocking, suboptimal delivery routes, and lack of automated decision-making, leading to stockouts, overstocking, increased fuel costs, and delayed deliveries, which harm customer satisfaction and profitability.


# How are you trying to solve this problem?

**RetailChain OS** tackles inefficiencies in retail inventory management and delivery optimization with a technology-driven, automated approach:

---

### Automated Inventory Management:

#### Smart Inventory:

Automatically generates stock replenishment lists for each store based on real-time sales data and inventory levels from the PostgreSQL database. These lists are sent to store owners via the Store Dashboard (React, Next.js, Tailwind CSS), enabling proactive restocking to prevent stockouts or overstocking.

#### Admin & Store Dashboards:

Built with React, Next.js, and Tailwind CSS, integrated with a Node.js backend, these dashboards display real-time inventory data from fulfillment centers/Inventory, with Charts visualizations for clear insights.

---

### Optimized Delivery Routes:

#### TrackX & RouteAI:

The TrackX module, powered by RouteAI, optimizes delivery routes using clustering and urgency-based prioritization. WebSockets provide real-time delivery vehicle updates.

##### Prioritization Factors:

* **Clustering**: Prioritizes groups of stores close to each other but farther from the fulfillment center over a single nearby store.
* **Priority**: Favors stores with critical stock shortages over nearby stores with ample stock.
* **Distance**: Selects clusters that minimize total travel distance while meeting urgency needs.

---

### Automated Fulfillment Selection:

#### Fulfill Smart:

Automatically selects the optimal fulfillment center to service store orders based on:

* **Proximity**: Chooses the closest fulfillment center to the store cluster.
* **Stock Availability**: Ensures the center has sufficient stock to meet order demands, using inventoryitem data.

---

### Scalable Architecture:

Built on a scalable stack (Next.js, Node.js, PostgreSQL), RetailChain OS handles multiple stores and fulfillment centers/Inventory efficiently. APIs ensure seamless data flow, reducing delivery times and operational costs, while automation minimizes manual intervention.









# Core Features and Functionality

## SmartInventory:
- **Purpose**: Predicts monthly inventory needs for each store using the Prophet forecasting model, generating a list of items and quantities to prevent stockouts.
- **Input**: Historical sales data (inventory, forecasts tables), reorder thresholds (reorder_alerts), and product details (products).
- **Output**: A list of SKUs and quantities (e.g., `{ sku_id: 1, name: "Rice 5kg", quantity: 100 }`) for each store (e.g., store_id: 2, Chennai).
- **Process**:
    - Prophet analyzes sales trends (e.g., daily sales from inventory) to forecast demand for the next 30 days.
    - Combines forecasts with current stock (reorder_alerts.current_stock) to identify shortages (reorder_threshold > current_stock).
    - Generates a proposed order list for each store, sent to SupplySync.

## Fulfillment:
- **Purpose**: Assigns orders to the nearest DC based on store location, optimizing for distance to reduce fuel and emissions.
- **Input**: Verified order list from SupplySync (SKUs, quantities, store_id), DC inventory (inventory, dc_id, lat, lng), and store locations (stores.lat, lng).
- **Output**: An order assignment (e.g., `{ store_id: 2, dc_id: 1, items: [{ sku_id: 1, quantity: 100 }] }`) sent to RouteAI.
- **Process**:
    - Uses Haversine distance to find the closest DC with sufficient stock for each SKU.
    - Updates inventory table (subtracts quantities from DC stock) and creates a delivery order in delivery_routes.

## RouteAI:
- **Purpose**: Optimizes delivery routes for vehicles from DCs to stores, prioritizing clusters of stores and urgency.
- **Input**: Delivery orders from Fulfillment (store IDs, items), store locations (stores.lat, lng), and priority scores (reorder_alerts.priority_score).
- **Output**: Optimized routes (delivery_routes) with sequences, distances, and ETAs for each vehicle (e.g., vehicle_id: 2).
- **Process**:
    - Uses DBSCAN clustering (in server.js) to group stores within 10 km, prioritizing clusters far from the DC (e.g., Bengaluru DC at [77.6000, 13.1000]) to satisfy more stores efficiently.
    - Factors in priority_score (e.g., high for stores with current_stock = 0) to override distance for urgent deliveries.
    - Calls OpenRouteService API (driving-hgv) to compute routes, storing results in delivery_routes (e.g., geometry: LineString, eta_days).

## TrackX:
- **Purpose**: Allows store owners to track delivery vehicles in real-time for their store.
- **Input**: storeId (e.g., 2 or Chennai), vehicle data from delivery_routes and tracking_logs (via `/track/:storeId`).
- **Output**: Mapbox GL JS map (TrackPortal.jsx) showing the vehicle’s position (truck icon), route, and ETA with a popup.
- **Process**:
    - Fetches `/track/:storeId` to get route and vehicle data.
    - Uses Socket.IO to update vehicle position (tracking_logs.latitude, longitude) in real-time.
    - Displays a Mapbox streets-v12 map with a blue route line and truck marker.

## Backend (Master Feature):
- **Purpose**: Orchestrates the workflow by coordinating SmartInventory, Fulfillment, RouteAI, and TrackX, and manages store owner interactions.
- **Input**: Store order lists from SmartInventory, store owner feedback, and delivery assignments from Fulfillment.
- **Output**: Verified order lists, delivery assignments, and notifications to store owners and delivery partners.
- **Process**:
    - Requests order lists from SmartInventory for each store (e.g., daily batch job).
    - Sends lists to store owners via a dashboard (`http://localhost:3000/store/:storeId`).
    - Store owners edit/verify lists (e.g., adjust quantities) and submit them back.
    - Forwards verified lists to Fulfillment for DC assignment.
    - Triggers RouteAI to optimize routes and TrackX for real-time tracking.


### Data Flow:

- **SmartInventory**: Runs Prophet daily (cron job) to update forecasts, generates order lists (`/inventory/:storeId`).
- **SupplySync**: Sends lists to store owners via `/store/:storeId`, receives verified lists via `/submit-order/:storeId`.
- **Fulfillment**: Processes verified lists via `/fulfillment`, assigns DCs, updates `delivery_routes`.
- **RouteAI**: Optimizes routes (`/optimize-routes`), stores in `delivery_routes`.
- **TrackX**: Displays real-time tracking (`/track/:storeId`, Socket.IO).

---

# Roles

---

### Store Owner:
- Accesses `/store/:storeId` to view/edit SmartInventory order lists.
- Tracks deliveries via `/track/:storeId`.
- **Example**: Chennai store owner (store_id: 2) verifies order list and monitors vehicle.

---

### Delivery Partner:
- Accesses `/vehicle/:vehicleId` to view optimized routes (DeliveryMap.jsx).
- Updates vehicle position via Socket.IO (`update-location`).
- **Example**: Driver for vehicle_id: 2 follows route to Chennai.

---

### Admin:
- Monitors system via a dashboard *(not built due to time constraints)* to trigger `/optimize-routes` or `/fulfillment`.
- Could be automated (cron jobs) for the prototype.
