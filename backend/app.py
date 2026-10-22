from datetime import datetime
from random import Random

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GRID = 4
CELLS = GRID * GRID
FIELD = 1009
DEFAULT_ANOMALY_RATIO = 0.25


def hilbert_cells(order):
    """论文 Algorithm 1：由 (x, y) 递推得到 Hilbert 序号，返回 序号 -> (x, y)。

    x 为列号、y 为行号，行号 0 位于顶部，与论文 Figure 1 / Figure 3 的排布一致。
    """
    cells = [None] * (order * order)
    for x in range(order):
        for y in range(order):
            px, py = x, y
            index = 0
            scale = order // 2
            while scale > 0:
                rx = 1 if px & scale else 0
                ry = 1 if py & scale else 0
                index += scale * scale * ((3 * rx) ^ ry)
                if ry == 0:
                    if rx == 1:
                        px, py = order - 1 - px, order - 1 - py
                    px, py = py, px
                scale //= 2
            cells[index] = (x, y)
    return cells


HILBERT_ORDER = hilbert_cells(GRID)

rng = Random()

# 接入设备数量在运行期间保持稳定，只有负荷和异常状态随模拟刷新。
DEVICE_COUNTS = [rng.randint(26, 68) for _ in range(CELLS)]
DEVICE_LOADS = [[] for _ in range(CELLS)]
LOADS = [0] * CELLS


def simulate(anomaly_ratio):
    """为每个区域分配随机负荷，并按比例注入偏高和异常区域。"""
    ratio = max(0.0, min(1.0, anomaly_ratio))
    attention_count = round(CELLS * ratio)
    attention_regions = rng.sample(range(CELLS), attention_count)
    critical_count = attention_count // 2
    critical_regions = set(attention_regions[:critical_count])
    warning_regions = set(attention_regions[critical_count:])
    for index in range(CELLS):
        if index in critical_regions:
            LOADS[index] = rng.randint(88, 98)
        elif index in warning_regions:
            LOADS[index] = rng.randint(74, 87)
        else:
            LOADS[index] = rng.randint(45, 72)
        DEVICE_LOADS[index] = [rng.uniform(0.6, 1.9) for _ in range(DEVICE_COUNTS[index])]


def status_of(load):
    if load >= 88:
        return "critical"
    if load >= 74:
        return "warning"
    return "normal"


def region_rows():
    rows = []
    for index, ((x, y), load) in enumerate(zip(HILBERT_ORDER, LOADS)):
        rows.append({
            "name": f"区域 {chr(65 + index)}",
            "code": format(index, "04b"),
            "x": x,
            "y": y,
            "load": load,
            "devices": DEVICE_COUNTS[index],
            "voltage": round(221 + (load - 70) * 0.05 + rng.uniform(-1.4, 1.4), 1),
            # 聚合指数 = 该区域所有设备的 DPF 聚合总量，对应论文中部门对各区域求和的结果。
            "aggregate": round(sum(DEVICE_LOADS[index]), 2),
            "status": status_of(load),
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
            "region": region["code"], "voltage": round(rng.uniform(217.5, 224.6), 1),
            "current": round(rng.uniform(3.2, 19.8), 1), "load": region["load"], "status": status,
        })
    return devices


def overview_payload():
    regions = region_rows()
    return {
        "updated_at": datetime.now().strftime("%H:%M:%S"),
        "metrics": {
            "devices": sum(r["devices"] for r in regions),
            "regions": CELLS,
            "alerts": sum(r["status"] != "normal" for r in regions),
            "latency": rng.randint(18, 25),
        },
        "regions": regions,
        "devices": build_devices(regions),
    }


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "PSDA Analytics API"})


@app.get("/api/overview")
def get_overview():
    return jsonify(overview_payload())


@app.post("/api/simulate")
def post_simulate():
    payload = request.get_json(silent=True) or {}
    try:
        ratio = float(payload.get("anomaly_ratio", DEFAULT_ANOMALY_RATIO))
    except (TypeError, ValueError):
        ratio = DEFAULT_ANOMALY_RATIO
    simulate(ratio)
    return jsonify(overview_payload())


@app.get("/api/trend")
def get_trend():
    times = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
    loads = [52, 58, 67, 62, 69, 81, 88, 74]
    return jsonify({"points": [{"time": t, "load": v + rng.randint(-2, 2)} for t, v in zip(times, loads)]})


@app.get("/api/privacy-demo")
def privacy_demo():
    regions = region_rows()
    requested = request.args.get("region")
    target = next((r for r in regions if r["code"] == requested), None)
    if target is None:
        target = max(regions, key=lambda r: r["load"])

    alpha = int(target["code"], 2)
    beta = target["load"]
    # 目标位置之外的份额两两抵消，只有 alpha 位置相加得到 beta。
    share_a = [rng.randrange(FIELD) for _ in range(CELLS)]
    share_b = [
        (beta - share_a[x]) % FIELD if x == alpha else (FIELD - share_a[x]) % FIELD
        for x in range(CELLS)
    ]

    return jsonify({
        "field": FIELD,
        "target": {
            "name": target["name"], "code": target["code"],
            "x": target["x"], "y": target["y"], "load": beta,
        },
        "keys": {
            "server_a": f"k0: {rng.randrange(1 << 24):06x}",
            "server_b": f"k1: {rng.randrange(1 << 24):06x}",
        },
        "evaluation": {
            "codes": [format(i, "04b") for i in range(CELLS)],
            "server_a": share_a,
            "server_b": share_b,
            "sum": [(a + b) % FIELD for a, b in zip(share_a, share_b)],
        },
    })


simulate(DEFAULT_ANOMALY_RATIO)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
