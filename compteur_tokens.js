const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

const FILE_PATH = path.join(__dirname, "tokens_log.json");
const MAX_TOKENS = 10000;

function readData() {
    if (!fs.existsSync(FILE_PATH)) {
        return [];
    }
    const raw = fs.readFileSync(FILE_PATH, "utf-8");
    try {
        return JSON.parse(raw);
    } catch (e) {
        return [];
    }
}

function writeData(data) {
    fs.writeFileSync(FILE_PATH, JSON.stringify(data, null, 2));
}

app.get("/api/tokens", (req, res) => {
    const now = Date.now();
    const limit = now - (24 * 60 * 60 * 1000);

    let data = readData();

    const filtered = data.filter(entry => {
        return new Date(entry.timestamp).getTime() >= limit;
    });

    const used = filtered.reduce((sum, entry) => {
        return sum + (entry.tokens || 0);
    }, 0);

    let remaining = MAX_TOKENS - used;
    if (remaining < 0) remaining = 0;

    writeData(filtered);

    res.json({
        used: used,
        remaining: remaining,
        max: MAX_TOKENS
    });
});

app.listen(PORT, () => {
    console.log(`Token server running on port ${PORT}`);
});
