"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const Dashboard = () => {
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    const role = localStorage.getItem("role");
    const store_id = localStorage.getItem("store_id");
    const vehicle_id = localStorage.getItem("vehicle_id");
    if (!token) {
      router.push("/login");
      return;
    }
    setUser({ role, store_id, vehicle_id });
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("store_id");
    localStorage.removeItem("vehicle_id");
    router.push("/login");
  };

  const handleOptimizeRoutes = async () => {
    try {
      const response = await fetch("http://localhost:3001/optimize-routes", {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      const data = await response.json();
      if (data.error) setError(data.error);
      else alert("Routes optimized successfully");
    } catch (error) {
      setError("Failed to optimize routes: " + error.message);
    }
  };

  if (!user) return <p>Loading...</p>;

  return (
    <div style={{ padding: "20px" }}>
      <h1>
        {user.role === "store_owner"
          ? "Store Owner Dashboard"
          : user.role === "delivery_partner"
            ? "Delivery Partner Dashboard"
            : "Admin Dashboard"}
      </h1>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <button
        onClick={handleLogout}
        style={{
          padding: "10px 20px",
          background: "#ff4444",
          color: "white",
          border: "none",
          borderRadius: "4px",
          marginBottom: "20px",
        }}
      >
        Logout
      </button>
      {user.role === "store_owner" && (
        <div>
          <h2>Store ID: {user.store_id}</h2>
          <Link
            href={`/store/${user.store_id}`}
            style={{
              display: "inline-block",
              padding: "10px 20px",
              background: "#1e90ff",
              color: "white",
              borderRadius: "4px",
              margin: "10px",
            }}
          >
            View/Edit Order List
          </Link>
          <Link
            href={`/track/${user.store_id}`}
            style={{
              display: "inline-block",
              padding: "10px 20px",
              background: "#1e90ff",
              color: "white",
              borderRadius: "4px",
              margin: "10px",
            }}
          >
            Track Delivery
          </Link>
        </div>
      )}
      {user.role === "delivery_partner" && (
        <div>
          <h2>Vehicle ID: {user.vehicle_id}</h2>
          <Link
            href={`/vehicle/${user.vehicle_id}`}
            style={{
              display: "inline-block",
              padding: "10px 20px",
              background: "#1e90ff",
              color: "white",
              borderRadius: "4px",
              margin: "10px",
            }}
          >
            View Route
          </Link>
          <button
            onClick={() => {
              const socket = io("http://localhost:3001");
              socket.emit("update-location", {
                vehicleId: user.vehicle_id,
                storeId: user.store_id || "Chennai",
                lat: 12.9716, // Simulate location update
                lng: 77.5946,
                token: localStorage.getItem("token"),
              });
              socket.on("error", (data) => setError(data.error));
            }}
            style={{
              padding: "10px 20px",
              background: "#1e90ff",
              color: "white",
              border: "none",
              borderRadius: "4px",
              margin: "10px",
            }}
          >
            Update Location (Test)
          </button>
        </div>
      )}
      {user.role === "admin" && (
        <div>
          <h2>Admin Actions</h2>
          <button
            onClick={handleOptimizeRoutes}
            style={{
              padding: "10px 20px",
              background: "#1e90ff",
              color: "white",
              border: "none",
              borderRadius: "4px",
              margin: "10px",
            }}
          >
            Optimize Routes
          </button>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
