from datetime import datetime
from random import Random

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GRID_SIZES = (4, 8, 16)
DEFAULT_GRID = 4
TOTAL_DEVICES = 768
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


class GridState:
    """当前演示网格及其随机负荷状态。"""

    def __init__(self):
        self.rng = Random()
        self.size = DEFAULT_GRID
        self.configure(DEFAULT_GRID)

    def configure(self, size):
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = DEFAULT_GRID
        if size not in GRID_SIZES:
            size = DEFAULT_GRID
        self.size = size
        self.cells = size * size
        self.order = hilbert_cells(size)
        self.code_width = len(format(self.cells - 1, "b"))
        # 物理区域不变，网格变细只改变设备归属，不改变接入设备总量。
        base_count, remainder = divmod(TOTAL_DEVICES, self.cells)
        self.device_counts = [
            base_count + (1 if index < remainder else 0)
            for index in range(self.cells)
        ]
        self.device_loads = [[] for _ in range(self.cells)]
        self.loads = [0] * self.cells

    def code(self, index):
        return format(index, f"0{self.code_width}b")

    def simulate(self, anomaly_ratio):
        """为每个区域分配随机负荷，并按比例注入偏高和异常区域。"""
        ratio = max(0.0, min(1.0, anomaly_ratio))
        attention_count = round(self.cells * ratio)
        attention_regions = self.rng.sample(range(self.cells), attention_count)
        critical_count = attention_count // 2
        critical_regions = set(attention_regions[:critical_count])
        warning_regions = set(attention_regions[critical_count:])
        for index in range(self.cells):
            if index in critical_regions:
                self.loads[index] = self.rng.randint(88, 98)
            elif index in warning_regions:
                self.loads[index] = self.rng.randint(74, 87)
            else:
                self.loads[index] = self.rng.randint(45, 72)
            self.device_loads[index] = [
                self.rng.uniform(0.6, 1.9) for _ in range(self.device_counts[index])
            ]


state = GridState()


def simulate(anomaly_ratio):
    state.simulate(anomaly_ratio)


def region_name(index):
    if index < 26:
        return f"区域 {chr(65 + index)}"
    return f"区域 {index + 1:02d}"


def status_of(load):
    if load >= 88:
        return "critical"
    if load >= 74:
        return "warning"
    return "normal"


def region_rows():
    rows = []
    for index, ((x, y), load) in enumerate(zip(state.order, state.loads)):
        rows.append({
            "name": region_name(index),
            "code": state.code(index),
            "x": x,
            "y": y,
            "load": load,
            "devices": state.device_counts[index],
            "voltage": round(221 + (load - 70) * 0.05 + state.rng.uniform(-1.4, 1.4), 1),
            # 聚合指数 = 该区域所有设备的 DPF 聚合总量，对应论文中部门对各区域求和的结果。
            "aggregate": round(sum(state.device_loads[index]), 2),
            "status": status_of(load),
        })
    return rows


def build_devices(regions):
    """为每个空间区域生成一个汇集区域终端设备的感知节点。"""
    node_names = [
        "智能电表汇聚节点", "充电站监测节点", "配电变压器监测节点", "光伏接入监测节点",
        "储能单元监测节点", "配电柜监测节点", "线路负荷监测节点", "园区用电监测节点",
    ]
    devices = []
    for index, region in enumerate(regions):
        suffix = region["name"].split(" ", 1)[-1]
        devices.append({
            "id": f"PSDA-N{index + 1:03d}",
            "name": f"{node_names[index % len(node_names)]} {suffix}",
            "region": region["code"], "voltage": round(state.rng.uniform(217.5, 224.6), 1),
            "managed_devices": region["devices"], "load": region["load"], "status": region["status"],
        })
    return devices


def overview_payload():
    regions = region_rows()
    return {
        "updated_at": datetime.now().strftime("%H:%M:%S"),
        "grid_size": state.size,
        "grid_cells": state.cells,
        "metrics": {
            "devices": sum(r["devices"] for r in regions),
            "regions": state.cells,
            "alerts": sum(r["status"] != "normal" for r in regions),
            "latency": state.rng.randint(18, 25),
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
    requested_size = payload.get("size", state.size)
    try:
        ratio = float(payload.get("anomaly_ratio", DEFAULT_ANOMALY_RATIO))
    except (TypeError, ValueError):
        ratio = DEFAULT_ANOMALY_RATIO
    try:
        requested_size = int(requested_size)
    except (TypeError, ValueError):
        requested_size = state.size
    if requested_size in GRID_SIZES and requested_size != state.size:
        state.configure(requested_size)
    simulate(ratio)
    return jsonify(overview_payload())


@app.get("/api/trend")
def get_trend():
    return jsonify({
        "points": [
            {"time": state.code(index), "load": load}
            for index, load in enumerate(state.loads)
        ]
    })


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
    share_a = [state.rng.randrange(FIELD) for _ in range(state.cells)]
    share_b = [
        (beta - share_a[x]) % FIELD if x == alpha else (FIELD - share_a[x]) % FIELD
        for x in range(state.cells)
    ]

    return jsonify({
        "field": FIELD,
        "target": {
            "name": target["name"], "code": target["code"],
            "x": target["x"], "y": target["y"], "load": beta,
        },
        "keys": {
            "server_a": f"k0: {state.rng.randrange(1 << 24):06x}",
            "server_b": f"k1: {state.rng.randrange(1 << 24):06x}",
        },
        "evaluation": {
            "codes": [state.code(i) for i in range(state.cells)],
            "server_a": share_a,
            "server_b": share_b,
            "sum": [(a + b) % FIELD for a, b in zip(share_a, share_b)],
        },
    })


simulate(DEFAULT_ANOMALY_RATIO)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
