import os
import sys
import json
import time
import socket
import threading
import argparse
from functools import partial
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.append(os.getcwd())

import rerun as rr
import rerun.blueprint as rrb

from src.real_time.radar_utils.RadarParser import RadarParser
from src.data_processors.fall_detector import FallDetector
from src.helpers.doppler_to_color import doppler_to_color
from src.helpers.microdoppler import log_microdoppler


# -----------------------------------------------------------------
# Phone UI
# -----------------------------------------------------------------

PHONE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fall Detector</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;500;700&display=swap');
  :root {
    --ok:    #1d9e75;
    --warn:  #ba7517;
    --alert: #e24b4a;
    --bg:    #0d0d0d;
    --card:  #161616;
    --text:  #e8e6e0;
    --muted: #5a5856;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'Inter', sans-serif;
    min-height: 100vh; padding: 20px;
    display: flex; flex-direction: column; gap: 16px;
  }
  h1 { font-size: 11px; letter-spacing: .2em; text-transform: uppercase;
       color: var(--muted); font-weight: 500; margin-bottom: 4px; }

  /* Status card */
  #status-card {
    background: var(--card); border-radius: 20px;
    padding: 28px 24px; text-align: center;
    transition: background .3s, box-shadow .3s;
    position: relative; overflow: hidden;
  }
  #status-card.fall {
    background: #1a0505;
    box-shadow: 0 0 0 2px var(--alert);
    animation: pulse-border 1s ease-in-out infinite;
  }
  @keyframes pulse-border {
    0%,100% { box-shadow: 0 0 0 2px var(--alert); }
    50%      { box-shadow: 0 0 0 6px #e24b4a44; }
  }
  #status-icon {
    font-size: 52px; line-height: 1; margin-bottom: 10px;
    transition: transform .2s;
  }
  #status-text {
    font-size: 22px; font-weight: 700; letter-spacing: .02em;
    transition: color .3s;
  }
  #status-sub {
    font-size: 12px; color: var(--muted); margin-top: 6px;
    font-family: 'JetBrains Mono', monospace;
  }

  /* Probability bar */
  #prob-wrap {
    background: var(--card); border-radius: 16px; padding: 18px 20px;
  }
  #prob-label {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 10px;
  }
  #prob-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px; color: var(--text); font-weight: 700;
  }
  #prob-track {
    height: 8px; background: #222; border-radius: 99px; overflow: hidden;
  }
  #prob-fill {
    height: 100%; border-radius: 99px; width: 0%;
    transition: width .4s ease, background .4s;
    background: var(--ok);
  }

  /* Alert history */
  #history-card {
    background: var(--card); border-radius: 16px; padding: 18px 20px;
    flex: 1;
  }
  #history-title {
    font-size: 11px; letter-spacing: .15em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 12px;
  }
  #history-list { list-style: none; display: flex; flex-direction: column; gap: 8px; }
  .alert-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 14px; background: #1a0505;
    border-radius: 10px; border-left: 3px solid var(--alert);
    font-size: 13px;
  }
  .alert-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--alert); flex-shrink: 0; }
  .alert-time { font-family: 'JetBrains Mono', monospace; color: var(--muted); font-size: 11px; }
  .alert-prob { margin-left: auto; font-family: 'JetBrains Mono', monospace;
                font-size: 11px; color: var(--alert); }
  #no-alerts { color: var(--muted); font-size: 13px; text-align: center; padding: 20px 0; }

  /* Controls */
  #controls { display: flex; gap: 10px; }
  .ctrl-btn {
    flex: 1; padding: 14px 0; border-radius: 12px;
    border: 1px solid #2a2a2a; background: var(--card);
    color: var(--text); font-size: 13px; font-weight: 500;
    cursor: pointer; font-family: 'Inter', sans-serif;
    transition: background .15s;
  }
  .ctrl-btn:active { background: #222; }
  #mute-btn.muted { color: var(--warn); border-color: var(--warn); }

  /* Connection dot */
  #conn { display: flex; align-items: center; gap: 6px;
          font-size: 11px; color: var(--muted); }
  #conn-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); }
  #conn-dot.live { background: var(--ok); animation: blink 2s ease-in-out infinite; }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.4} }

  /* Flash overlay for fall */
  #flash {
    position: fixed; inset: 0; background: #e24b4a;
    opacity: 0; pointer-events: none; z-index: 99;
    transition: opacity .1s;
  }
  #flash.show { opacity: .18; }
</style>
</head>
<body>
<div id="flash"></div>

<div style="display:flex;justify-content:space-between;align-items:center">
  <h1>Fall Detector</h1>
  <div id="conn"><div id="conn-dot"></div><span id="conn-text">Connecting...</span></div>
</div>

<div id="status-card">
  <div id="status-icon">&#x1F6B6;</div>
  <div id="status-text" style="color:var(--ok)">Monitoring</div>
  <div id="status-sub">Waiting for radar frames...</div>
</div>

<div id="prob-wrap">
  <div id="prob-label">
    <span>Fall probability</span>
    <span id="prob-val">—</span>
  </div>
  <div id="prob-track"><div id="prob-fill"></div></div>
</div>

<div id="controls">
  <button class="ctrl-btn" id="mute-btn" onclick="toggleMute()">Mute alerts</button>
  <button class="ctrl-btn" onclick="testAlert()">Test alert</button>
  <button class="ctrl-btn" onclick="clearHistory()">Clear log</button>
</div>

<div id="history-card">
  <div id="history-title">Alert history</div>
  <ul id="history-list">
    <li id="no-alerts">No falls detected yet</li>
  </ul>
</div>

<script>
let muted = false;
let eventSource = null;
let lastAlertTime = 0;
const DEBOUNCE_MS = 3000;  // ignore repeated alerts within 3s

function connect() {
  eventSource = new EventSource('/events');

  eventSource.addEventListener('status', e => {
    const d = JSON.parse(e.data);
    document.getElementById('conn-dot').className = 'live';
    document.getElementById('conn-text').textContent = 'Live';

    const pct = Math.round(d.prob * 100);
    document.getElementById('prob-val').textContent = pct + '%';
    const fill = document.getElementById('prob-fill');
    fill.style.width = pct + '%';
    fill.style.background = pct < 30 ? 'var(--ok)' : pct < 60 ? 'var(--warn)' : 'var(--alert)';
    document.getElementById('status-sub').textContent =
      'XGB: ' + (d.p_xgb*100).toFixed(0) + '%  CNN: ' + (d.p_cnn*100).toFixed(0) + '%';
  });

  eventSource.addEventListener('fall', e => {
    const d = JSON.parse(e.data);
    const now = Date.now();
    if (now - lastAlertTime < DEBOUNCE_MS) return;
    lastAlertTime = now;
    triggerAlert(d);
  });

  eventSource.onerror = () => {
    document.getElementById('conn-dot').className = '';
    document.getElementById('conn-text').textContent = 'Reconnecting...';
    eventSource.close();
    setTimeout(connect, 2000);
  };
}

function triggerAlert(d) {
  // Visual
  const card = document.getElementById('status-card');
  card.className = 'fall';
  document.getElementById('status-icon').textContent = '\u26A0\uFE0F';
  document.getElementById('status-text').textContent = 'FALL DETECTED';
  document.getElementById('status-text').style.color = 'var(--alert)';

  const flash = document.getElementById('flash');
  flash.className = 'show';
  setTimeout(() => flash.className = '', 400);

  // Sound
  if (!muted) {
    try {
      const ctx = new AudioContext();
      [440, 550, 440, 550].forEach((f, i) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g); g.connect(ctx.destination);
        o.frequency.value = f;
        g.gain.setValueAtTime(0.4, ctx.currentTime + i*0.15);
        g.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + i*0.15 + 0.13);
        o.start(ctx.currentTime + i*0.15);
        o.stop(ctx.currentTime + i*0.15 + 0.13);
      });
    } catch(e) {}
  }

  // Add to history
  const ul = document.getElementById('history-list');
  document.getElementById('no-alerts')?.remove();
  const li = document.createElement('li');
  li.className = 'alert-item';
  const t = new Date(d.t * 1000).toLocaleTimeString();
  li.innerHTML = `<div class="alert-dot"></div>
    <span>Fall detected</span>
    <span class="alert-time">${t}</span>
    <span class="alert-prob">${(d.p_fused*100).toFixed(0)}%</span>`;
  ul.insertBefore(li, ul.firstChild);

  // Auto-clear fall state after 5s
  setTimeout(() => {
    card.className = '';
    document.getElementById('status-icon').innerHTML = '&#x1F6B6;';
    document.getElementById('status-text').textContent = 'Monitoring';
    document.getElementById('status-text').style.color = 'var(--ok)';
  }, 5000);
}

function toggleMute() {
  muted = !muted;
  fetch('/mute');
  const btn = document.getElementById('mute-btn');
  btn.textContent = muted ? 'Unmute alerts' : 'Mute alerts';
  btn.className = muted ? 'ctrl-btn muted' : 'ctrl-btn';
}

function testAlert() {
  triggerAlert({t: Date.now()/1000, p_fused: 0.92, p_xgb: 0.88, p_cnn: 0.95});
}

function clearHistory() {
  const ul = document.getElementById('history-list');
  ul.innerHTML = '<li id="no-alerts" style="color:var(--muted);font-size:13px;text-align:center;padding:20px 0">No falls detected yet</li>';
}

connect();
</script>
</body>
</html>"""


# -----------------------------------------------------------------
# HTTP + SSE server
# -----------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):

    def __init__(self, fall_detector,  *args, **kwargs):
        self.fall_detector = fall_detector
        super().__init__(*args, **kwargs)
        return

    def log_message(self, *a):
        pass

    def do_GET(self):
        global _muted
        path = self.path.split("?")[0]

        if path == "/":
            html = PHONE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        elif path == "/events":
            # Server-Sent Events — keep this connection open
            self.send_response(200)
            self.send_header("Content-Type",  "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection",    "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            client = {"wfile": self.wfile}
            with self.fall_detector._sse_lock:
                self.fall_detector._sse_clients.append(client)
            # Block until client disconnects or server stops
            while not self.fall_detector._stop_flag.is_set():
                try:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    time.sleep(15)
                except Exception:
                    break
            with self.fall_detector._sse_lock:
                if client in self.fall_detector._sse_clients:
                    self.fall_detector._sse_clients.remove(client)

        elif path == "/mute":
            _muted = not _muted
            body = json.dumps({"muted": _muted}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/stop":
            self.fall_detector._stop_flag.set()
            self._ok("Stopped.")

        else:
            self.send_response(404)
            self.end_headers()

    def _ok(self, msg: str):
        body = msg.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(fall_detector, port: int = 8766):
    # Use threading server so SSE clients don't block other requests
    from socketserver import ThreadingMixIn
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(("0.0.0.0", port), partial(_Handler, fall_detector))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "YOUR_PC_IP"

    print(f"\n  Phone UI:  http://{ip}:{port}")
    print("  (PC and phone must be on same WiFi)\n")


# -----------------------------------------------------------------
# Main radar loop
# -----------------------------------------------------------------

def run_detection_loop(radar_parser, fall_detector: FallDetector):
    point_cloud_list: list = []
    t_list:  list[float]  = []
    frame_idx = 0
    last_alert_t = 0.0
    ALERT_COOLDOWN_S = 5.0   # don't fire twice within 5s

    print(f"  Threshold: {fall_detector.threshold}  |  Ctrl+C to stop\n")

    while not fall_detector._stop_flag.is_set():
        try:
            outputDict = radar_parser.read_raw_frame_bytes()
            if not outputDict or outputDict.get("error", 0) != 0:
                frame_idx += 1
                continue

            t_now  = time.time()
            pc     = outputDict["pointCloud"]
            numPts = outputDict.get("numDetectedPoints", 0)

            rr.set_time("frame", sequence=frame_idx)

            # Rolling point cloud
            point_cloud_list.insert(0, pc)
            t_list.insert(0, t_now)
            if len(point_cloud_list) > 20:
                point_cloud_list.pop()
                t_list.pop()

            # Rerun viz
            if numPts > 0:
                tot, zg = 0, 0.0
                for i, pci in enumerate(point_cloud_list):
                    zg += np.sum(pci[:, 2])
                    rr.log(f"radar/point_cloud{i+1}", rr.Points3D(
                        positions=pci[:, 0:3], radii=0.03,
                        colors=doppler_to_color(pci[:, 3]),
                    ))
                    tot += len(pci)
                rr.log("radar/mean_height", rr.Scalars(zg / tot))

            # Micro-Doppler
            log_microdoppler(outputDict, frame_idx)

            # Extract features for this frame
            feats = fall_detector.extract_frame_features(
                pc if numPts > 0 else None, point_cloud_list, t_list)
            feat_row = np.array([feats.get(c, 0.0) for c in fall_detector.FRAME_COLS],
                                dtype=np.float32)

            # Micro-Doppler spectrum
            udoppler    = outputDict.get("microDopplerOutput")
            num_targets = outputDict.get("numTargets", 0)
            spectrum    = np.zeros(64, dtype=np.float32)
            if udoppler is not None and num_targets > 0:
                sp = np.mean(udoppler.astype(np.float32), axis=0)
                spectrum = 20.0 * np.log10(np.maximum(sp, 1e-6))

            # Push to rolling buffers
            with fall_detector._buf_lock:
                fall_detector._frame_buf.append(feat_row)
                fall_detector._md_buf.append(spectrum)

            # Run inference once buffer is full
            result = fall_detector.run_inference(
                fall_detector.xgb, 
                fall_detector.cnn,
                fall_detector.cnn_mean, 
                fall_detector.cnn_std, 
                fall_detector.cnn_window, 
                fall_detector.weights
            )

            if result is not None:
                p = result["p_fused"]

                # Push live status to phone every frame
                fall_detector.push_event("status", {
                    "prob":  round(p, 3),
                    "p_xgb": result["p_xgb"],
                    "p_cnn": result["p_cnn"],
                })

                rr.log("detection/fall_prob", rr.Scalars(p))

                # Trigger alert
                if p >= fall_detector.threshold and (t_now - last_alert_t) > ALERT_COOLDOWN_S:
                    last_alert_t = t_now
                    alert = {"t": t_now, **result}
                    fall_detector._alerts.append(alert)

                    print(f"\n  *** FALL DETECTED ***  "
                          f"p={p:.2f}  (xgb={result['p_xgb']:.2f}, "
                          f"cnn={result['p_cnn']:.2f})")

                    # Push alert to phone
                    fall_detector.push_event("fall", alert)

                    # Beep on PC
                    if not _muted:
                        threading.Thread(
                            target=lambda: [fall_detector._beep(880, 200), time.sleep(0.1),
                                            fall_detector._beep(880, 200), time.sleep(0.1),
                                            fall_detector._beep(880, 400)],
                            daemon=True
                        ).start()

            frame_idx += 1

        except KeyboardInterrupt:
            print("\nStopped.")
            fall_detector._stop_flag.set()
        except Exception as e:
            print(f"Frame {frame_idx} exception: {e}")
            frame_idx += 1


# -----------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models",    default="models/")
    parser.add_argument("--cfg",       default="cfg/Tracking_MidBw.cfg")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Fall probability threshold (0–1). Lower = more sensitive.")
    parser.add_argument("--port",      type=int, default=8766)
    args = parser.parse_args()

    print("\n  Loadifng models...")
    fall_detector = FallDetector(models_dir=args.models, threshold=args.threshold)

    print("\n  Starting phone server...")
    start_server(fall_detector=fall_detector, port=args.port)

    # Radar + Rerun
    radar_parser = RadarParser()
    rr.init("fall_detector_live")
    rr.spawn()
    time.sleep(2)

    rr.send_blueprint(rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial3DView(origin="radar"),
            rrb.Vertical(
                rrb.TimeSeriesView(origin="radar/mean_height"),
                rrb.TimeSeriesView(origin="detection/fall_prob"),
                rrb.TensorView(origin="radar/microdoppler/spectrogram"),
            )
        )
    ))

    rr.log("radar/box", rr.Boxes3D(
        centers=[[0,0,0]], half_sizes=[[0.1,0.05,0.18]],
        colors=[[255,255,255,255]]
    ))

    radar_parser.sendConfig(cfg_path=args.cfg)

    run_detection_loop(
        radar_parser, fall_detector
    )

    # Cleanup
    radar_parser.sensor_stop()
    radar_parser.warm_reset_and_wait()
    if radar_parser.cliCom and radar_parser.cliCom != "Don't Care":
        radar_parser.cliCom.close()
    if radar_parser.dataCom:
        radar_parser.dataCom.close()


if __name__ == "__main__":
    main()