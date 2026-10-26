# RTX & Ollama System Dashboard 🚀

A lightweight, real-time web dashboard built with Python (`http.server` & `ThreadingTCPServer`) and vanilla HTML/CSS (Bento Grid design) to monitor system hardware (GPU temp/power/VRAM, CPU temp, RAM, Disk) and manage local LLMs running via **[Ollama](https://ollama.com)** on Ubuntu workstations.

Designed with optimization in mind for **8GB VRAM GPUs**.

---

## ✨ Features

- **Real-time GPU Telemetry:** Temperature, power consumption, core utilization, and VRAM usage.
- **System Hardware Monitor:** CPU temperature, RAM consumption, and total disk space.
- **System Specifications Card:** OS, Kernel, CPU model, total RAM, total disk, Ollama version, and GPU model.
- **Ollama Model Management:** View active models in VRAM, load models on demand, eject models, and delete models directly from disk with a custom confirmation modal.
- **Bilingual Support (I18N):** Instant toggle between Spanish (ES) and English (EN).
- **Dark / Light Mode:** Fully responsive theme switcher with persistent local storage.

---

## 📋 Requirements

- Ubuntu (or a Debian-based distro)
- Python 3
- NVIDIA GPU with drivers installed (`nvidia-smi` must work)
- `lm-sensors` for CPU temperature
- [Ollama](https://ollama.com)

---

## ⚙️ Complete Step-by-Step Installation Guide (Ubuntu)

### Step 1: System Dependencies & Temperature Sensors

To allow Python to read your CPU temperatures via `sensors` and GPU telemetry via `nvidia-smi`, run the following commands in your terminal:

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

Run the following commands one by one to pull the best local models suited for an 8GB VRAM setup:

| Model | Command | Notes |
|-------|---------|-------|
| DeepSeek-R1 (7B) | `ollama run deepseek-r1:7b` | Advanced reasoning & logic |
| Llama 3.2 (3B) | `ollama run llama3.2:3b` | Ultra-fast and lightweight |
| Gemma 2 (9B) | `ollama run gemma2:9b` | Excellent for general reasoning & English |
| Gemma 2 (2B) | `ollama run gemma2:2b` | Ultra-fast speed demon |
| Gemma 4 (E4B) | `ollama run gemma4:e4b` | Compact optimized variant |

> 💡 `ollama run` downloads the model and opens a chat. Press `Ctrl+D` (or type `/bye`) to exit. If you only want to download, use `ollama pull <model>` instead.

---

## 🚀 Running the Dashboard

1. Download or copy the `rtx_dashboard.py` file into a directory on your computer.
2. Run the Python script:

   ```bash
   python3 rtx_dashboard.py
   ```

3. Open your web browser and go to:

   ```text
   http://localhost:8090
   ```

---

## 🛠️ Troubleshooting

- **GPU data not showing:** verify that `nvidia-smi` runs correctly in your terminal.
- **CPU temperature shows N/A:** run `sudo sensors-detect --auto` again and check that `sensors` returns values.
- **Ollama models not listed:** make sure the Ollama service is running (`systemctl status ollama`).
- **Port 8090 already in use:** stop the other process or change the port in `rtx_dashboard.py`.

---

## 🤝 Contributing

Issues and pull requests are welcome. Feel free to open an issue to suggest features or report bugs.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
