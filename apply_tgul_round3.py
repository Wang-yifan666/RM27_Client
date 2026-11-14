#!/usr/bin/env python3
'''One-time, checked TGUL map adapter installation (after round 2).'''
from pathlib import Path

BASE = Path(__file__).resolve().parent
SERVER = BASE / "sim/server"
STATIC = SERVER / "static"
changes = {}


def replace_exact(source: str, old: str, new: str, file: str) -> str:
    n = source.count(old)
    if n != 1:
        raise RuntimeError(
            f"{file}: expected 1 anchor, found {n}: {old[:90]!r}. "
            "Do not apply an incompatible patch automatically."
        )
    return source.replace(old, new, 1)


tgul_file = SERVER / "tgul2027_simulation.py"
main_file = SERVER / "main.py"
app_file = STATIC / "app.js"
index_file = STATIC / "index.html"
for path in (tgul_file, main_file, app_file, index_file):
    if not path.is_file():
        raise FileNotFoundError(path)

if "TGUL_MAP_ROUND3" in tgul_file.read_text(encoding="utf-8"):
    print("TGUL map adapter already installed; nothing to change.")
    raise SystemExit(0)

sim = tgul_file.read_text(encoding="utf-8")
sim = replace_exact(
    sim,
    "from server.tgul2027_rules import (",
    "from server.tgul2027_map import get_tgul_map, initial_demo_positions\n"
    "from server.tgul2027_rules import (",
    tgul_file.name,
)
sim = replace_exact(
    sim,
    "        self.robot_ids = ids\n",
    "        self.robot_ids = ids\n"
    "        demo_positions = initial_demo_positions(self.tgul_mode, ids)\n"
    "        if demo_positions:\n"
    "            self.positions = demo_positions\n",
    tgul_file.name,
)
sim = replace_exact(
    sim,
    "    def get_state(self):\n"
    "        snapshot = super().get_state()\n",
    '''    # TGUL_MAP_ROUND3: reject invalid coordinates and inactive robots.
    def set_robot_position(self, robot_index, x, y, angle=None):
        import math
        try:
            idx, px, py = int(robot_index), float(x), float(y)
            angle_num = None if angle is None else float(angle)
        except (ValueError, TypeError, OverflowError):
            return False
        cfg = get_tgul_map(self.tgul_mode)
        if not cfg["configured"] or not (0 <= idx < len(self.robot_ids)):
            return False
        if self.robot_ids[idx] not in self.active_robot_ids:
            return False
        if not math.isfinite(px) or not math.isfinite(py):
            return False
        if angle_num is not None and not math.isfinite(angle_num):
            return False
        if not (0 <= px <= cfg["width_m"] and 0 <= py <= cfg["height_m"]):
            return False
        super().set_robot_position(idx, px, py, angle_num)
        return True

    def get_state(self):
        snapshot = super().get_state()
''',
    tgul_file.name,
)
sim = replace_exact(
    sim,
    '        snapshot["tgulActiveRobotIds"] = list(self.active_robot_ids)\n',
    '        snapshot["tgulActiveRobotIds"] = list(self.active_robot_ids)\n'
    '        snapshot["tgulMap"] = get_tgul_map(self.tgul_mode)\n',
    tgul_file.name,
)
changes[tgul_file] = sim

main = main_file.read_text(encoding="utf-8")
main = replace_exact(
    main,
    '        if mqtt_publisher:\n            angle = 0.0\n',
    '        if mqtt_publisher and not args.tgul_mode:\n            angle = 0.0\n',
    main_file.name,
)
changes[main_file] = main

index = index_file.read_text(encoding="utf-8")
index = replace_exact(
    index,
    '    <script src="/app.js?v=20260809_01" defer></script>',
    '    <script src="/tgul_map_geometry.js?v=20261103_01" defer></script>\n'
    '    <script src="/app.js?v=20260809_01" defer></script>',
    index_file.name,
)
index = replace_exact(
    index,
    '                            <span class="minimap-hint">左下角为场地坐标原点</span>',
    '                            <span class="minimap-hint">左下角为场地坐标原点</span>\n'
    '                            <span v-if="tgulMode" class="minimap-hint">'
    'TGUL {{ tgulMode }} · {{ tgulMap && tgulMap.calibrated ? "场地已标定" : "场地未标定，仅供演示" }}'
    '</span>',
    index_file.name,
)
changes[index_file] = index

app = app_file.read_text(encoding="utf-8")
app = replace_exact(
    app,
    '        mapWidth: 28.0,\n        mapHeight: 15.0,',
    '        mapWidth: 28.0,\n        mapHeight: 15.0,\n'
    '        tgulMode: null,\n        tgulMap: null,\n        tgulActiveRobotIds: [],',
    app_file.name,
)
app = replace_exact(
    app,
    '            this.robotIds = data.robotIds || this.robotIds;',
    '            this.robotIds = data.robotIds || this.robotIds;\n'
    '            this.applyTGULMapData(data.tgulMode, data.tgulMap, data.tgulActiveRobotIds);',
    app_file.name,
)
app = replace_exact(
    app,
    '    methods: {\n        // 当前机器人改变时触发',
    '''    methods: {
        // TGUL_MAP_ROUND3
        applyTGULMapData(mode, config, activeIds) {
            if (!mode) return;  // Legacy mode is left unchanged.
            this.tgulMode = mode;
            this.tgulMap = config || null;
            this.tgulActiveRobotIds = Array.isArray(activeIds) ? activeIds.map(Number) : [];
            if (config && config.configured) {
                this.mapWidth = Number(config.width_m);
                this.mapHeight = Number(config.height_m);
            }
            if (this.canvas) this.canvas.style.backgroundImage = 'none';
            if (this.pathPlanCanvas) this.pathPlanCanvas.style.backgroundImage = 'none';
            const url = config && config.image_url ? config.image_url : '';
            if (this._tgulMapUrl === url) return;
            this._tgulMapUrl = url;
            this._tgulImage = null;
            if (!url) return;
            const img = new Image();
            img.onload = () => {
                if (this._tgulMapUrl !== url) return;
                this._tgulImage = img;
                this.drawMinimap();
                this.drawRobotPathPlanCanvas();
            };
            img.onerror = () => {
                if (this._tgulMapUrl !== url) return;
                this._tgulImage = null;
                this.drawMinimap();
            };
            img.src = url;
        },
        drawTGULField(ctx, w, h, padding = 0) {
            ctx.fillStyle = '#0a1725';
            ctx.fillRect(0, 0, w, h);
            const config = this.tgulMap;
            if (!config || !config.configured) {
                ctx.fillStyle = '#f0c87e';
                ctx.font = '14px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('TGUL map not calibrated: set field dimensions', w / 2, h / 2);
                return false;
            }
            const g = window.TGULMapGeometry;
            const frame = g.view(this.mapWidth, this.mapHeight, w, h, padding);
            ctx.fillStyle = '#21394c';
            ctx.fillRect(frame.left, frame.top, frame.width, frame.height);
            ctx.save();
            ctx.beginPath();
            ctx.rect(frame.left, frame.top, frame.width, frame.height);
            ctx.clip();
            let imageValid = false;
            if (this._tgulImage && this._tgulImage.naturalWidth > 0) {
                const crop = config.crop || [0, 0, 1, 1];
                const img = this._tgulImage;
                const sx = crop[0] * img.naturalWidth;
                const sy = crop[1] * img.naturalHeight;
                const sw = (crop[2] - crop[0]) * img.naturalWidth;
                const sh = (crop[3] - crop[1]) * img.naturalHeight;
                const ratio = (sw / sh) / (this.mapWidth / this.mapHeight);
                if (Math.abs(ratio - 1) <= 0.015) {
                    ctx.drawImage(img, sx, sy, sw, sh,
                        frame.left, frame.top, frame.width, frame.height);
                    imageValid = true;
                }
            }
            ctx.strokeStyle = 'rgba(240, 245, 255, 0.16)';
            ctx.lineWidth = 1;
            for (let i = 0; i <= Math.ceil(this.mapWidth); ++i) {
                const px = frame.left + i * frame.scale;
                ctx.beginPath();
                ctx.moveTo(px, frame.top);
                ctx.lineTo(px, frame.top + frame.height);
                ctx.stroke();
            }
            for (let i = 0; i <= Math.ceil(this.mapHeight); ++i) {
                const py = frame.top + i * frame.scale;
                ctx.beginPath();
                ctx.moveTo(frame.left, py);
                ctx.lineTo(frame.left + frame.width, py);
                ctx.stroke();
            }
            ctx.restore();
            ctx.strokeStyle = '#71a8c6';
            ctx.strokeRect(frame.left, frame.top, frame.width, frame.height);
            if (!imageValid) {
                ctx.fillStyle = '#f5cc84';
                ctx.font = '12px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Export a cropped top-view PNG with matching aspect ratio',
                    w / 2, h / 2);
            }
            return true;
        },
        // 当前机器人改变时触发''',
    app_file.name,
)
app = replace_exact(
    app,
    '''        getTeamRobotIds(team) {
            return team === 'blue'
                ? [101, 103, 106, 107]
                : [1, 3, 6, 7];
        },''',
    '''        getTeamRobotIds(team) {
            if (this.tgulMode) {
                return this.tgulActiveRobotIds.filter(
                    id => team === 'blue' ? id >= 100 : id < 100
                );
            }
            return team === 'blue'
                ? [101, 103, 106, 107]
                : [1, 3, 6, 7];
        },''',
    app_file.name,
)

# Robust method-level integration: retain upstream method bodies unchanged.
# This approach does NOT depend on comments or the layout of expressions
# inside drawMinimap / startDrag / onDrag / path planner.
import re
import textwrap


def wrap_js_method(source, name, original_name, wrapper):
    # In this Vue source methods are declared at eight spaces indentation.
    # Fail closed if a changed upstream code has zero or multiple definitions.
    regex = re.compile(
        rf"(?m)^(?P<indent>[ ]{{8}}){re.escape(name)}"
        r"\((?P<args>[^)]*)\)[ \t]*\{"
    )
    hits = list(regex.finditer(source))
    if len(hits) != 1:
        raise RuntimeError(
            f"app.js: expected one {name}() definition, found {len(hits)}. "
            "No source files have been modified."
        )
    found = hits[0]
    new_wrapper = textwrap.indent(textwrap.dedent(wrapper).strip() + "\n", " " * 8)
    # Rename only this method definition; nothing else in its original body.
    old_signature = source[found.start():found.end()]
    renamed = old_signature.replace(name + "(", original_name + "(", 1)
    return source[:found.start()] + new_wrapper + renamed + source[found.end():]


app = wrap_js_method(
    app, "drawMinimap", "drawLegacyMinimap",
    '''
drawMinimap() {
    if (!this.tgulMode) return this.drawLegacyMinimap();
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    if (!this.drawTGULField(ctx, w, h)) return;
    const geometry = window.TGULMapGeometry;
    if (!geometry || !this.tgulMap || !this.tgulMap.configured) return;
    (this.positions || []).forEach((pose, index) => {
        const robotId = Number(this.robotIds[index] ?? index + 1);
        if (!this.tgulActiveRobotIds.includes(robotId)) return;
        if (!Number.isFinite(Number(pose.x)) || !Number.isFinite(Number(pose.y))) return;
        if (pose.x < 0 || pose.x > this.mapWidth ||
            pose.y < 0 || pose.y > this.mapHeight) return;
        const pixel = geometry.worldToCanvas(
            pose.x, pose.y, this.mapWidth, this.mapHeight, w, h
        );
        const visual = this.getMinimapRobotVisual(index);
        this.drawMinimapRobot(
            pixel.x, pixel.y, Number(pose.angle || 0), visual, robotId
        );
    });
},
''',
)
app = wrap_js_method(
    app, "startDrag", "startLegacyDrag",
    '''
startDrag(evt) {
    if (!this.tgulMode) return this.startLegacyDrag(evt);
    this.draggingRobot = -1;
    if (!this.canvas || !this.tgulMap || !this.tgulMap.configured ||
        !window.TGULMapGeometry) return;
    const mouse = this.getMousePos(evt);
    const w = this.canvas.width, h = this.canvas.height;
    const scale = Math.max(0.75, Math.min(w / 800, h / 450));
    let nearest = 18 * scale;
    (this.positions || []).forEach((pose, index) => {
        const robotId = Number(this.robotIds[index] ?? index + 1);
        if (!this.tgulActiveRobotIds.includes(robotId)) return;
        const pixel = window.TGULMapGeometry.worldToCanvas(
            pose.x, pose.y, this.mapWidth, this.mapHeight, w, h
        );
        const distance = Math.hypot(mouse.x - pixel.x, mouse.y - pixel.y);
        if (distance < nearest) {
            nearest = distance;
            this.draggingRobot = index;
        }
    });
    if (this.draggingRobot !== -1 && this.simulationState === 'running')
        this.simulationManualOverride = true;
},
''',
)
app = wrap_js_method(
    app, "onDrag", "onLegacyDrag",
    '''
onDrag(evt) {
    if (!this.tgulMode) return this.onLegacyDrag(evt);
    if (this.draggingRobot < 0 || !this.canvas ||
        !this.tgulMap || !this.tgulMap.configured) return;
    const pixel = this.getMousePos(evt);
    const field = window.TGULMapGeometry.canvasToWorld(
        pixel.x, pixel.y, this.mapWidth, this.mapHeight,
        this.canvas.width, this.canvas.height
    );
    if (!field.inside) return;  // No dragging into aspect-ratio margins.
    const index = this.draggingRobot;
    if (!this.positions[index] ||
        !this.tgulActiveRobotIds.includes(Number(this.robotIds[index]))) return;
    this.positions[index].x = field.x;
    this.positions[index].y = field.y;
    this.drawMinimap();
    this.sendCommand('set_position', {
        robot_id: index, x: field.x, y: field.y,
        angle: Number(this.positions[index].angle || 0)
    });
},
''',
)
app = wrap_js_method(
    app, "pathPlanDmToCanvas", "legacyPathPlanDmToCanvas",
    '''
pathPlanDmToCanvas(dmX, dmY) {
    if (!this.tgulMode || !this.tgulMap || !this.tgulMap.configured)
        return this.legacyPathPlanDmToCanvas(dmX, dmY);
    return window.TGULMapGeometry.worldToCanvas(
        this.clampPathPlanDmX(dmX) / 10,
        this.clampPathPlanDmY(dmY) / 10,
        this.mapWidth, this.mapHeight,
        this.pathPlanWidth, this.pathPlanHeight, this.pathPlanPadding
    );
},
''',
)
app = wrap_js_method(
    app, "pathPlanCanvasToDm", "legacyPathPlanCanvasToDm",
    '''
pathPlanCanvasToDm(canvasX, canvasY) {
    if (!this.tgulMode || !this.tgulMap || !this.tgulMap.configured)
        return this.legacyPathPlanCanvasToDm(canvasX, canvasY);
    const point = window.TGULMapGeometry.canvasToWorld(
        canvasX, canvasY, this.mapWidth, this.mapHeight,
        this.pathPlanWidth, this.pathPlanHeight, this.pathPlanPadding
    );
    return {
        x: this.clampPathPlanDmX(Math.round(point.x * 10)),
        y: this.clampPathPlanDmY(Math.round(point.y * 10))
    };
},
''',
)
app = wrap_js_method(
    app, "drawRobotPathPlanCanvas", "drawLegacyRobotPathPlanCanvas",
    '''
drawRobotPathPlanCanvas() {
    if (!this.tgulMode) return this.drawLegacyRobotPathPlanCanvas();
    if (!this.pathPlanCtx || !this.pathPlanCanvas) return;
    const ctx = this.pathPlanCtx;
    const w = this.pathPlanCanvas.width, h = this.pathPlanCanvas.height;
    ctx.clearRect(0, 0, w, h);
    if (!this.drawTGULField(ctx, w, h, this.pathPlanPadding)) return;
    const points = Array.isArray(this.robotPathPlanPoints)
        ? this.robotPathPlanPoints : [];
    ctx.save();
    ctx.strokeStyle = '#68b4fc';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    points.forEach((point, i) => {
        if (i === 0) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
    });
    if (points.length) ctx.stroke();
    points.forEach((point, i) => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, i === 0 ? 7 : 6, 0, Math.PI * 2);
        ctx.fillStyle = i === 0 ? '#f1bc65' : '#5c9fc3';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#fcf9f0';
        ctx.stroke();
        ctx.fillStyle = '#fcf9f0';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(i === 0 ? 'START' : `P${i}`, point.x, point.y - 12);
    });
    ctx.restore();
},
''',
)
changes[app_file] = app


# Validate syntactic integrity before writing anything.
import ast
ast.parse(sim)
ast.parse(main)
for path, text in changes.items():
    path.write_text(text, encoding="utf-8")
print("TGUL round 3 map integration installed.")
