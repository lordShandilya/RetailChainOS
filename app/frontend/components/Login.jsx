"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:3001/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (data.error) {
        console.error("Login failed:", data.error);
        setError(data.error);
        return;
      }
      localStorage.setItem("token", data.token);
      localStorage.setItem("role", data.role);
      localStorage.setItem("store_id", data.store_id);
      localStorage.setItem("vehicle_id", data.vehicle_id);
      console.log("Stored token:", data.token);
      if (data.role === "store_owner" && data.store_id) {
        router.push(`/store/${data.store_id}`);
      } else if (data.role === "delivery_partner" && data.vehicle_id) {
        router.push(`/vehicle/${data.vehicle_id}`);
      } else if (data.role === "admin") {
        router.push("/admin");
      } else {
        setError("Invalid role or configuration");
      }
    } catch (error) {
      console.error("Login error:", error.message);
      setError("Login failed: " + error.message);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="card bg-base-100 shadow-xl max-w-md mx-auto">
        <div className="card-body">
          <h1 className="card-title">RetailChain OS Login</h1>
          {error && <div className="alert alert-error">{error}</div>}
          <form onSubmit={handleLogin}>
            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text">Username</span>
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input input-bordered w-full"
                required
              />
            </div>
            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text">Password</span>
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input input-bordered w-full"
                required
              />
            </div>
            <button type="submit" className="btn btn-primary w-full">
              Login
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Login;
