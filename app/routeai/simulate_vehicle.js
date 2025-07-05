require("dotenv").config();

const io = require("socket.io-client");
const socket = io(process.env.BACKEND_URL || "http://localhost:3001");
const vehicleId = 2;
setInterval(() => {
  socket.emit("update-location", { vehicleId, lat: 29.8305, lng: -95.3842 }); // Houston store
  console.log(`Sent location for vehicle ${vehicleId}`);
}, 5000);
