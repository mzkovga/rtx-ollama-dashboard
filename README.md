# RTX & Ollama System Dashboard

A lightweight, real-time web dashboard built with Python's standard library (`http.server`) and vanilla HTML/CSS/JS. It monitors your GPU, CPU, RAM and disk, and lets you manage local LLMs running via **[Ollama](https://ollama.com)** on Ubuntu workstations. No `pip install`, no frameworks, a single file.

Designed with **8GB VRAM GPUs** in mind: the main view shows exactly which models are taking up your VRAM.

---

## ✨ Features

- **VRAM at a glance:** a large readout with a segmented bar, one color per loaded model, plus a hatched segment for VRAM used by other processes (desktop, games, other apps).
- **GPU telemetry with history:** temperature, core utilization and power draw, each with a sparkline of the last minute. Temperature changes color as it gets hotter.
- **System monitor:** CPU temperature, RAM usage and free disk space, with color-coded bars that warn as they fill up.
- **Ollama model management:**
  - See which models are loaded, how much of each sits on the GPU (`100% GPU`, or a warning when part of it spills to CPU/RAM), its context length and when it expires from memory.
  - Browse every installed model with its size, then **load**, **eject** or **delete** it with one click (deleting asks for confirmation).
- **Ollama status indicator:** tells you whether Ollama is running (and its version) or not responding, instead of just showing an empty list.
- **System specifications:** OS, kernel, CPU model, total RAM and GPU model.
- **Bilingual (ES / EN):** instant language toggle.
- **Dark / Light mode:** theme switcher, saved in your browser. The layout adapts to small screens.
- **Light on resources:** polling pauses when the tab is hidden, and the server caches readings for about a second so several open tabs don't hammer `nvidia-smi`.

---

## 📋 Requirements

- Ubuntu (or a Debian-based distro)
- Python 3 (standard library only)
- NVIDIA GPU with drivers installed (`nvidia-smi` must work)
- `lm-sensors` for CPU temperature
- [Ollama](https://ollama.com)

---

## ⚙️ Complete Step-by-Step Installation Guide (Ubuntu)

### Step 1: System Dependencies & Temperature Sensors

To read CPU temperatures via `sensors` and GPU telemetry via `nvidia-smi`, run:

```bash
sudo apt update && sudo apt install -y python3 lm-sensors
sudo sensors-detect --auto
```

### Step 2: Install Ollama

If you don't have Ollama installed yet, use the official installation script:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 3: Download Recommended Models (Optimized for 8GB VRAM)

Run the following commands to download models that suit an 8GB VRAM setup:

| Model | Command | Notes |
|-------|---------|-------|
| DeepSeek-R1 (7B) | `ollama pull deepseek-r1:7b` | Advanced reasoning & logic |
| Llama 3.2 (3B) | `ollama pull llama3.2:3b` | Ultra-fast and lightweight |
| Gemma 2 (9B) | `ollama pull gemma2:9b` | Excellent for general reasoning & English |
| Gemma 2 (2B) | `ollama pull gemma2:2b` | Ultra-fast speed demon |
| Gemma 4 (E4B) | `ollama pull gemma4:e4b` | Compact optimized variant |

> 💡 `ollama pull` only downloads the model. If you use `ollama run <model>` instead, it also opens a chat: press `Ctrl+D` (or type `/bye`) to exit.

---

## 🚀 Running the Dashboard

1. Download or copy the `rtx_dashboard.py` file into a directory on your computer.
2. Run the Python script:

   ```bash
   python3 rtx_dashboard.py
   ```

3. Open your web browser and go to:

   ```text
   http://127.0.0.1:8090
   ```

Stop it with `Ctrl+C`.

### Configuration

Everything is optional and set through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RTX_HOST` | `127.0.0.1` | Address to listen on. See [Security](#-security) before changing it. |
| `RTX_PORT` | `8090` | Port for the dashboard. |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Where the Ollama API is running. |
| `OLLAMA_MODELS` | *(unset)* | Folder where your models are stored. If set, the disk card measures that location instead of `/` (e.g. `/usr/share/ollama/.ollama/models` for the default Linux service). |

Example:

```bash
RTX_PORT=8091 OLLAMA_MODELS=/usr/share/ollama/.ollama/models python3 rtx_dashboard.py
```

---

## 🖱️ Launch It From an Icon (Ubuntu)

Create a small launcher script that starts the server if it isn't running and opens your browser, plus a `.desktop` entry that points to it. Set `DIR` to the folder containing `rtx_dashboard.py`:

```bash
DIR="$HOME/path/to/your/folder"

cat > "$DIR/rtx_launcher.sh" <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
if ! pgrep -f "python3.*rtx_dashboard.py" >/dev/null; then
  nohup python3 rtx_dashboard.py >/dev/null 2>&1 &
  sleep 1.5
fi
xdg-open http://127.0.0.1:8090
EOF
chmod +x "$DIR/rtx_launcher.sh"

cat > ~/.local/share/applications/rtx-dashboard.desktop <<EOF
[Desktop Entry]
Type=Application
Name=RTX Dashboard
Comment=GPU and Ollama monitor
Exec=$DIR/rtx_launcher.sh
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;
EOF
chmod +x ~/.local/share/applications/rtx-dashboard.desktop
```

Then press the Super key, search for **RTX Dashboard** and launch it (right-click → *Add to Favorites* pins it to the dock). To stop the server: `pkill -f rtx_dashboard.py`.

### Optional: run it automatically at login

Create `~/.config/systemd/user/rtx-dashboard.service` (change the path to yours):

```ini
[Unit]
Description=RTX Dashboard

[Service]
ExecStart=/usr/bin/python3 /home/YOUR_USER/rtx_dashboard.py
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now rtx-dashboard
```

---

## 🔒 Security

The dashboard can unload and **delete** your models, and it has no login. By default it only listens on `127.0.0.1`, so only your own machine can reach it. In addition:

- POST requests must be `application/json`, which stops other websites open in your browser from triggering actions on the dashboard.
- Load, eject and delete only work on models that Ollama reports as installed.

If you set `RTX_HOST=0.0.0.0` to view it from another device, anyone on that network can use these controls. Only do that on a network you trust, or put the dashboard behind a reverse proxy with authentication.

---

## 🔌 API

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `GET` | `/api/stats` | – | GPU, CPU, RAM, disk, Ollama status, loaded and installed models, system specs. |
| `POST` | `/api/load` | `{"name": "model:tag"}` | Load a model into memory. |
| `POST` | `/api/stop` | `{"name": "model:tag"}` | Eject a model from memory. |
| `POST` | `/api/delete` | `{"name": "model:tag"}` | Delete a model from disk. |

---

<img width="1228" height="664" alt="image" src="https://github.com/user-attachments/assets/4eb4ad82-449b-4dca-98e3-ca86dd988883" />
<img width="1218" height="676" alt="image" src="https://github.com/user-attachments/assets/79161c23-aa47-4f3f-9bc7-d241780ba776" />



---

## 🛠️ Troubleshooting

- **GPU values show N/A:** verify that `nvidia-smi` runs correctly in your terminal.
- **CPU temperature shows N/A:** run `sudo sensors-detect --auto` again and check that `sensors` returns values.
- **"Ollama not responding":** make sure the service is running (`systemctl status ollama`, start it with `sudo systemctl start ollama`). If Ollama runs on another address, set `OLLAMA_URL`.
- **Models not listed:** the list comes from the Ollama API, so first check that the status indicator at the top says Ollama is running.
- **Loading a large model takes a while:** the Load button shows `…` until the model is in memory (up to 3 minutes before it reports an error).
- **Port 8090 already in use:** stop the other process or start the dashboard with another port, e.g. `RTX_PORT=8091 python3 rtx_dashboard.py`.
- **Disk card shows the wrong drive:** your models live on a different partition than `/`. Set `OLLAMA_MODELS` to their folder.
- **Can't open it from another device:** by design it only listens on `127.0.0.1`. See [Security](#-security) before changing `RTX_HOST`.

---

## 🤝 Contributing

Issues and pull requests are welcome. Feel free to open an issue to suggest features or report bugs.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
