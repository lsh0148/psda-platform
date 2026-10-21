# PSDA 隐私保护型电力分布分析平台

本项目根据论文《Efficient and Privacy-preserving Power Distribution Analytics based on IoT》的主体流程制作，用于数字媒体课程演示。

## 功能

- 区域电力分布总览
- Hilbert 曲线空间编码动画
- IoT 设备实时监测列表
- DPF 双服务器隐私计算演示
- 区域负荷趋势和潜在异常分析

## 启动后端

```powershell
cd psda-platform
.\.venv\Scripts\python.exe .\backend\app.py
```

后端默认运行在 `http://127.0.0.1:5000`。

## 启动前端

另开一个终端：

```powershell
cd frontend
pnpm install
pnpm run dev
```

浏览器访问 `http://127.0.0.1:5173`。

## 说明

当前数据为课堂展示用的动态模拟数据。系统只定位潜在电力分布不均衡区域，不宣称能够完成精确故障定位。
