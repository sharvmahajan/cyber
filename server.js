const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname, "public"))); // serve static files

// Routes
app.get("/", (req, res) => {
    res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.post("/log-ip", (req, res) => {
    const publicIP = req.body.public_ip || "N/A";
    const serverIP = req.headers["x-forwarded-for"] || req.socket.remoteAddress;

    console.log(`[CLIENT PUBLIC IP] ${publicIP}`);
    console.log(`[CLIENT SERVER IP] ${serverIP}`);

    res.json({ status: "success", server_ip: serverIP });
});

// Start server
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
