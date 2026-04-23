# msbd5005

VAST 2021 Mini-Challenge 1 可视化与原始数据：根目录为分析用 JSON；`mc1-portal/` 为本地/ Pages 可部署的静态站点（需同仓 `MC1/` 与根目录 JSON）。

**本地预览**

```bash
python3 mc1-portal/generate_data.py
python3 -m http.server 8000
```

打开 `http://127.0.0.1:8000/mc1-portal/index.html` 。

**GitHub Pages**（在仓库 Settings → Pages 中启用后）

`https://<用户>.github.io/<仓库名>/mc1-portal/index.html`
