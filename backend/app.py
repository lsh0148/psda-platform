from datetime import datetime
from random import randint, uniform

from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

HILBERT_ORDER = [
    (0, 3), (0, 2), (1, 2), (1, 3),
    (2, 3), (3, 3), (3, 2), (2, 2),
    (2, 1), (3, 1), (3, 0), (2, 0),
    (1, 0), (1, 1), (0, 1), (0, 0),
]


def build_regions():
    base_loads = [52, 56, 61, 58, 64, 71, 68, 63, 75, 87, 92, 78, 66, 59, 55, 49]
    rows = []
    for index, ((x, y), base) in enumerate(zip(HILBERT_ORDER, base_loads)):
        load = max(35, min(96, base + randint(-2, 2)))
        status = "critical" if load >= 88 else "warning" if load >= 74 else "normal"
        rows.append({
            "name": f"区域 {chr(65 + index)}",
            "code": format(index, "04b"),
            "x": x,
            "y": y,
            "load": load,
            "devices": randint(26, 68),
            "voltage": round(uniform(218.2, 223.8), 1),
            "aggregate": round(load * uniform(1.18, 1.42), 2),
            "status": status,
        })
    return rows


def build_devices(regions):
    types = [("智能电表", "Smart Meter"), ("充电站", "EV Station"), ("变压器监测器", "Transformer")]
    devices = []
    for index in range(10):
        region = regions[(index * 3 + 2) % len(regions)]
        cn, en = types[index % len(types)]
        status = region["status"] if index in (3, 7) else "normal"
        devices.append({
            "id": f"PSDA-{index + 1:03d}", "name": f"{cn} {index + 1:02d}", "type": en,
            "region": region["code"], "voltage": round(uniform(217.5, 224.6), 1),
            "current": round(uniform(3.2, 19.8), 1), "load": region["load"], "status": status,
        })
    return devices


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "PSDA Analytics API"})


@app.get("/api/overview")
def get_overview():
    regions = build_regions()
    return jsonify({
        "updated_at": datetime.now().strftime("%H:%M:%S"),
        "metrics": {"devices": sum(r["devices"] for r in regions), "regions": 16,
                    "alerts": sum(r["status"] != "normal" for r in regions), "latency": randint(18, 25)},
        "regions": regions,
        "devices": build_devices(regions),
    })


@app.get("/api/trend")
def get_trend():
    times = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
    loads = [52, 58, 67, 62, 69, 81, 88, 74]
    return jsonify({"points": [{"time": t, "load": v + randint(-2, 2)} for t, v in zip(times, loads)]})


@app.get("/api/privacy-demo")
def privacy_demo():
    return jsonify({
        "input": {"region": "0111", "load": 85},
        "shares": {"server_a": "k0: 9f2a••••", "server_b": "k1: c71d••••"},
        "result": {"scope": "regional aggregate", "privacy": "single-server indistinguishability"},
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
