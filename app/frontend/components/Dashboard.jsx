"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import Chart from "chart.js/auto";

const Dashboard = () => {
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreId] = useState(null);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const router = useRouter();
  const chartRef = useRef(null);

  // Store mapping for display name
  const storeNameMap = {
    1: "Bengaluru",
    2: "Chennai",
    3: "Hyderabad",
    4: "Kochi",
    5: "Coimbatore",
    6: "Delhi",
    7: "Mumbai",
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    const role = localStorage.getItem("role");
    if (!token || role !== "admin") {
      router.push("/login");
      return;
    }

    const fetchStores = async () => {
      try {
        const response = await axios.get("http://localhost:3001/stores", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setStores(response.data);
        if (response.data.length > 0) {
          setSelectedStoreId(response.data[0].store_id);
        }
        console.log("Fetched stores:", response.data);
      } catch (err) {
        setError(
          "Failed to fetch stores: " +
            (err.response?.data?.error || err.message),
        );
        console.error("Fetch stores error:", err);
      }
    };

    fetchStores();
  }, [router]);

  useEffect(() => {
    if (!selectedStoreId) return;

    const token = localStorage.getItem("token");
    const fetchInventory = async () => {
      try {
        const response = await axios.get(
          `http://localhost:3001/inventory/${selectedStoreId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        setItems(response.data.items);
        setError(null);
        console.log(
          "Fetched inventory for store",
          selectedStoreId,
          response.data.items,
        );
      } catch (err) {
        setError(
          "Failed to fetch inventory: " +
            (err.response?.data?.error || err.message),
        );
        setItems([]);
        console.error("Fetch inventory error:", err);
      }
    };

    fetchInventory();
  }, [selectedStoreId]);

  useEffect(() => {
    if (items.length > 0) {
      const ctx = document.getElementById("inventoryChart").getContext("2d");
      if (chartRef.current) {
        chartRef.current.destroy();
      }
      chartRef.current = new Chart(ctx, {
        type: "bar",
        data: {
          labels: items.map((item) => item.name || `SKU ${item.sku_id}`),
          datasets: [
            {
              label: "Calculated Stock",
              data: items.map((item) => item.current_stock || 0),
              backgroundColor: "rgba(94, 129, 172, 0.6)", // Nord primary
              borderColor: "#5E81AC",
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              title: { display: true, text: "Stock Quantity" },
            },
            x: { title: { display: true, text: "Product" } },
          },
        },
      });
    }
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [items]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    router.push("/login");
  };

  return (
    <div
      className="container mx-auto p-6 min-h-screen bg-base-200"
      data-theme="nord"
    >
      <header className="navbar bg-base-100 shadow-xl glass mb-6">
        <div className="flex-1">
          <h1 className="text-3xl font-bold text-primary">RetailChainOS</h1>
        </div>
        <div className="flex-none">
          <span className="text-lg mr-4">Admin</span>
          <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>
      {error && <div className="alert alert-error glass mb-4">{error}</div>}
      <div className="card bg-base-100 shadow-xl glass">
        <div className="card-body">
          <h1 className="card-title">Admin Dashboard - Inventory Management</h1>
          <div className="mb-4">
            <label className="label">
              <span className="label-text">Select Store</span>
            </label>
            <select
              className="select select-bordered w-full max-w-xs"
              value={selectedStoreId || ""}
              onChange={(e) => setSelectedStoreId(e.target.value)}
            >
              <option value="" disabled>
                Select a store
              </option>
              {stores.map((store) => (
                <option key={store.store_id} value={store.store_id}>
                  {storeNameMap[store.store_id] || store.store_id}
                </option>
              ))}
            </select>
          </div>
          <div className="mb-6">
            <h2 className="text-xl font-bold mb-4">Inventory Stock Levels</h2>
            <div className="w-full" style={{ height: "160px" }}>
              <canvas id="inventoryChart" className="w-full"></canvas>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="table w-full">
              <thead>
                <tr>
                  <th>SKU ID</th>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Calculated Stock</th>
                </tr>
              </thead>
              <tbody>
                {items.length > 0 ? (
                  items.map((item) => (
                    <tr key={item.sku_id}>
                      <td>{item.sku_id}</td>
                      <td>{item.name || "Unknown"}</td>
                      <td>{item.category || "Unknown"}</td>
                      <td>{item.current_stock || 0}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="4" className="text-center">
                      No inventory found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
