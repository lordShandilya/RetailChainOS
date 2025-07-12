"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const StoreDashboard = ({ storeId }) => {
  const [orderList, setOrderList] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    const fetchOrderList = async () => {
      try {
        const response = await fetch(
          `http://localhost:3001/inventory/${storeId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        const data = await response.json();
        if (data.error) {
          setError(data.error);
          setLoading(false);
          return;
        }
        setOrderList(data);
        setLoading(false);
      } catch (error) {
        setError("Failed to fetch order list: " + error.message);
        setLoading(false);
      }
    };
    fetchOrderList();
  }, [storeId, router]);

  const handleQuantityChange = (sku_id, quantity) => {
    setOrderList((prev) => ({
      ...prev,
      items: prev.items.map((item) =>
        item.sku_id === sku_id
          ? { ...item, quantity: parseInt(quantity) || 0 }
          : item,
      ),
    }));
  };

  const handleVerify = (sku_id) => {
    setOrderList((prev) => ({
      ...prev,
      items: prev.items.map((item) =>
        item.sku_id === sku_id ? { ...item, verified: true } : item,
      ),
    }));
  };

  const handleSubmit = async () => {
    try {
      const response = await fetch(
        `http://localhost:3001/submit-order/${storeId}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
          body: JSON.stringify({ items: orderList.items }),
        },
      );
      const data = await response.json();
      if (data.error) {
        setError(data.error);
        return;
      }
      alert("Order submitted successfully");
      router.push(`/track/${storeId}`);
    } catch (error) {
      setError("Failed to submit order: " + error.message);
    }
  };

  if (loading) return <p>Loading...</p>;
  if (error) return <p style={{ color: "red" }}>Error: {error}</p>;
  if (!orderList) return <p>No order list available</p>;

  return (
    <div style={{ padding: "20px" }}>
      <h1>Order List for Store {storeId}</h1>
      <table
        style={{ width: "100%", borderCollapse: "collapse", marginTop: "20px" }}
      >
        <thead>
          <tr>
            <th style={{ border: "1px solid #ccc", padding: "10px" }}>
              SKU ID
            </th>
            <th style={{ border: "1px solid #ccc", padding: "10px" }}>Name</th>
            <th style={{ border: "1px solid #ccc", padding: "10px" }}>
              Quantity
            </th>
            <th style={{ border: "1px solid #ccc", padding: "10px" }}>
              Verified
            </th>
          </tr>
        </thead>
        <tbody>
          {orderList.items.map((item) => (
            <tr key={item.sku_id}>
              <td style={{ border: "1px solid #ccc", padding: "10px" }}>
                {item.sku_id}
              </td>
              <td style={{ border: "1px solid #ccc", padding: "10px" }}>
                {item.name}
              </td>
              <td style={{ border: "1px solid #ccc", padding: "10px" }}>
                <input
                  type="number"
                  value={item.quantity}
                  onChange={(e) =>
                    handleQuantityChange(item.sku_id, e.target.value)
                  }
                  style={{ width: "80px", padding: "5px" }}
                  disabled={item.verified}
                />
              </td>
              <td style={{ border: "1px solid #ccc", padding: "10px" }}>
                <input
                  type="checkbox"
                  checked={item.verified}
                  onChange={() => handleVerify(item.sku_id)}
                  disabled={item.verified}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        onClick={handleSubmit}
        style={{
          padding: "10px 20px",
          background: "#1e90ff",
          color: "white",
          border: "none",
          borderRadius: "4px",
          marginTop: "20px",
        }}
      >
        Submit Order
      </button>
    </div>
  );
};

export default StoreDashboard;
