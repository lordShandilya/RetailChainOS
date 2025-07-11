"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";

const StoreDashboard = () => {
  const { storeId } = useParams();
  const [orderList, setOrderList] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [quantities, setQuantities] = useState({});

  useEffect(() => {
    const fetchOrderList = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001"}/inventory/${storeId}`,
        );
        const data = await response.json();
        if (data.error) {
          setError(data.error);
          setLoading(false);
          return;
        }
        setOrderList(data);
        setQuantities(
          data.items.reduce(
            (acc, item) => ({
              ...acc,
              [item.sku_id]: item.quantity,
            }),
            {},
          ),
        );
        setError(null);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching order list:", error.message);
        setError("Failed to fetch order list: " + error.message);
        setLoading(false);
      }
    };
    fetchOrderList();
  }, [storeId]);

  const handleQuantityChange = (skuId, value) => {
    setQuantities((prev) => ({
      ...prev,
      [skuId]: Math.max(0, parseInt(value) || 0),
    }));
  };

  const handleSubmitOrder = async () => {
    try {
      const items = Object.entries(quantities).map(([sku_id, quantity]) => ({
        sku_id: parseInt(sku_id),
        quantity,
      }));
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001"}/submit-order/${storeId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items }),
        },
      );
      const data = await response.json();
      if (data.error) {
        setError(data.error);
        return;
      }
      alert(`Order submitted successfully for store ${storeId}!`);
      setError(null);
    } catch (error) {
      console.error("Error submitting order:", error.message);
      setError("Failed to submit order: " + error.message);
    }
  };

  return (
    <div style={{ padding: "20px" }}>
      <h1>Store Dashboard: {storeId}</h1>
      {loading && <p>Loading order list...</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      {orderList && (
        <div>
          <h2>Order List</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ border: "1px solid #ddd", padding: "8px" }}>
                  SKU
                </th>
                <th style={{ border: "1px solid #ddd", padding: "8px" }}>
                  Name
                </th>
                <th style={{ border: "1px solid #ddd", padding: "8px" }}>
                  Quantity
                </th>
              </tr>
            </thead>
            <tbody>
              {orderList.items.map((item) => (
                <tr key={item.sku_id}>
                  <td style={{ border: "1px solid #ddd", padding: "8px" }}>
                    {item.sku_id}
                  </td>
                  <td style={{ border: "1px solid #ddd", padding: "8px" }}>
                    {item.name}
                  </td>
                  <td style={{ border: "1px solid #ddd", padding: "8px" }}>
                    <input
                      type="number"
                      value={quantities[item.sku_id] || ""}
                      onChange={(e) =>
                        handleQuantityChange(item.sku_id, e.target.value)
                      }
                      min="0"
                      style={{ width: "60px" }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            onClick={handleSubmitOrder}
            style={{ marginTop: "20px", padding: "10px 20px" }}
          >
            Submit Order
          </button>
        </div>
      )}
    </div>
  );
};

export default StoreDashboard;
