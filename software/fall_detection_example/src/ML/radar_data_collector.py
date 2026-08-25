"""
radar_record.py — Solo fall-detection recorder with phone WiFi remote.
Phone UI -> http://<your-pc-ip>:8765
Usage: python radar_record.py --subject S01 --action forward_fall --frames 500
"""

import os
import sys
import json
import time
import socket
import threading
import argparse
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.append(os.getcwd())

import rerun as rr
import rerun.blueprint as rrb

from src.real_time.radar_utils.RadarParser import RadarParser
from src.helpers.doppler_to_color import doppler_to_color
from src.helpers.microdoppler import log_microdoppler

fall_timestamps: list[float] = []
_stop_flag = threading.Event()
_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────
# Feature extraction
# Point cloud columns: x=0  y=1  z=2  doppler=3  (snr=4 if present)
# ─────────────────────────────────────────────────────────────────

FEATURE_COLS = [
    # per-frame height
    "centroid_z", "centroid_z_min", "centroid_z_max", "z_variance",
    # per-frame shape
    "bbox_height", "bbox_width", "aspect_ratio",
    # per-frame doppler
    "doppler_mean", "doppler_max", "doppler_std",
    # per-frame count
    "point_count",
    # window / temporal
    "delta_z",        # centroid drop over rolling window
    "delta_z_rate",   # drop speed m/s  (key fall signal)
    "doppler_post",   # stillness in last 3 frames
    "window_z_std",   # height variability over window
]


def extract_features(pc: np.ndarray, pc_list: list, t_list: list) -> dict:
    """
    Compute one feature vector from the current frame (pc) and
    rolling history (pc_list / t_list, newest first).
    Returns a dict keyed by FEATURE_COLS; NaN when data is insufficient.
    """
    nan = float("nan")
    feats = {k: nan for k in FEATURE_COLS}

    if pc is None or len(pc) == 0:
        return feats

    z  = pc[:, 2]
    dv = np.abs(pc[:, 3])

    # -- per-frame -------------------------------------------------
    feats["centroid_z"]     = float(np.mean(z))
    feats["centroid_z_min"] = float(np.min(z))
    feats["centroid_z_max"] = float(np.max(z))
    feats["z_variance"]     = float(np.var(z))
    feats["point_count"]    = int(len(pc))

    bh = float(np.max(z) - np.min(z))
    bw = float(max(np.max(pc[:, 0]) - np.min(pc[:, 0]),
                   np.max(pc[:, 1]) - np.min(pc[:, 1])))
    feats["bbox_height"]  = bh
    feats["bbox_width"]   = bw
    feats["aspect_ratio"] = bh / bw if bw > 0.01 else nan

    feats["doppler_mean"] = float(np.mean(dv))
    feats["doppler_max"]  = float(np.max(dv))
    feats["doppler_std"]  = float(np.std(dv))

    # -- window / temporal -----------------------------------------
    if len(pc_list) < 2:
        return feats

    cz_hist = [float(np.mean(p[:, 2])) for p in pc_list if len(p) > 0]
    feats["delta_z"]      = cz_hist[0] - cz_hist[-1]
    feats["window_z_std"] = float(np.std(cz_hist))

    if len(t_list) >= 2:
        dt = t_list[0] - t_list[-1]
        feats["delta_z_rate"] = feats["delta_z"] / dt if dt > 0 else nan

    # doppler_post: stillness check over oldest 3 frames
    post_frames = pc_list[-3:] if len(pc_list) >= 3 else pc_list
    post_dv = np.concatenate([np.abs(p[:, 3]) for p in post_frames if len(p) > 0])
    feats["doppler_post"] = float(np.mean(post_dv)) if len(post_dv) > 0 else nan

    return feats


# ─────────────────────────────────────────────────────────────────
# Micro-Doppler recorder
# ─────────────────────────────────────────────────────────────────

class MicroDopplerRecorder:
    """
    Mirrors log_microdoppler exactly:
      1. average across targets  -> (numDopplerBins,)
      2. convert to dB
      3. accumulate one spectrum per frame

    Saved files:
      _microdoppler.npy         float32  (N_frames, numDopplerBins)
                                one dB spectrum per frame, newest = last row
      _microdoppler_labels.npy  int8     (N_frames,)  0=normal, 1=fall
    """

    def __init__(self):
        self._spectra:     list[np.ndarray] = []   # each (numDopplerBins,)
        self._frame_idxs:  list[int]        = []
        self._num_bins:    int | None       = None

    def push(self, outputDict: dict, frame_idx: int) -> np.ndarray | None:
        """
        Call once per frame with the same outputDict passed to log_microdoppler.
        Returns the dB spectrum (numDopplerBins,) or None if no data.
        """
        udoppler    = outputDict.get("microDopplerOutput")   # (numTargets, numDopplerBins)
        num_targets = outputDict.get("numTargets", 0)

        if udoppler is None or num_targets == 0:
            return None

        # mirror log_microdoppler: average targets -> dB
        spectrum    = np.mean(udoppler.astype(np.float32), axis=0)          # (numDopplerBins,)
        spectrum_db = 20.0 * np.log10(np.maximum(spectrum, 1e-6))           # dB

        if self._num_bins is None:
            self._num_bins = len(spectrum_db)
            print(f"  [MicroDoppler] recording {self._num_bins} Doppler bins per frame")

        self._spectra.append(spectrum_db)
        self._frame_idxs.append(frame_idx)
        return spectrum_db

    def save(self, session_base: str,
             fall_stamps: list[float],
             t_map: dict,
             pre_fall_s:  float = 0.5,
             post_fall_s: float = 2.0):

        if not self._spectra:
            print("  [MicroDoppler] No data captured — skipping save.")
            return None

        # stack: (N_frames, numDopplerBins)
        stack  = np.stack(self._spectra, axis=0).astype(np.float32)
        labels = np.zeros(len(self._spectra), dtype=np.int8)

        for i, fidx in enumerate(self._frame_idxs):
            t = t_map.get(fidx)
            if t is None:
                continue
            for tf in fall_stamps:
                if tf - pre_fall_s <= t <= tf + post_fall_s:
                    labels[i] = 1
                    break

        md_path  = session_base + "_microdoppler.npy"
        lbl_path = session_base + "_microdoppler_labels.npy"
        np.save(md_path,  stack)
        np.save(lbl_path, labels)

        fall_count = int(labels.sum())
        print("\n  Micro-Doppler summary:")
        print(f"    Frames saved : {len(self._spectra)}")
        print(f"    Shape        : {stack.shape}  (frames, doppler_bins)")
        print(f"    Fall frames  : {fall_count} ({100*fall_count/max(len(labels),1):.1f}%)")
        print(f"    Saved -> {md_path}")
        print(f"    Saved -> {lbl_path}")
        return md_path


def _beep(freq: int, ms: int):
    try:
        import winsound
        winsound.Beep(freq, ms)
    except Exception:
        print("\a", end="", flush=True)


def countdown_and_mark(seconds: int = 5):
    print(f"\n  Countdown started — fall in {seconds}s")
    for i in range(seconds, 0, -1):
        print(f"  {i}...", flush=True)
        _beep(600, 150)
        time.sleep(0.85)
    _beep(1200, 400)
    t_fall = time.time()
    with _lock:
        fall_timestamps.append(t_fall)
    print(f"  *** FALL MARKED @ {t_fall:.3f} ***", flush=True)
    time.sleep(2.5)
    _beep(400, 200)
    print("  You can get up now.", flush=True)


PHONE_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Fall Recorder</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{display:flex;flex-direction:column;align-items:center;
      justify-content:center;min-height:100vh;
      background:#111;gap:18px;font-family:sans-serif;padding:20px;}
    h2{color:#eee;font-size:1.1rem;letter-spacing:.05em;text-transform:uppercase}
    button{width:100%;max-width:340px;padding:28px 0;border-radius:16px;
      border:none;font-size:1.4rem;font-weight:700;cursor:pointer;transition:opacity .15s;}
    button:active{opacity:.75}
    #btn-countdown{background:#1d9e75;color:#fff}
    #btn-fall{background:#e24b4a;color:#fff}
    #btn-undo{background:#444;color:#ccc;font-size:1rem;padding:18px 0}
    #btn-stop{background:#222;color:#666;font-size:.9rem;padding:14px 0}
    #status{color:#aaa;font-size:.95rem;font-family:monospace;
      text-align:center;max-width:340px;line-height:1.6;min-height:3em;}
    #falls{color:#1d9e75;font-size:.85rem;font-family:monospace}
  </style>
</head>
<body>
  <h2>Fall Recorder</h2>
  <button id='btn-countdown' onclick="cmd('/start')">START 5s countdown</button>
  <button id='btn-fall' onclick="cmd('/fall')">MARK FALL NOW</button>
  <button id='btn-undo' onclick="cmd('/undo')">Undo last mark</button>
  <div id='status'>Ready</div>
  <div id='falls'></div>
  <button id='btn-stop' onclick="cmd('/stop')">Stop recording</button>
  <script>
    function cmd(url){
      document.getElementById('status').textContent='Sending...';
      fetch(url).then(r=>r.json()).then(d=>{
        document.getElementById('status').textContent=d.msg;
        document.getElementById('falls').textContent=d.count+' fall(s) marked';
      }).catch(()=>{
        document.getElementById('status').textContent='No response - are you on the same WiFi?';
      });
    }
    setInterval(()=>fetch('/status').then(r=>r.json()).then(d=>{
      document.getElementById('falls').textContent=d.count+' fall(s) marked';
    }).catch(()=>{}),3000);
  </script>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):

    def log_message(self, *a):          # FIX 1: no stray 'c' here
        pass

    def _json(self, msg: str):          # FIX 2: _json only sends JSON
        body = json.dumps({
            "msg":   msg,
            "count": len(fall_timestamps),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            _html = PHONE_HTML.encode("utf-8")   # FIX 3: encode str -> bytes
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_html)))
            self.end_headers()
            self.wfile.write(_html)

        elif path == "/fall":
            t = time.time()
            with _lock:
                fall_timestamps.append(t)
            msg = f"FALL marked @ {t:.3f}"
            print(f"\n  *** {msg} ***", flush=True)
            self._json(msg)

        elif path == "/start":
            threading.Thread(target=countdown_and_mark, args=(5,), daemon=True).start()
            self._json("Countdown started - fall in 5s!")

        elif path == "/undo":
            with _lock:
                if fall_timestamps:
                    removed = fall_timestamps.pop()
                    msg = f"Removed mark @ {removed:.3f}"
                else:
                    msg = "Nothing to undo"
            print(f"  [{msg}]", flush=True)
            self._json(msg)

        elif path == "/stop":
            _stop_flag.set()
            self._json("Recording stopped.")

        elif path == "/status":
            self._json("ok")

        else:
            self.send_response(404)
            self.end_headers()


def start_phone_server(port: int = 8765):
    server = HTTPServer(("0.0.0.0", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "YOUR_PC_IP"
    print(f"\n  Phone remote:  http://{ip}:{port}")
    print("  (PC and phone must be on same WiFi)\n")
    return server


def run_scan_loop(radar_parser, start_idx, max_frames,
                  point_cloud_list, log_file, md_recorder: MicroDopplerRecorder,
                  N=20):
    frame_idx = start_idx
    end_idx   = start_idx + max_frames
    t_list: list[float] = []          # timestamps parallel to point_cloud_list
    t_map:  dict[int, float] = {}     # frame_idx → wall-clock time (for MD labeling)

    while frame_idx < end_idx and not _stop_flag.is_set():
        try:
            outputDict = radar_parser.read_raw_frame_bytes()
            if not outputDict or outputDict.get("error", 0) != 0:
                frame_idx += 1
                continue

            t_now  = time.time()
            pc     = outputDict["pointCloud"]
            numPts = outputDict.get("numDetectedPoints", 0)

            rr.set_time("frame", sequence=frame_idx)
            t_map[frame_idx] = t_now

            # rolling window  (newest at index 0)
            point_cloud_list.insert(0, pc)
            t_list.insert(0, t_now)
            if len(point_cloud_list) > N:
                point_cloud_list.pop()
                t_list.pop()

            if numPts > 0:
                tot_pts, z_g = 0, 0.0
                for i, pci in enumerate(point_cloud_list):
                    z_g += np.sum(pci[:, 2])
                    rr.log(f"radar/point_cloud{i+1}", rr.Points3D(
                        positions=pci[:, 0:3], radii=0.03,
                        colors=doppler_to_color(pci[:, 3]),
                    ))
                    tot_pts += len(pci)
                rr.log("radar/mean_height", rr.Scalars(z_g / tot_pts))
            else:
                print(f"Frame {frame_idx}: 0 points")

            numTracks = outputDict.get("numDetectedTracks", 0)
            if numTracks > 0:
                tracks = outputDict["trackData"][:numTracks]
                rr.log("radar/tracks", rr.Points3D(
                    positions=tracks[:, 1:4], radii=0.08,
                    labels=[str(int(tid)) for tid in tracks[:, 0]],
                ))

            # -- micro-Doppler: log to Rerun + accumulate for saving --
            log_microdoppler(outputDict, frame_idx)
            md_recorder.push(outputDict, frame_idx)

            # -- feature extraction --------------------------------
            feats = extract_features(pc if numPts > 0 else None,
                                     point_cloud_list, t_list)

            # log key features to Rerun for live inspection
            if numPts > 0:
                rr.log("features/delta_z_rate",
                       rr.Scalars(feats["delta_z_rate"] if not
                                  np.isnan(feats["delta_z_rate"]) else 0.0))
                rr.log("features/doppler_max",
                       rr.Scalars(feats["doppler_max"]))
                rr.log("features/aspect_ratio",
                       rr.Scalars(feats["aspect_ratio"] if not
                                  np.isnan(feats["aspect_ratio"]) else 0.0))

            record = {
                "frame_idx": frame_idx,
                "t":         t_now,
                "numPts":    int(numPts),
                "points":    pc.tolist() if numPts > 0 else [],
                "label":     0,
                **feats,
            }
            log_file.write(json.dumps(record) + "\n")
            log_file.flush()
            frame_idx += 1

        except KeyboardInterrupt:
            print("\nStopped by keyboard.")
            _stop_flag.set()
            return frame_idx, t_map
        except Exception as e:
            print(f"Frame {frame_idx} exception: {e}")
            frame_idx += 1

    return frame_idx, t_map


def apply_labels(jsonl_path: str, fall_stamps: list[float],
                 pre_fall_s: float = 0.5, post_fall_s: float = 2.0):
    import csv

    rows = []
    with open(jsonl_path) as f:
        for line in f:
            rows.append(json.loads(line))

    # CSV columns: metadata + all features + label
    fieldnames = ["frame_idx", "t", "numPts"] \
                 + FEATURE_COLS \
                 + ["label"]

    out_path = jsonl_path.replace(".jsonl", "_labeled.csv")
    with open(out_path, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            label = 0
            for tf in fall_stamps:
                if tf - pre_fall_s <= r["t"] <= tf + post_fall_s:
                    label = 1
                    break
            row = {k: r.get(k, float("nan")) for k in fieldnames}
            row["label"] = label
            writer.writerow(row)

    fall_frames = sum(
        1 for r in rows
        if any(tf - pre_fall_s <= r["t"] <= tf + post_fall_s for tf in fall_stamps)
    )
    print("\n  Labeling summary:")
    print(f"    Total frames : {len(rows)}")
    print(f"    Fall frames  : {fall_frames} ({100*fall_frames/max(len(rows),1):.1f}%)")
    print(f"    Features     : {FEATURE_COLS}")
    print(f"    Saved -> {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="S01")
    parser.add_argument("--action",  default="fall")
    parser.add_argument("--frames",  type=int, default=2000)
    parser.add_argument("--port",    type=int, default=8765)
    parser.add_argument("--cfg",     default="cfg/Tracking_MidBw.cfg")
    args = parser.parse_args()

    os.makedirs("data/sessions", exist_ok=True)
    tag          = f"{args.subject}_{args.action}_{int(time.time())}"
    session_base = f"data/sessions/{tag}"

    session_meta = {
        "subject_id": args.subject, "action": args.action,
        "radar_height_m": 0.85, "cfg": args.cfg,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    start_phone_server(port=args.port)

    radar_parser = RadarParser()
    rr.init("radar_3d_viz")
    rr.spawn()
    time.sleep(2)

    rr.send_blueprint(rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial3DView(origin="radar"),
            rrb.Vertical(
                rrb.TimeSeriesView(origin="radar/mean_height"),
                rrb.TensorView(origin="radar/microdoppler/spectrogram"),
            )
        )
    ))

    rr.log("radar/box", rr.Boxes3D(
        centers=[[0,0,0]], half_sizes=[[0.1,0.05,0.18]],
        colors=[[255,255,255,255]]
    ))

    point_cloud_list = []
    md_recorder      = MicroDopplerRecorder()
    radar_parser.sendConfig(cfg_path=args.cfg)

    print(f"\n  Recording session: {tag}")
    print(f"  Max frames: {args.frames}  |  Ctrl+C or tap STOP on phone\n")

    with open(session_base + ".jsonl", "w") as log_file:
        frame_idx, t_map = run_scan_loop(
            radar_parser=radar_parser, start_idx=0, max_frames=args.frames,
            point_cloud_list=point_cloud_list, log_file=log_file,
            md_recorder=md_recorder, N=20,
        )

    session_meta["total_frames"]    = frame_idx
    session_meta["fall_timestamps"] = fall_timestamps
    session_meta["num_falls"]       = len(fall_timestamps)

    with open(session_base + "_meta.json", "w") as f:
        json.dump(session_meta, f, indent=2)

    apply_labels(session_base + ".jsonl", fall_timestamps)

    md_recorder.save(
        session_base  = session_base,
        fall_stamps   = fall_timestamps,
        t_map         = t_map,
        pre_fall_s    = 0.5,
        post_fall_s   = 2.0,
    )

    _stop_flag.set()
    radar_parser.sensor_stop()
    radar_parser.warm_reset_and_wait()
    if radar_parser.cliCom and radar_parser.cliCom != "Don't Care":
        radar_parser.cliCom.close()
    if radar_parser.dataCom:
        radar_parser.dataCom.close()

    print("\n  Done. Files saved:")
    print(f"    {session_base}.jsonl")
    print(f"    {session_base}_meta.json")
    print(f"    {session_base}_labeled.csv")
    print(f"    {session_base}_microdoppler.npy")
    print(f"    {session_base}_microdoppler_labels.npy")


if __name__ == "__main__":
    main()