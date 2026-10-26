#!/usr/bin/env python3
import http.server
import socketserver
import json
import urllib.request
import urllib.error
import subprocess
import shutil
import glob
import re

HOST = '0.0.0.0'
PORT = 8090
OLLAMA_PS_URL = 'http://127.0.0.1:11434/api/ps'
OLLAMA_TAGS_URL = 'http://127.0.0.1:11434/api/tags'

# --- ESPECIFICACIONES ESTÁTICAS DEL SISTEMA ---
def get_system_specs():
    specs = {
        'cpu': 'Desconocido',
        'ram_total_gb': 0,
        'disk_total_gb': 0,
        'os_name': 'Ubuntu Linux',
        'kernel': 'Desconocido',
        'gpu_model': 'NVIDIA GeForce RTX 2070',
        'ollama_version': 'Desconocido'
    }
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'model name' in line:
                    specs['cpu'] = line.split(':')[1].strip()
                    break
    except: pass

    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemTotal' in line:
                    kb = int(line.split()[1])
                    specs['ram_total_gb'] = round(kb / (1024 * 1024), 1)
                    break
    except: pass

    try:
        total, _, _ = shutil.disk_usage("/")
        specs['disk_total_gb'] = round(total / (2**30), 1)
    except: pass

    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    specs['os_name'] = line.split('=')[1].strip().strip('"')
                    break
    except: pass

    try:
        res = subprocess.run(['uname', '-r'], capture_output=True, text=True, timeout=3)
        if res.returncode == 0: specs['kernel'] = res.stdout.strip()
    except: pass

    try:
        res = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], capture_output=True, text=True, timeout=3)
        if res.returncode == 0: specs['gpu_model'] = res.stdout.strip()
    except: pass

    try:
        res = subprocess.run(['ollama', '--version'], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            # Ejemplo de salida: "ollama version is 0.5.7" o similar
            ver_text = res.stdout.strip()
            specs['ollama_version'] = ver_text.replace('ollama version is ', '').replace('ollama version ', 'v')
    except: pass

    return specs

CACHED_SPECS = get_system_specs()

# --- LECTURA DINÁMICA DE CPU TEMP Y RAM ---
def get_dynamic_system_stats():
    cpu_temp = 0.0
    try:
        res = subprocess.run(['sensors'], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            for line in res.stdout.split('\n'):
                if any(k in line for k in ['Core 0', 'Tctl', 'Tdie', 'Package id 0', 'CPU Temperature', 'temp1']):
                    match = re.search(r'\+?([0-9]+\.[0-9]+)°C', line)
                    if match:
                        cpu_temp = float(match.group(1))
                        break
        if cpu_temp == 0.0:
            match = re.search(r'\+?([0-9]+\.[0-9]+)°C', res.stdout)
            if match: cpu_temp = float(match.group(1))
    except: pass

    if cpu_temp == 0.0:
        try:
            for tf in glob.glob('/sys/class/thermal/thermal_zone*/temp'):
                with open(tf, 'r') as f:
                    val = float(f.read().strip())
                    if val > 1000: val = val / 1000.0
                    if 0 < val < 110:
                        cpu_temp = val
                        break
        except: pass

    ram_used_gb = 0.0
    ram_total_gb = 0.0
    ram_percent = 0.0
    try:
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2: meminfo[parts[0].strip()] = int(parts[1].split()[0])
        
        total_kb = meminfo.get('MemTotal', 0)
        free_kb = meminfo.get('MemFree', 0)
        buffers_kb = meminfo.get('Buffers', 0)
        cached_kb = meminfo.get('Cached', 0)
        used_kb = total_kb - (free_kb + buffers_kb + cached_kb)
        
        ram_total_gb = round(total_kb / (1024 * 1024), 1)
        ram_used_gb = round(used_kb / (1024 * 1024), 1)
        ram_percent = round((used_kb / total_kb) * 100, 1) if total_kb > 0 else 0.0
    except: pass

    return {
        'cpu_temp': round(cpu_temp, 1),
        'ram_used_gb': ram_used_gb,
        'ram_total_gb': ram_total_gb,
        'ram_percent': ram_percent
    }

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RTX Dashboard</title>
    <style>
        :root {
            --bg: #0f172a; --card: #1e293b; --border: #334155;
            --text: #f8fafc; --text-muted: #94a3b8; --green: #10b981; 
            --red: #ef4444; --blue: #3b82f6; --purple: #8b5cf6; --amber: #f59e0b;
            --bar-bg: #334155; --item-bg: rgba(255,255,255,0.05);
        }
        [data-theme="light"] {
            --bg: #f1f5f9; --card: #ffffff; --border: #cbd5e1;
            --text: #0f172a; --text-muted: #64748b; --green: #059669; 
            --red: #dc2626; --blue: #2563eb; --purple: #7c3aed; --amber: #d97706;
            --bar-bg: #e2e8f0; --item-bg: rgba(0,0,0,0.03);
        }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background-color: var(--bg); color: var(--text);
            margin: 0; padding: 20px; display: flex;
            flex-direction: column; align-items: center; min-height: 100vh;
        }
        .header-container { display: flex; justify-content: space-between; align-items: center; width: 100%; max-width: 1000px; margin-bottom: 20px; }
        h1 { margin: 0; font-weight: 300; letter-spacing: 1px; }
        .controls-group { display: flex; gap: 10px; align-items: center; }
        .btn-control { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 8px 14px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.9em; }
        .btn-control:hover { opacity: 0.8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; width: 100%; max-width: 1000px; }
        .card { background-color: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .card-header { font-size: 0.9em; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; }
        .value { font-size: 1.5em; font-weight: 600; margin-bottom: 4px; }
        .sub-value { font-size: 0.85em; color: var(--text); display: flex; align-items: center; gap: 8px; opacity: 0.9; }
        .bar-container { width: 100%; height: 8px; background-color: var(--bar-bg); border-radius: 4px; margin-top: 8px; overflow: hidden; }
        .bar-fill { height: 100%; width: 0%; transition: width 0.3s ease, background-color 0.3s; }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 0.8em; font-weight: 600; background-color: #475569; color: #fff; margin-top: 8px; }
        .model-item { background: var(--item-bg); margin-top: 8px; padding: 10px; border-radius: 6px; font-size: 0.9em; border-left: 3px solid var(--blue); }
        .model-header { display: flex; justify-content: space-between; align-items: center; font-weight: bold; }
        .model-meta { font-size: 0.8em; color: var(--text-muted); margin-top: 4px; }
        .spec-row { display: flex; justify-content: space-between; font-size: 0.85em; margin-top: 8px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
        .spec-label { color: var(--text-muted); }
        .spec-val { font-weight: 600; color: var(--text); text-align: right; max-width: 60%; word-break: break-word; }
        .load-box { margin-top: 15px; display: grid; grid-template-columns: 1fr auto auto; gap: 6px; align-items: center; width: 100%; }
        .load-select { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px; color: var(--text); font-size: 0.85em; height: 38px; box-sizing: border-box; }
        .btn-load { background-color: var(--blue); color: white; border: none; padding: 0 12px; border-radius: 6px; cursor: pointer; font-weight: 600; height: 38px; }
        .btn-delete { background-color: var(--red); color: white; border: none; padding: 0 10px; border-radius: 6px; cursor: pointer; font-weight: 600; height: 38px; }
        .btn-stop { background-color: var(--red); color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.75em; }
        .error-msg { color: var(--red); font-size: 0.9em; margin-top: 10px; display: none; }
    </style>
</head>
<body>
    <div class="header-container">
        <h1>RTX System Monitor</h1>
        <div class="controls-group">
            <button class="btn-control" onclick="toggleLanguage()" id="lang-btn">🇺🇸 EN</button>
            <button class="btn-control" onclick="toggleTheme()">🌓 <span data-i18n="theme">Tema</span></button>
        </div>
    </div>
    <div id="error-container" class="error-msg">Error: No se pudo conectar con el servidor local.</div>
    <div class="grid">
        <!-- 1. GPU Temp & Power -->
        <div class="card">
            <div class="card-header" data-i18n="gpu_temp">Temperatura GPU</div>
            <div class="value" id="val-temp">-- °C</div>
            <div class="bar-container"><div id="bar-temp" class="bar-fill" style="background-color: var(--green);"></div></div>
            <div class="card-header" style="margin-top: 15px;" data-i18n="gpu_power">Consumo (Watts)</div>
            <div class="value" id="val-power">-- W</div>
            <div class="sub-value">
                <div class="bar-container" style="flex:1;"><div id="bar-power" class="bar-fill" style="background-color: var(--blue);"></div></div>
                <span style="font-size: 0.75em;"><span data-i18n="limit">Límite</span>: <span id="val-power-limit">--</span>W</span>
            </div>
        </div>
        <!-- 2. GPU Util & VRAM -->
        <div class="card">
            <div class="card-header" data-i18n="gpu_util">Utilización GPU</div>
            <div class="value" id="val-util">-- %</div>
            <div class="bar-container"><div id="bar-util" class="bar-fill" style="background-color: var(--green);"></div></div>
            <div class="card-header" style="margin-top: 15px;" data-i18n="vram_used">VRAM Usada</div>
            <div class="value" id="val-vram">-- MiB</div>
            <div class="sub-value">
                <div class="bar-container" style="flex:1;"><div id="bar-vram" class="bar-fill" style="background-color: var(--green);"></div></div>
                <span style="font-size: 0.75em;"><span data-i18n="total">Total</span>: 8192 MiB</span>
            </div>
        </div>
        <!-- 3. Disco -->
        <div class="card">
            <div class="card-header" data-i18n="disk_space">Espacio en Disco</div>
            <div class="value" id="val-disk-free">-- GB Libres</div>
            <div class="bar-container"><div id="bar-disk" class="bar-fill" style="background-color: var(--purple);"></div></div>
            <div class="sub-value" style="margin-top: 12px; justify-content: space-between;">
                <span><span data-i18n="used">Usado</span>: <strong id="val-disk-used">-- GB</strong></span>
                <span><span data-i18n="total">Total</span>: <strong id="val-disk-total">-- GB</strong></span>
            </div>
        </div>
        <!-- 4. CPU Temp -->
        <div class="card">
            <div class="card-header" data-i18n="cpu_temp">Temperatura CPU</div>
            <div class="value" id="val-cpu-temp">-- °C</div>
            <div class="bar-container"><div id="bar-cpu-temp" class="bar-fill" style="background-color: var(--amber);"></div></div>
            <div class="sub-value" style="margin-top: 15px;"><span data-i18n="cpu_thermal">Estado térmico del procesador</span></div>
        </div>
        <!-- 5. RAM -->
        <div class="card">
            <div class="card-header" data-i18n="ram_used">Memoria RAM Usada</div>
            <div class="value" id="val-ram-used">-- GB</div>
            <div class="bar-container"><div id="bar-ram" class="bar-fill" style="background-color: var(--blue);"></div></div>
            <div class="sub-value" style="margin-top: 12px; justify-content: space-between;">
                <span><span data-i18n="usage">Uso</span>: <strong id="val-ram-pct">--%</strong></span>
                <span><span data-i18n="total">Total</span>: <strong id="val-ram-total">-- GB</strong></span>
            </div>
        </div>
        <!-- 6. Specs -->
        <div class="card">
            <div class="card-header" data-i18n="sys_specs">Specs del Sistema</div>
            <div class="spec-row"><span class="spec-label">OS:</span><span class="spec-val" id="spec-os">--</span></div>
            <div class="spec-row"><span class="spec-label">Kernel:</span><span class="spec-val" id="spec-kernel">--</span></div>
            <div class="spec-row"><span class="spec-label" data-i18n="processor">Procesador</span>:</span><span class="spec-val" id="spec-cpu">--</span></div>
            <div class="spec-row"><span class="spec-label">RAM Total:</span><span class="spec-val" id="spec-ram">--</span></div>
            <div class="spec-row"><span class="spec-label">Disco Total:</span><span class="spec-val" id="spec-disk">--</span></div>
            <div class="spec-row"><span class="spec-label">Ollama Ver:</span><span class="spec-val" id="spec-ollama">--</span></div>
            <div class="spec-row" style="border-bottom:none;"><span class="spec-label">GPU:</span><span class="spec-val" id="spec-gpu">--</span></div>
        </div>
        <!-- 7. Ollama Control -->
        <div class="card" style="grid-column: 1 / -1;">
            <div class="card-header" data-i18n="ollama_title">Ollama Activo y Gestión de Modelos</div>
            <div id="ollama-status" class="status-badge">Verificando...</div>
            <div id="models-list" style="margin-top: 10px;"><div class="model-meta" data-i18n="no_models_vram">Sin modelos en VRAM</div></div>
            <div class="load-box">
                <select id="model-select" class="load-select"><option value="" data-i18n="select_model">-- Seleccionar --</option></select>
                <button class="btn-load" onclick="loadModel()" data-i18n="btn_load">Cargar</button>
                <button class="btn-delete" onclick="deleteModel()" title="Eliminar del disco">🗑️</button>
            </div>
        </div>
    </div>
    <script>
        const translations = {
            es: {
                theme: "Tema",
                gpu_temp: "Temperatura GPU",
                gpu_power: "Consumo (Watts)",
                limit: "Límite",
                gpu_util: "Utilización GPU",
                vram_used: "VRAM Usada",
                total: "Total",
                disk_space: "Espacio en Disco",
                free: "Libres",
                used: "Usado",
                cpu_temp: "Temperatura CPU",
                cpu_thermal: "Estado térmico del procesador",
                ram_used: "Memoria RAM Usada",
                usage: "Uso",
                sys_specs: "Specs del Sistema",
                processor: "Procesador",
                ollama_title: "Ollama Activo y Gestión de Modelos",
                no_models_vram: "Sin modelos en VRAM",
                gpu_free: "GPU Libre / Sin modelos",
                select_model: "-- Seleccionar --",
                btn_load: "Cargar",
                loading: "Cargando...",
                online: "Online",
                eject: "Expulsar",
                confirm_eject: "¿Expulsar",
                confirm_delete: "¿Estás seguro de borrar",
                from_disk: "del disco duro?"
            },
            en: {
                theme: "Theme",
                gpu_temp: "GPU Temperature",
                gpu_power: "Power Draw (Watts)",
                limit: "Limit",
                gpu_util: "GPU Utilization",
                vram_used: "VRAM Used",
                total: "Total",
                disk_space: "Disk Space",
                free: "Free",
                used: "Used",
                cpu_temp: "CPU Temperature",
                cpu_thermal: "Processor thermal state",
                ram_used: "RAM Memory Used",
                usage: "Usage",
                sys_specs: "System Specs",
                processor: "Processor",
                ollama_title: "Active Ollama & Model Management",
                no_models_vram: "No models in VRAM",
                gpu_free: "GPU Free / No models",
                select_model: "-- Select Model --",
                btn_load: "Load",
                loading: "Loading...",
                online: "Online",
                eject: "Eject",
                confirm_eject: "Eject",
                confirm_delete: "Are you sure to delete",
                from_disk: "from hard drive?"
            }
        };

        function getLang() {
            return localStorage.getItem('rtx_lang') || 'es';
        }

        function setLanguage(lang) {
            localStorage.setItem('rtx_lang', lang);
            document.getElementById('lang-btn').textContent = lang === 'es' ? '🇺🇸 EN' : '🇪🇸 ES';
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (translations[lang][key]) {
                    el.textContent = translations[lang][key];
                }
            });
        }

        function toggleLanguage() {
            const current = getLang();
            setLanguage(current === 'es' ? 'en' : 'es');
            fetchData();
        }

        function applyTheme(theme) {
            if (theme === 'light') { document.documentElement.setAttribute('data-theme', 'light'); }
            else { document.documentElement.removeAttribute('data-theme'); }
            localStorage.setItem('rtx_theme', theme);
        }
        function toggleTheme() {
            applyTheme((localStorage.getItem('rtx_theme') || 'dark') === 'dark' ? 'light' : 'dark');
        }
        
        applyTheme(localStorage.getItem('rtx_theme') || 'dark');
        setLanguage(getLang());

        async function stopModel(name) {
            const lang = getLang();
            if (!confirm(`${translations[lang].confirm_eject} ${name}?`)) return;
            await fetch('/api/stop', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) });
            fetchData();
        }
        async function loadModel() {
            const name = document.getElementById('model-select').value;
            const lang = getLang();
            if (!name) return alert(lang === 'es' ? 'Selecciona un modelo' : 'Select a model');
            await fetch('/api/load', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) });
            setTimeout(fetchData, 2000);
        }
        async function deleteModel() {
            const name = document.getElementById('model-select').value;
            const lang = getLang();
            if (!name) return alert(lang === 'es' ? 'Selecciona un modelo' : 'Select a model');
            if (!confirm(`${translations[lang].confirm_delete} "${name}" ${translations[lang].from_disk}`)) return;
            await fetch('/api/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) });
            setTimeout(fetchData, 1000);
        }

        function updateDashboard(data) {
            const lang = getLang();
            const t = translations[lang];

            document.getElementById('error-container').style.display = 'none';
            document.getElementById('val-temp').textContent = `${data.temperature} °C`;
            document.getElementById('bar-temp').style.width = `${Math.min(data.temperature, 100)}%`;
            document.getElementById('val-power').textContent = `${data.power.toFixed(1)} W`;
            document.getElementById('val-power-limit').textContent = data.power_limit.toFixed(1);
            const pPct = (data.power / data.power_limit) * 100;
            document.getElementById('bar-power').style.width = `${Math.min(pPct, 100)}%`;

            document.getElementById('val-util').textContent = `${data.utilization}%`;
            document.getElementById('bar-util').style.width = `${data.utilization}%`;
            
            const vram = data.vram_used_mb || 0;
            const vramPct = (vram / 8192) * 100;
            document.getElementById('val-vram').textContent = `${vram} MiB`;
            document.getElementById('bar-vram').style.width = `${vramPct}%`;

            if (data.disk) {
                document.getElementById('val-disk-free').textContent = `${data.disk.free_gb} GB ${t.free}`;
                document.getElementById('val-disk-used').textContent = `${data.disk.used_gb} GB`;
                document.getElementById('val-disk-total').textContent = `${data.disk.total_gb} GB`;
                document.getElementById('bar-disk').style.width = `${data.disk.percent}%`;
            }

            if (data.sys_dynamic) {
                const cTemp = data.sys_dynamic.cpu_temp;
                document.getElementById('val-cpu-temp').textContent = cTemp > 0 ? `${cTemp} °C` : 'N/A';
                document.getElementById('bar-cpu-temp').style.width = `${Math.min(cTemp, 100)}%`;

                document.getElementById('val-ram-used').textContent = `${data.sys_dynamic.ram_used_gb} GB`;
                document.getElementById('val-ram-pct').textContent = `${data.sys_dynamic.ram_percent}%`;
                document.getElementById('val-ram-total').textContent = `${data.sys_dynamic.ram_total_gb} GB`;
                document.getElementById('bar-ram').style.width = `${data.sys_dynamic.ram_percent}%`;
            }

            if (data.specs) {
                document.getElementById('spec-os').textContent = data.specs.os_name;
                document.getElementById('spec-kernel').textContent = data.specs.kernel;
                document.getElementById('spec-cpu').textContent = data.specs.cpu;
                document.getElementById('spec-ram').textContent = `${data.specs.ram_total_gb} GB`;
                document.getElementById('spec-disk').textContent = `${data.specs.disk_total_gb} GB`;
                document.getElementById('spec-ollama').textContent = data.specs.ollama_version;
                document.getElementById('spec-gpu').textContent = data.specs.gpu_model;
            }

            const select = document.getElementById('model-select');
            const current = select.value;
            if (data.available_models) {
                select.innerHTML = `<option value="">${t.select_model}</option>` + 
                    data.available_models.map(m => `<option value="${m}" ${m===current?'selected':''}>${m}</option>`).join('');
            }

            const status = document.getElementById('ollama-status');
            const list = document.getElementById('models-list');
            if (data.ollama_models && data.ollama_models.length > 0) {
                status.textContent = t.online; status.style.backgroundColor = "var(--green)"; status.style.color = "#000";
                list.innerHTML = data.ollama_models.map(m => `
                    <div class="model-item">
                        <div class="model-header"><span>${m.name}</span><button class="btn-stop" onclick="stopModel('${m.name}')">${t.eject}</button></div>
                        <div class="model-meta">VRAM: ${m.size_vram_mb} MiB</div>
                    </div>`).join('');
            } else {
                status.textContent = t.gpu_free; status.style.backgroundColor = "#475569"; status.style.color = "#fff";
                list.innerHTML = `<div class="model-meta">${t.no_models_vram}</div>`;
            }
        }

        async function fetchData() {
            try {
                const res = await fetch('/api/stats');
                if (!res.ok) throw new Error();
                updateDashboard(await res.json());
            } catch {
                document.getElementById('error-container').style.display = 'block';
            }
        }
        setInterval(fetchData, 2000);
        fetchData();
    </script>
</body>
</html>
"""

def run_server():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length).decode('utf-8'))
                name = body.get('name')
                if self.path == '/api/stop' and name:
                    subprocess.run(['ollama', 'stop', name], capture_output=True, timeout=5)
                elif self.path == '/api/load' and name:
                    urllib.request.urlopen(urllib.request.Request(
                        'http://127.0.0.1:11434/api/generate',
                        data=json.dumps({"model": name, "prompt": "", "stream": False}).encode('utf-8'),
                        headers={'Content-Type': 'application/json'}
                    ), timeout=5)
                elif self.path == '/api/delete' and name:
                    subprocess.run(['ollama', 'rm', name], capture_output=True, timeout=10)
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}')
            except:
                self.send_response(400); self.end_headers()

        def do_GET(self):
            if self.path == '/api/stats':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                try:
                    res = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu,memory.used,power.draw,power.limit', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3)
                    p = res.stdout.strip().split(',')
                    gpu = {
                        'temperature': int(float(p[0])), 
                        'utilization': int(float(p[1])), 
                        'vram_used_mb': int(float(p[2])),
                        'power': float(p[3]),
                        'power_limit': float(p[4])
                    }
                except:
                    gpu = {'temperature': 0, 'utilization': 0, 'vram_used_mb': 0, 'power': 0.0, 'power_limit': 215.0}
                
                try:
                    total, used, free = shutil.disk_usage("/")
                    disk = {
                        'total_gb': round(total / (2**30), 1),
                        'used_gb': round(used / (2**30), 1),
                        'free_gb': round(free / (2**30), 1),
                        'percent': round((used / total) * 100, 1)
                    }
                except:
                    disk = {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}

                sys_dynamic = get_dynamic_system_stats()

                active = []
                try:
                    with urllib.request.urlopen(OLLAMA_PS_URL, timeout=2) as resp:
                        for m in json.loads(resp.read()).get('models', []):
                            active.append({'name': m.get('name'), 'size_vram_mb': round(m.get('size_vram', 0)/(1024*1024), 1)})
                except: pass

                available = []
                try:
                    with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=2) as resp:
                        for m in json.loads(resp.read()).get('models', []):
                            if m.get('name'): available.append(m.get('name'))
                    available = list(set(available))
                except: pass

                payload = {
                    **gpu, 
                    'disk': disk, 
                    'sys_dynamic': sys_dynamic,
                    'specs': CACHED_SPECS,
                    'ollama_models': active, 
                    'available_models': available
                }
                self.wfile.write(json.dumps(payload).encode())
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(HTML_CONTENT.encode('utf-8'))

    class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True

    with ThreadingTCPServer((HOST, PORT), Handler) as httpd:
        print(f"RTX Dashboard - Ollama srv - http://{HOST}:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
