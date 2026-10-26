# RTX & Ollama System Dashboard 🚀

A lightweight, real-time web dashboard built with Python (`http.server` & `ThreadingTCPServer`) and vanilla HTML/CSS (Bento Grid design) to monitor system hardware (GPU temp/power/VRAM, CPU temp, RAM, Disk) and manage local LLMs running via **Ollama** on Ubuntu workstations.

Designed with optimization in mind for **8GB VRAM GPUs (like the RTX 2060,2070,2080, Series 3, 4 With 8GB VRAM)**.

## ✨ Features
* **Real-time GPU Telemetry:** Temperature, power consumption, core utilization, and VRAM usage.
* **System Hardware Monitor:** CPU temperature, RAM consumption, and total disk space.
* **System Specifications Card:** OS, Kernel, CPU model, total RAM, total disk, Ollama version, and GPU model.
* **Ollama Model Management:** View active models in VRAM, load models on-demand, eject models, and delete models directly from disk with a custom confirmation modal.
* **Bilingual Support (I18N):** Instant toggle between Spanish (ES) and English (EN).
* **Dark / Light Mode:** Fully responsive theme switcher with persistent local storage.

---

## ⚙️ Prerequisites & Setup (Ubuntu)

1. **Install Python 3 & lm-sensors:**
   ```bash
   sudo apt update && sudo apt install -y python3 lm-sensors
   sudo sensors-detect --auto
