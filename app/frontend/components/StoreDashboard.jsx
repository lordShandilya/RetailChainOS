"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import Chart from "chart.js/auto";

const StoreDashboard = ({ storeId }) => {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [quantities, setQuantities] = useState({});
  const [verified, setVerified] = useState({});
  const [showModal, setShowModal] = useState(false);
  const [ownerName, setOwnerName] = useState("");
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
    const userStoreId = localStorage.getItem("store_id");
    if (
      !token ||
      role !== "store_owner" ||
      parseInt(userStoreId) !== parseInt(storeId)
    ) {
      router.push("/login");
      return;
    }

    // Decode JWT to get owner name
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const storeLocation = storeNameMap[storeId] || "Store Owner";
      setOwnerName(`${storeLocation} Store Owner`);
    } catch (err) {
      console.error("Error decoding JWT:", err);
      setOwnerName("Store Owner");
    }

    const fetchInventory = async () => {
      try {
        const response = await axios.get(
          `http://localhost:3001/inventory/${storeId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        setItems(response.data.items);
        const initialQuantities = {};
        const initialVerified = {};
        response.data.items.forEach((item) => {
          initialQuantities[item.sku_id] = item.current_stock;
          initialVerified[item.sku_id] = false;
        });
        setQuantities(initialQuantities);
        setVerified(initialVerified);
        console.log(
          "Fetched inventory for store",
          storeId,
          response.data.items,
        );
      } catch (err) {
        setError(
          "Failed to fetch inventory: " +
            (err.response?.data?.error || err.message),
        );
        console.error("Fetch inventory error:", err);
      }
    };

    fetchInventory();
  }, [router, storeId]);

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
              data: items.map(
                (item) => quantities[item.sku_id] || item.current_stock || 0,
              ),
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

  useEffect(() => {
    if (chartRef.current && items.length > 0) {
      chartRef.current.data.datasets[0].data = items.map(
        (item) => quantities[item.sku_id] || item.current_stock || 0,
      );
      chartRef.current.update();
      console.log("Chart updated with quantities:", quantities);
    }
  }, [quantities]);

  const handleQuantityChange = (sku_id, value) => {
    setQuantities((prev) => ({ ...prev, [sku_id]: parseInt(value) || 0 }));
  };

  const handleVerifyChange = (sku_id, checked) => {
    setVerified((prev) => ({ ...prev, [sku_id]: checked }));
  };

  const handleSelectAll = () => {
    const newVerified = {};
    items.forEach((item) => {
      newVerified[item.sku_id] = true;
    });
    setVerified(newVerified);
  };

  const handleSubmit = async () => {
    const allVerified = items.every((item) => verified[item.sku_id]);
    if (!allVerified) {
      setShowModal(true);
      return;
    }
    try {
      const token = localStorage.getItem("token");
      const response = await axios.post(
        `http://localhost:3001/submit-order/${storeId}`,
        {
          items: items.map((item) => ({
            sku_id: item.sku_id,
            quantity: quantities[item.sku_id],
          })),
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      alert(response.data.message);
      router.push(`/track/${storeId}`);
    } catch (err) {
      setError(
        "Failed to submit order: " + (err.response?.data?.error || err.message),
      );
      console.error("Submit order error:", err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("store_id");
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
          <span className="text-lg mr-4">{ownerName}</span>
          <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>
      {error && <div className="alert alert-error glass mb-4">{error}</div>}
      <div className="card bg-base-100 shadow-xl glass">
        <div className="card-body">
          <h1 className="card-title">
            Store Dashboard - {storeNameMap[storeId]}
          </h1>
          <div className="mb-6">
            <h2 className="text-xl font-bold mb-4">Inventory Stock Levels</h2>
            <div className="w-full" style={{ height: "160px" }}>
              <canvas id="inventoryChart" className="w-full"></canvas>
            </div>
          </div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold">Inventory List</h2>
            <button
              className="btn btn-primary btn-md"
              onClick={handleSelectAll}
            >
              Select All
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="table w-full">
              <thead>
                <tr>
                  <th>SKU ID</th>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Calculated Stock</th>
                  <th>Update Quantity</th>
                  <th>Verify</th>
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
                      <td>
                        <input
                          type="number"
                          value={quantities[item.sku_id] || ""}
                          onChange={(e) =>
                            handleQuantityChange(item.sku_id, e.target.value)
                          }
                          className="input input-bordered w-24"
                          min="0"
                        />
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          checked={verified[item.sku_id] || false}
                          onChange={(e) =>
                            handleVerifyChange(item.sku_id, e.target.checked)
                          }
                          className="checkbox checkbox-primary"
                        />
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="text-center">
                      No inventory found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="card-actions justify-end mt-4">
            <button
              className="btn btn-primary btn-md px-4"
              onClick={handleSubmit}
              disabled={!items.every((item) => verified[item.sku_id])}
            >
              Submit
            </button>
          </div>
        </div>
      </div>

      <input
        type="checkbox"
        id="verify-modal"
        className="modal-toggle"
        checked={showModal}
        onChange={() => setShowModal(!showModal)}
      />
      <div className="modal" role="dialog">
        <div className="modal-box glass">
          <h3 className="text-lg font-bold">Verification Required</h3>
          <p className="py-4">
            Please verify all items by checking the boxes before submitting the
            order.
          </p>
          <div className="modal-action">
            <label htmlFor="verify-modal" className="btn btn-primary btn-md">
              Close
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StoreDashboard;
