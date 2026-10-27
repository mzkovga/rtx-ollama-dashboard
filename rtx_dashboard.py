#!/usr/bin/env python3
"""RTX & Ollama Dashboard. Uso: python3 rtx_dashboard.py  ->  http://127.0.0.1:8090
Variables: RTX_HOST (def. 127.0.0.1), RTX_PORT (8090), OLLAMA_URL, OLLAMA_MODELS (ruta para medir disco)."""
import glob, http.server, json, os, re, shutil, subprocess, threading, time, urllib.request

HOST = os.environ.get('RTX_HOST', '127.0.0.1')
PORT = int(os.environ.get('RTX_PORT', '8090'))
OLLAMA = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
DISK_PATH = os.environ.get('OLLAMA_MODELS') if os.path.isdir(os.environ.get('OLLAMA_MODELS', '')) else '/'


def rd(p):
    try:
        with open(p) as f:
            return f.read()
    except Exception:
        return ''


def sh(cmd, t=3):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        return r.stdout if r.returncode == 0 else ''
    except Exception:
        return ''


def api(path, data=None, method=None, timeout=5):
    req = urllib.request.Request(OLLAMA + path, method=method, headers={'Content-Type': 'application/json'},
                                 data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return json.loads(b) if b else {}


def get_specs():
    m = re.search(r'model name\s*:\s*(.+)', rd('/proc/cpuinfo'))
    o = re.search(r'PRETTY_NAME="?([^"\n]+)', rd('/etc/os-release'))
    mem = re.search(r'MemTotal:\s+(\d+)', rd('/proc/meminfo'))
    return {
        'os': o.group(1) if o else 'Linux',
        'kernel': sh(['uname', '-r']).strip() or '?',
        'cpu': m.group(1) if m else '?',
        'ram': f"{int(mem.group(1)) / 1048576:.1f} GB" if mem else '?',
        'gpu': (sh(['nvidia-smi', '-i', '0', '--query-gpu=name', '--format=csv,noheader']).strip() or '?'),
    }


SPECS = get_specs()


def cpu_temp():
    lines = sh(['sensors'], 2).split('\n')
    for k in ('Package id 0', 'Tctl', 'Tdie', 'Core 0', 'CPU Temperature', 'temp1'):
        for l in lines:
            if k in l:
                m = re.search(r'\+?(\d+(?:\.\d+)?)\s*°C', l)
                if m:
                    return float(m.group(1))
    for d in glob.glob('/sys/class/thermal/thermal_zone*'):
        if rd(d + '/type').strip() in ('x86_pkg_temp', 'k10temp', 'coretemp'):
            try:
                return int(rd(d + '/temp')) / 1000
            except ValueError:
                pass
    return None


def gpu():
    keys = ['temp', 'util', 'vram', 'vram_total', 'power', 'power_limit']
    q = 'temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit'
    p = sh(['nvidia-smi', '-i', '0', '--query-gpu=' + q, '--format=csv,noheader,nounits']).strip().split(',')
    g = {}
    for k, v in zip(keys, p + [''] * 6):
        try:
            g[k] = float(v)
        except ValueError:
            g[k] = None
    return g


def ram():
    mi = {k: int(v) for k, v in re.findall(r'(\w+):\s+(\d+)', rd('/proc/meminfo'))}
    tot = mi.get('MemTotal', 0)
    used = tot - mi.get('MemAvailable', mi.get('MemFree', 0))
    return {'used_gb': round(used / 1048576, 1), 'total_gb': round(tot / 1048576, 1),
            'pct': round(used / tot * 100, 1) if tot else 0}


def disk():
    try:
        total, used, free = shutil.disk_usage(DISK_PATH)
        return {'free_gb': round(free / 2**30, 1), 'total_gb': round(total / 2**30, 1),
                'pct': round(used / total * 100, 1), 'path': DISK_PATH}
    except Exception:
        return {'free_gb': 0, 'total_gb': 0, 'pct': 0, 'path': DISK_PATH}


def ollama():
    o = {'up': False, 'version': '', 'loaded': [], 'installed': []}
    try:
        o['version'] = api('/api/version', timeout=2).get('version', '')
        o['up'] = True
        for m in api('/api/ps', timeout=2).get('models', []):
            o['loaded'].append({k: m.get(k) for k in ('name', 'size', 'size_vram', 'expires_at', 'context_length')})
        o['installed'] = sorted(({'name': m['name'], 'size': m.get('size', 0)}
                                 for m in api('/api/tags', timeout=2).get('models', [])), key=lambda m: m['name'])
    except Exception:
        pass
    return o


_cache = {'t': 0, 'd': None}
_lock = threading.Lock()


def stats():
    with _lock:
        if _cache['d'] and time.time() - _cache['t'] < 1.2:
            return _cache['d']
        _cache['d'] = {'gpu': gpu(), 'cpu_temp': cpu_temp(), 'ram': ram(), 'disk': disk(),
                       'ollama': ollama(), 'specs': SPECS}
        _cache['t'] = time.time()
        return _cache['d']


PAGE = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RTX Dashboard</title>
<style>
:root{--bg:#0e1322;--s1:#161d33;--s2:#1f2845;--line:#2b3556;--tx:#e8ecf8;--mut:#8b96b8;--vram:#5ac8fa;--ok:#5eead4;--heat:#ffb454;--hot:#ff6b6b;
--m0:#5ac8fa;--m1:#b69cff;--m2:#ff9ec4;--m3:#ffd166}
[data-theme=light]{--bg:#edf0f7;--s1:#fff;--s2:#f1f4fb;--line:#d5dbea;--tx:#151b30;--mut:#5d6788;--vram:#0a84c6;--ok:#0f9d74;--heat:#c97a06;--hot:#d63b3b;
--m0:#0a84c6;--m1:#6b4fd8;--m2:#d6336c;--m3:#c98a00}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;height:100dvh;padding:14px;background:var(--bg);color:var(--tx);font-family:"Avenir Next","Segoe UI",Inter,system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;height:100%;display:flex;flex-direction:column;gap:10px}
main>*{flex:none}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
h1{margin:0;font-size:1.1rem;font-weight:600}
.row{display:flex;gap:8px;align-items:center}
button{font:inherit;cursor:pointer;color:var(--tx);background:var(--s1);border:1px solid var(--line);border-radius:9px;padding:5px 11px;font-weight:600;font-size:.82rem}
button:hover{background:var(--s2)}button:disabled{opacity:.5;cursor:wait}
button:focus-visible{outline:2px solid var(--vram);outline-offset:2px}
.pill{display:inline-flex;gap:8px;align-items:center;font-size:.8rem;padding:5px 12px;border-radius:99px;background:var(--s1);border:1px solid var(--line)}
.pill:before{content:"";width:8px;height:8px;border-radius:50%;background:var(--mut)}
.pill.up:before{background:var(--ok);box-shadow:0 0 8px var(--ok)}.pill.down:before{background:var(--hot)}
#err{background:var(--hot);color:#fff;border-radius:10px;padding:8px 14px;font-size:.88rem}
.hero{display:grid;grid-template-columns:1.4fr 1fr;gap:10px}
.card{background:var(--s1);border:1px solid var(--line);border-radius:14px;padding:12px 16px}
.big{border-radius:20px;padding:14px 20px}
.lab{font-size:.8rem;color:var(--mut)}
.num{font-size:1.35rem;font-weight:600;font-variant-numeric:tabular-nums}
.vnum{font-size:2.8rem;font-weight:650;line-height:1.05;font-variant-numeric:tabular-nums;color:var(--vram)}
.vof{font-size:1rem;color:var(--mut);margin-left:8px}
.vbar{display:flex;height:16px;margin:10px 0 8px;background:var(--s2);border-radius:99px;overflow:hidden;gap:2px}
.vbar i{display:block;height:100%;transition:width .4s}
.vbar .other{background:repeating-linear-gradient(45deg,var(--mut) 0 4px,transparent 4px 8px);opacity:.55}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.78rem;color:var(--mut);min-height:16px}
.legend b{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px}
.sparks{display:grid;gap:4px;align-content:center}
.spark{display:grid;grid-template-columns:1fr 96px;align-items:center;gap:12px}
.spark>div:first-child{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.spark .num{font-size:1.2rem}
svg{width:100%;height:30px;overflow:visible}
polyline{fill:none;stroke:currentColor;stroke-width:2;vector-effect:non-scaling-stroke;stroke-linejoin:round}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.bar{height:6px;background:var(--s2);border-radius:99px;margin:7px 0 4px;overflow:hidden}
.bar i{display:block;height:100%;width:0;transition:width .4s,background .4s;border-radius:99px}
.sub{font-size:.76rem;color:var(--mut)}
h2{font-size:.95rem;margin:0 0 8px;font-weight:600}
.models-card{flex:0 1 auto;min-height:0;overflow:auto;scrollbar-width:thin}
.loaded{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px;margin-bottom:8px}
.m{display:flex;justify-content:space-between;align-items:center;gap:10px;background:var(--s2);border-radius:10px;border-left:4px solid var(--vram);padding:8px 12px}
.m .top{display:flex;gap:8px;align-items:center;font-weight:600;font-size:.9rem;word-break:break-all}
.badge{font-size:.72rem;padding:2px 8px;border-radius:99px;font-weight:600;background:var(--ok);color:#06231f;white-space:nowrap}
.badge.warn{background:var(--heat);color:#2b1700}
.empty{color:var(--mut);font-size:.85rem;margin:0 0 2px;grid-column:1/-1}
.inst{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:6px}
.irow{display:grid;grid-template-columns:10px 1fr auto auto auto;gap:10px;align-items:center;padding:6px 10px;border-radius:10px;background:var(--s2);font-size:.86rem}
.irow button,.m button{padding:3px 10px;font-size:.78rem}
.dot{width:8px;height:8px;border-radius:50%;background:var(--line)}.dot.on{background:var(--ok)}
.irow .nm{word-break:break-all}
.danger{color:var(--hot)}
.slim{padding:8px 16px}
details summary{cursor:pointer;font-weight:600;font-size:.88rem}
#specs{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));column-gap:28px;margin-top:6px}
.spec{display:flex;justify-content:space-between;gap:16px;padding:5px 0;border-bottom:1px solid var(--line);font-size:.82rem}
.spec span:first-child{color:var(--mut)}.spec span:last-child{text-align:right;word-break:break-word}
#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--tx);color:var(--bg);padding:10px 18px;border-radius:10px;font-size:.9rem;font-weight:600;opacity:0;pointer-events:none;transition:opacity .25s}
#toast.show{opacity:1}#toast.bad{background:var(--hot);color:#fff}
@media(max-width:760px){html,body{height:auto}body{padding:12px}main{height:auto}.hero,.tiles{grid-template-columns:1fr}.models-card{overflow:visible}
.inst{grid-template-columns:1fr}.irow{grid-template-columns:10px 1fr auto auto}.irow .sz{display:none}.vnum{font-size:2.4rem}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><main>
<header><h1>RTX · Ollama</h1><div class="row">
<span class="pill" id="pill"><span id="pilltx">…</span></span>
<button id="bl" onclick="toggleLang()"></button>
<button onclick="toggleTheme()" aria-label="theme">◐</button></div></header>
<div id="err" hidden></div>

<section class="hero">
 <div class="card big">
  <div class="lab" data-i="vram"></div>
  <div><span class="vnum" id="vnum">--</span><span class="vof" id="vof"></span></div>
  <div class="vbar" id="vbar"></div><div class="legend" id="legend"></div>
 </div>
 <div class="card sparks">
  <div class="spark"><div><div class="lab" data-i="gpu_temp"></div><div class="num" id="v-temp">--</div></div><svg id="sp-temp" viewBox="0 0 100 34" preserveAspectRatio="none"><polyline/></svg></div>
  <div class="spark"><div><div class="lab" data-i="gpu_util"></div><div class="num" id="v-util">--</div></div><svg id="sp-util" viewBox="0 0 100 34" preserveAspectRatio="none"><polyline/></svg></div>
  <div class="spark"><div><div class="lab" data-i="gpu_power"></div><div class="num" id="v-power">--</div></div><svg id="sp-power" viewBox="0 0 100 34" preserveAspectRatio="none"><polyline/></svg></div>
 </div>
</section>

<section class="tiles">
 <div class="card"><div class="lab" data-i="cpu_temp"></div><div class="num" id="v-cpu">--</div><div class="bar"><i id="b-cpu"></i></div></div>
 <div class="card"><div class="lab" data-i="ram"></div><div class="num" id="v-ram">--</div><div class="bar"><i id="b-ram"></i></div><div class="sub" id="s-ram"></div></div>
 <div class="card"><div class="lab" data-i="disk"></div><div class="num" id="v-disk">--</div><div class="bar"><i id="b-disk"></i></div><div class="sub" id="s-disk"></div></div>
</section>

<section class="card models-card"><h2 data-i="models"></h2><div class="loaded" id="loaded"></div><div class="inst" id="inst"></div></section>
<section class="card slim"><details><summary data-i="specs"></summary><div id="specs"></div></details></section>
</main><div id="toast"></div>
<script>
const L={es:{vram:"VRAM en uso",gpu_temp:"Temperatura GPU",gpu_util:"Uso de GPU",gpu_power:"Consumo",cpu_temp:"Temperatura CPU",ram:"Memoria RAM",disk:"Espacio libre en disco",
models:"Modelos",specs:"Especificaciones del sistema",online:"Ollama activo",offline:"Ollama no responde",
load:"Cargar",eject:"Expulsar",del:"Borrar",in_mem:"En memoria",other:"Otros procesos",empty:"No hay modelos cargados. Elige uno de la lista para cargarlo.",
off:"No se pudo conectar con Ollama. Inícialo con: systemctl start ollama",no_inst:"No hay modelos instalados. Descarga uno con: ollama pull <modelo>",err:"No se pudo conectar con el dashboard.",
conf_del:"¿Borrar del disco",conf_eject:"¿Expulsar",done:"Listo",used:"usada",free:"libre",never:"sin límite",min:"min",spill:"parte en CPU/RAM: más lento",
os:"Sistema",kernel:"Kernel",cpu:"Procesador",ramt:"RAM total",gpu:"GPU",ctx:"contexto",exp:"expira en"},
en:{vram:"VRAM in use",gpu_temp:"GPU temperature",gpu_util:"GPU load",gpu_power:"Power draw",cpu_temp:"CPU temperature",ram:"RAM",disk:"Free disk space",
models:"Models",specs:"System specs",online:"Ollama running",offline:"Ollama not responding",
load:"Load",eject:"Eject",del:"Delete",in_mem:"In memory",other:"Other processes",empty:"No models loaded. Pick one from the list below to load it.",
off:"Can't reach Ollama. Start it with: systemctl start ollama",no_inst:"No models installed. Pull one with: ollama pull <model>",err:"Can't reach the dashboard server.",
conf_del:"Delete from disk",conf_eject:"Eject",done:"Done",used:"used",free:"free",never:"no limit",min:"min",spill:"partly on CPU/RAM: slower",
os:"System",kernel:"Kernel",cpu:"Processor",ramt:"Total RAM",gpu:"GPU",ctx:"context",exp:"expires in"}};
const $=i=>document.getElementById(i), gb=mb=>(mb/1024).toFixed(1), G=b=>(b/2**30).toFixed(1);
let lang=localStorage.rtx_lang||'es', last=null, sig='', tm, H={temp:[],util:[],power:[]};
const T=()=>L[lang];
function h(tag,p={},...k){const e=document.createElement(tag);for(const[a,v]of Object.entries(p)){if(a==='class')e.className=v;else if(a.startsWith('on'))e[a]=v;else e.setAttribute(a,v)}e.append(...k);return e}
function setLang(l){lang=l;localStorage.rtx_lang=l;document.documentElement.lang=l;$('bl').textContent=l==='es'?'EN':'ES';
 document.querySelectorAll('[data-i]').forEach(e=>e.textContent=T()[e.dataset.i]);sig='';if(last)render(last)}
function toggleLang(){setLang(lang==='es'?'en':'es')}
function toggleTheme(){const d=document.documentElement,n=d.dataset.theme==='light'?'dark':'light';d.dataset.theme=n;localStorage.rtx_theme=n}
document.documentElement.dataset.theme=localStorage.rtx_theme||'dark';
function lvl(v,w,hh){return v>=hh?'var(--hot)':v>=w?'var(--heat)':'var(--ok)'}
function toast(m,bad){const t=$('toast');t.textContent=m;t.className='show'+(bad?' bad':'');setTimeout(()=>t.className='',2600)}
function spark(id,arr,lo,hi,col){const e=$('sp-'+id);e.style.color=col;
 e.firstChild.setAttribute('points',arr.map((v,i)=>`${((i+60-arr.length)/59*100).toFixed(1)},${(32-Math.min(1,Math.max(0,(v-lo)/(hi-lo)))*30).toFixed(1)}`).join(' '))}
function push(k,v){if(v==null)return;H[k].push(v);if(H[k].length>60)H[k].shift()}
function setBar(id,pct,col){const b=$(id);b.style.width=Math.min(100,pct||0)+'%';b.style.background=col}

function render(d){
 last=d;const t=T(),g=d.gpu,o=d.ollama;
 $('pill').className='pill '+(o.up?'up':'down');$('pilltx').textContent=o.up?`${t.online} ${o.version}`:t.offline;
 const tot=g.vram_total||8192;
 $('vnum').textContent=g.vram==null?'N/A':gb(g.vram);$('vof').textContent='/ '+gb(tot)+' GB';
 const bar=$('vbar'),lg=$('legend');bar.replaceChildren();lg.replaceChildren();let sum=0;
 o.loaded.forEach((m,i)=>{const mb=m.size_vram/1048576;sum+=mb;
  bar.append(h('i',{style:`width:${mb/tot*100}%;background:var(--m${i%4})`,title:m.name}));
  lg.append(h('span',{},h('b',{style:`background:var(--m${i%4})`}),`${m.name} ${gb(mb)} GB`))});
 if(g.vram!=null&&g.vram-sum>64){bar.append(h('i',{class:'other',style:`width:${(g.vram-sum)/tot*100}%`}));
  lg.append(h('span',{},h('b',{style:'background:var(--mut)'}),`${t.other} ${gb(g.vram-sum)} GB`))}
 push('temp',g.temp);push('util',g.util);push('power',g.power);
 const f=(v,u)=>v==null?'N/A':Math.round(v)+u;
 $('v-temp').textContent=f(g.temp,' °C');$('v-util').textContent=f(g.util,' %');$('v-power').textContent=g.power==null?'N/A':`${g.power.toFixed(0)} W`;
 spark('temp',H.temp,30,95,lvl(g.temp||0,70,82));spark('util',H.util,0,100,'var(--vram)');spark('power',H.power,0,g.power_limit||215,'var(--m1)');
 $('v-cpu').textContent=d.cpu_temp==null?'N/A':Math.round(d.cpu_temp)+' °C';setBar('b-cpu',d.cpu_temp,lvl(d.cpu_temp||0,75,88));
 $('v-ram').textContent=`${d.ram.used_gb} GB`;$('s-ram').textContent=`${d.ram.pct}% ${t.used} · ${d.ram.total_gb} GB`;setBar('b-ram',d.ram.pct,lvl(d.ram.pct,80,92));
 $('v-disk').textContent=`${d.disk.free_gb} GB`;$('s-disk').textContent=`${d.disk.pct}% ${t.used} · ${d.disk.total_gb} GB · ${d.disk.path}`;setBar('b-disk',d.disk.pct,lvl(d.disk.pct,80,92));

 const ld=$('loaded');ld.replaceChildren();
 if(!o.up)ld.append(h('p',{class:'empty'},t.off));else if(!o.loaded.length)ld.append(h('p',{class:'empty'},t.empty));
 o.loaded.forEach((m,i)=>{
  const pct=m.size?Math.round(m.size_vram/m.size*100):0,full=pct>=99;
  let ex=t.never;if(m.expires_at){const mins=Math.round((new Date(m.expires_at)-Date.now())/60000);if(mins<60*24*30)ex=`${t.exp} ${Math.max(0,mins)} ${t.min}`}
  const eb=h('button',{},t.eject);eb.onclick=()=>{if(confirm(`${t.conf_eject} ${m.name}?`))act('/api/stop',m.name,eb)};
  ld.append(h('div',{class:'m',style:`border-color:var(--m${i%4})`},
   h('div',{},h('div',{class:'top'},m.name,h('span',{class:'badge'+(full?'':' warn'),title:full?'':t.spill},`${pct}% GPU`)),
   h('div',{class:'sub'},`${G(m.size)} GB · ${m.context_length?t.ctx+' '+m.context_length+' · ':''}${ex}`)),eb))});

 const s=JSON.stringify([o.installed,o.loaded.map(m=>m.name),lang]);
 if(s!==sig){sig=s;const ib=$('inst');ib.replaceChildren();
  if(o.up&&!o.installed.length)ib.append(h('p',{class:'empty'},t.no_inst));
  const on=new Set(o.loaded.map(m=>m.name));
  o.installed.forEach(m=>{
   const lb=h('button',{},on.has(m.name)?t.in_mem:t.load);lb.disabled=on.has(m.name);lb.onclick=()=>act('/api/load',m.name,lb);
   const db=h('button',{class:'danger',title:t.del,'aria-label':t.del},'✕');db.onclick=()=>{if(confirm(`${t.conf_del} "${m.name}"?`))act('/api/delete',m.name,db)};
   ib.append(h('div',{class:'irow'},h('span',{class:'dot'+(on.has(m.name)?' on':'')}),h('span',{class:'nm'},m.name),h('span',{class:'sub sz'},G(m.size)+' GB'),lb,db))})}

 const sp=$('specs');sp.replaceChildren();
 [['os',d.specs.os],['kernel',d.specs.kernel],['cpu',d.specs.cpu],['ramt',d.specs.ram],['gpu',d.specs.gpu]].forEach(([k,v])=>sp.append(h('div',{class:'spec'},h('span',{},t[k]),h('span',{},v))))}

async function act(path,name,btn){
 const old=btn.textContent;btn.disabled=true;btn.textContent='…';
 try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
  const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);toast(T().done)}
 catch(e){toast(e.message,1)}
 btn.disabled=false;btn.textContent=old;sig='';poll(true)}

async function poll(now){
 clearTimeout(tm);
 if(!document.hidden||now){
  let d=null;
  try{const r=await fetch('/api/stats');if(!r.ok)throw 0;d=await r.json();$('err').hidden=true}
  catch{$('err').textContent=T().err;$('err').hidden=false}
  if(d){try{render(d)}catch(e){console.error(e)}}}
 tm=setTimeout(poll,2000)}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll(true)});
setLang(lang);poll(true);
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body, ct='application/json'):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == '/api/stats':
            self.reply(200, stats())
        elif self.path in ('/', '/index.html'):
            self.reply(200, PAGE.encode(), 'text/html; charset=utf-8')
        else:
            self.reply(404, {'error': 'not found'})

    def do_POST(self):
        # Exigir JSON fuerza un preflight CORS en navegadores: bloquea POSTs desde otras webs.
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self.reply(415, {'error': 'content-type must be application/json'})
        try:
            n = min(int(self.headers.get('Content-Length', 0)), 4096)
            name = str(json.loads(self.rfile.read(n)).get('name', ''))
            known = {m['name'] for m in api('/api/tags', timeout=3).get('models', [])}
            if name not in known:
                return self.reply(404, {'error': 'modelo desconocido'})
            if self.path == '/api/load':
                api('/api/generate', {'model': name, 'prompt': '', 'stream': False}, timeout=180)
            elif self.path == '/api/stop':
                api('/api/generate', {'model': name, 'prompt': '', 'stream': False, 'keep_alive': 0})
            elif self.path == '/api/delete':
                api('/api/delete', {'model': name}, 'DELETE', 30)
            else:
                return self.reply(404, {'error': 'not found'})
            _cache['t'] = 0
            self.reply(200, {'ok': True})
        except Exception as e:
            self.reply(502, {'error': str(e)})


if __name__ == '__main__':
    srv = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    print(f'RTX Dashboard -> http://{HOST}:{PORT}')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
