"""Render a static HTML mockup of the Streamlit web UI for preview purposes."""

html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stocker — Preview</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Source Sans Pro", sans-serif; background: #0e1117; color: #fafafa; display: flex; min-height: 100vh; }

  /* Sidebar */
  .sidebar { width: 260px; min-height: 100vh; background: #262730; padding: 24px 16px; flex-shrink: 0; }
  .sidebar h2 { font-size: 1.3rem; margin-bottom: 4px; }
  .sidebar .caption { font-size: 0.78rem; color: #aaa; margin-bottom: 16px; }
  .divider { border: none; border-top: 1px solid #444; margin: 14px 0; }
  .label { font-size: 0.82rem; color: #ccc; margin-bottom: 4px; margin-top: 12px; }
  .input-box { background: #0e1117; border: 1px solid #555; border-radius: 6px; padding: 7px 10px; width: 100%; color: #fafafa; font-size: 0.9rem; }
  .slider-track { background: #555; height: 4px; border-radius: 2px; margin: 8px 0; position: relative; }
  .slider-fill  { background: #ff4b4b; height: 4px; border-radius: 2px; width: 25%; }
  .slider-thumb { width: 14px; height: 14px; background: #ff4b4b; border-radius: 50%; position: absolute; top: -5px; left: 25%; }
  .btn-primary { background: #ff4b4b; color: #fff; border: none; border-radius: 6px; padding: 10px; width: 100%; font-size: 0.95rem; font-weight: 600; cursor: pointer; margin-top: 8px; }
  .btn-stop { background: transparent; color: #ff4b4b; border: 1px solid #ff4b4b; border-radius: 6px; padding: 10px; width: 100%; font-size: 0.95rem; font-weight: 600; cursor: pointer; margin-top: 8px; }

  /* Main */
  .main { flex: 1; padding: 32px 40px; }
  .ticker-row { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
  .ticker-row h2 { font-size: 1.8rem; }
  .badge-open   { background: #1b5e20; color: #69f0ae; border-radius: 12px; padding: 4px 12px; font-size: 0.82rem; font-weight: 600; }
  .badge-ts { color: #888; font-size: 0.82rem; margin-left: auto; }

  .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .metric-card { background: #262730; border-radius: 10px; padding: 16px 18px; }
  .metric-label { font-size: 0.78rem; color: #aaa; margin-bottom: 6px; }
  .metric-value { font-size: 1.5rem; font-weight: 700; }
  .metric-delta { font-size: 0.82rem; margin-top: 4px; }
  .green { color: #00e676; }
  .red   { color: #ff5252; }

  hr { border: none; border-top: 1px solid #333; margin: 20px 0; }

  .section-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 4px; }
  .section-caption { font-size: 0.8rem; color: #888; margin-bottom: 14px; }

  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th { text-align: left; padding: 10px 14px; background: #1e2130; color: #aaa; font-weight: 600; font-size: 0.8rem; border-bottom: 1px solid #333; }
  td { padding: 10px 14px; border-bottom: 1px solid #1e2130; }
  tr:hover td { background: #1a1d27; }
  .triggered-row td { background: #0d2b1a; }
  .status-triggered { color: #00e676; font-weight: 700; }
  .status-close     { color: #ffd600; font-weight: 600; }
  .status-waiting   { color: #777; }
  .gap-pos { color: #00e676; }
  .gap-neg { color: #ef5350; }

  .alert-box { background: #0d2b1a; border: 1px solid #00e676; border-radius: 8px; padding: 14px 18px; margin-bottom: 10px; font-size: 0.92rem; }
  .tip { font-size: 0.8rem; color: #777; margin-top: 10px; }
</style>
</head>
<body>

<!-- Sidebar -->
<div class="sidebar">
  <h2>📈 Stocker</h2>
  <div class="caption">Live Stock Profit Monitor</div>
  <hr class="divider">

  <div class="label">Ticker Symbol</div>
  <input class="input-box" value="AAPL" readonly>

  <div class="label">Shares Held</div>
  <input class="input-box" value="50" readonly>

  <div class="label">Average Cost Basis per Share ($)</div>
  <input class="input-box" value="145.00" readonly>

  <div class="label">Profit Target ($)</div>
  <input class="input-box" value="500.00" readonly>

  <hr class="divider">
  <div class="caption">Settings</div>
  <div class="label">Price refresh (seconds) — 10</div>
  <div class="slider-track"><div class="slider-fill"></div><div class="slider-thumb"></div></div>

  <div class="label">Scenario granularity — 5</div>
  <div class="slider-track"><div class="slider-fill" style="width:30%"></div><div class="slider-thumb" style="left:30%"></div></div>

  <hr class="divider">
  <button class="btn-stop">⏹  Stop Monitoring</button>
</div>

<!-- Main -->
<div class="main">
  <div class="ticker-row">
    <h2>AAPL</h2>
    <span class="badge-open">🟢 Market Open</span>
    <span class="badge-ts">Last update: 14:03:22 EDT &nbsp;·&nbsp; Next refresh in <strong>7s</strong></span>
  </div>

  <div class="metrics">
    <div class="metric-card">
      <div class="metric-label">Current Price</div>
      <div class="metric-value">$156.72</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Cost Basis</div>
      <div class="metric-value">$145.00</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Unrealized P&amp;L</div>
      <div class="metric-value green">+$586.00</div>
      <div class="metric-delta green">▲ +8.08%</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Profit Target</div>
      <div class="metric-value">$500.00</div>
    </div>
  </div>

  <hr>

  <div class="alert-box">
    🔔 <strong>Sell 50 share(s) @ $155.00</strong> — price target crossed at <strong>14:03:22</strong> — nets you <strong>$500.00</strong>
  </div>

  <hr>

  <div class="section-title">Sell Scenarios</div>
  <div class="section-caption">Each row shows the exact price you need to sell at to net your profit target for a given number of shares.</div>

  <table>
    <thead>
      <tr>
        <th>Shares to Sell</th>
        <th>Sell at This Price</th>
        <th>Current Price</th>
        <th>Gap to Target</th>
        <th>Status</th>
        <th>Triggered At</th>
      </tr>
    </thead>
    <tbody>
      <tr class="triggered-row">
        <td>50</td><td>$155.00</td><td>$156.72</td>
        <td class="gap-pos">+$1.72</td>
        <td class="status-triggered">✅ TRIGGERED</td>
        <td>14:03:22</td>
      </tr>
      <tr>
        <td>45</td><td>$156.11</td><td>$156.72</td>
        <td class="gap-pos">+$0.61</td>
        <td class="status-triggered">✅ TRIGGERED</td>
        <td>14:03:22</td>
      </tr>
      <tr>
        <td>40</td><td>$157.50</td><td>$156.72</td>
        <td class="gap-neg">-$0.78</td>
        <td class="status-close">🟡 Almost there</td>
        <td>—</td>
      </tr>
      <tr>
        <td>35</td><td>$159.29</td><td>$156.72</td>
        <td class="gap-neg">-$2.57</td>
        <td class="status-waiting">⏳ Waiting</td>
        <td>—</td>
      </tr>
      <tr>
        <td>30</td><td>$161.67</td><td>$156.72</td>
        <td class="gap-neg">-$4.95</td>
        <td class="status-waiting">⏳ Waiting</td>
        <td>—</td>
      </tr>
      <tr>
        <td>25</td><td>$165.00</td><td>$156.72</td>
        <td class="gap-neg">-$8.28</td>
        <td class="status-waiting">⏳ Waiting</td>
        <td>—</td>
      </tr>
      <tr>
        <td>20</td><td>$170.00</td><td>$156.72</td>
        <td class="gap-neg">-$13.28</td>
        <td class="status-waiting">⏳ Waiting</td>
        <td>—</td>
      </tr>
      <tr>
        <td>15</td><td>$178.33</td><td>$156.72</td>
        <td class="gap-neg">-$21.61</td>
        <td class="status-waiting">⏳ Waiting</td>
        <td>—</td>
      </tr>
      <tr>
        <td>10</td><td>$195.00</td><td>$156.72</td>
        <td class="gap-neg">-$38.28</td>
        <td class="status-waiting">⏳ Waiting</td>
        <td>—</td>
      </tr>
      <tr>
        <td>5</td><td>$245.00</td><td>$156.72</td>
        <td class="gap-neg">-$88.28</td>
        <td class="status-waiting">⏳ Waiting</td>
        <td>—</td>
      </tr>
    </tbody>
  </table>
  <div class="tip">💡 Tip: rows with a positive Gap are already above your sell target price. A green ✅ means a notification has fired for that row.</div>
</div>

</body>
</html>"""

with open("/tmp/stocker_web_preview.html", "w") as f:
    f.write(html)
print("Written to /tmp/stocker_web_preview.html")
