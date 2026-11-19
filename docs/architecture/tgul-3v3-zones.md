# TGUL 2027 3V3 赛场区域审计与最小实现计划

- 基线提交：`fa58d03`
- 本轮性质：只读审计。不修改 `MQTT`、Qt 客户端和比赛规则，不新增运行时行为
- 目标形态：2D 赛场态势模拟；不做 3D 机器人仿真；不开发 1V1；保留 `tgul` 命名

## 1. 现状检查

### 1.1 `sim/server/static/tgul_maps/tgul_3v3.json`

已有字段：`width_m`/`height_m`、`calibrated`、`crop`、`image_styles`、`source*`、`orientation`、`geometry`、`notes`。

审计结论：

- 场地框（`width_m`/`height_m`）与图片样式表分离得清楚，`image_styles` 带 `available` 语义，切换风格不影响坐标。
- `geometry` 块记录的是**单一标量或一维尺寸**：`highland_mm: [2000, 4060, 200]`、`central_control_zone_mm: [3000, 3000, 10]`、`tunnel_clearance_mm`。这些是**包围盒尺寸**，不是可做点包含判定的轮廓，原因见第 5 节。
- 缺少区域/障碍的**位置与形状**：目前无法回答“某个坐标是否在障碍物里”。

### 1.2 `sim/server/tgul2027_map.py`

- `get_tgul_map()` 负责读 JSON、校验尺寸与 `crop`、解析 `image_styles`，返回给 Web 的展示元数据。职责单一，无需改动。
- `initial_demo_positions()` 的文档字符串已明确写明：

  > `Sample positions inside a CONFIGURED field, not official robot spawn points.`

  即演示出生点从设计上就不是官方出生点。第 2 节给出数值证据。
- 未配置（`width_m`/`height_m` 为 `null`）时返回 `[]`，调用方回退旧坐标——1V1 走这条路径，本轮不改。

### 1.3 `sim/server/tgul2027_simulation.py`

- `TGULStateManager.active_robot_ids` 为 3v3 返回 `(1, 3, 7, 101, 103, 107)`，`4`/`104` 是登记在册的替补，八个显示槽位保留但零值占位。
- `set_robot_position()` 只用矩形场地边界做校验（`0 ≤ x ≤ width_m`、`0 ≤ y ≤ height_m`），**没有障碍物概念**。
- `TGULMatchSimulationEngine._build_positions()` 让上台机器人在出生点附近巡逻，幅度按到边界余量的一半收紧；替补原地不动。位置推进按真实秒（`PATROL_CYCLE_SEC = 25`），不受 `battle_progress` 门控。
- 结论：区域数据接入点是 `set_robot_position()` 与 `_build_positions()` 两处；两者都不需要改动比赛规则模块。

### 1.4 地图几何测试现状

| 文件 | 用例数 | 覆盖 |
| --- | --- | --- |
| `sim/tests/test_tgul_map_geometry.js` | 5 | `view()` 比例/letterbox、`worldToCanvas`↔`canvasToWorld` 往返、边界外 `inside=false`、非法尺寸抛错 |
| `sim/tests/test_map_geometry.js` | 3 | 旧版地图几何 |
| `sim/tests/test_tgul2027_map.py` | 5 | 尺寸与 `initial_demo_positions`、样式表、缺图回退、1v1 未配置 |
| `sim/tests/test_tgul2027_map_integration.py` | 3 | 状态快照字段、重置后位置、演示帧钳制 |
| `sim/tests/test_tgul2027_integration.py` | 8 | 初始化、阶段边界、暂停/恢复/重置、位置推进、开局即动、贴边停滞 |

覆盖缺口（本轮不补，列入第 6 节）：

- 没有 `point_in_polygon`，也没有任何区域/障碍概念；
- 没有区域进入/离开事件；
- 没有“位置是否可行（考虑障碍）”的判定。

## 2. 阵营位置核对：官方测量 vs 演示出生点

### 2.1 官方测量记录（STEP 面颜色聚类，`markers3d.txt`）

| 阵营 | x 范围 | y 范围 | 尺寸 | AABB 中心 |
| --- | --- | --- | --- | --- |
| 红方 | 0.92 – 1.56 m | 6.65 – 7.33 m | 0.64 × 0.68 m | (1.24, 6.99) |
| 蓝方 | 10.44 – 11.08 m | 0.67 – 1.35 m | 0.64 × 0.68 m | (10.76, 1.01) |

`z = 0.002 m`，即贴地标识。红方在西北、蓝方在东南，与底图一致。

### 2.2 演示出生点（`initial_demo_positions`，3v3 分支）

| 机器人 | 演示坐标 | 到本方基地标识中心 | 是否落在标识内 |
| --- | --- | --- | --- |
| 1 | (1.92, 1.92) | 5.12 m | 否 |
| 3 | (2.16, 4.08) | 3.05 m | 否 |
| 4（替补） | (2.16, 6.16) | 1.24 m | 否 |
| 7 | (3.48, 4.08) | 3.67 m | 否 |
| 101 | (10.08, 6.08) | 5.12 m | 否 |
| 103 | (9.84, 3.92) | 3.05 m | 否 |
| 104（替补） | (9.84, 1.84) | 1.24 m | 否 |
| 107 | (8.52, 3.92) | 3.67 m | 否 |

### 2.3 结论：两者是不同概念，且数值上不重合

- **官方基地标识**是 STEP 里真实存在的贴地面，用于区分阵营侧别；它不等于机器人出生点。
- **官方机器人出生点/朝向**在 STEP 中**不存在**。这类信息由规则手册规定，本项目仓库内没有该手册（官方 PDF 按素材策略排除）。因此本轮把“官方出生点”标记为 **待录入**，不能从 CAD 或底图推断。
- **演示出生点**是代码里合成的采样位置，目的是让画布上八台机器人分散且都落在场内。数值上最近的一台（4/104）仍偏离本方基地中心 1.24 m，**没有任何一台落在基地标识范围内**。
- 八台的偏移量完全对称（5.12/3.05/1.24/3.67 两侧相同），说明这是刻意构造的布局，不是测量结果。

保持现状，不把演示出生点改名为“出生点”，也不让区域数据依赖它。

## 3. 坐标系与数据来源（后续区域文件必须沿用）

- 单位：米。原点：内场西南角 `(0, 0)`。`+x` 向东（0→12），`+y` 向北（0→8）。
- 图像约定：像素第 0 行对应 `y = 8.0`（北），第 0 列对应 `x = 0.0`（西），与 `TGULMapGeometry.worldToCanvas()` 一致。
- CAD 变换：`sim_x = (6000 − CAD_X) / 1000`，`sim_y = (4000 − CAD_Z) / 1000`，`height = −CAD_Y / 1000`（CAD 竖直轴 −Y 向上）。
- 源文件：`RMUL2027_3V3_V1.0.0.stp`，SHA-256 `7d47c1b6…4a48ca4`，模型 `00_RMUL_2027_3V3_STU_V100`。
- 测量记录：`recon_3v3.txt`（点云范围与实体普查）、`bands.txt`（按高度分层的面与实测面积）、`markers3d.txt`（阵营标识与绿色标识）。
- 该 STEP 的实体普查：`ADVANCED_FACE 1274`、`PLANE 1274`、`EDGE_CURVE/LINE 3069`，**全平面 + 直线边、无样条**，因此面轮廓可以被精确重建，不需要近似。

**明确禁止**：从 `tgul_3v3.png` / `tgul_3v3_cad.png` 的像素主观推断官方几何尺寸。底图只用于视觉呈现；此前的像素测量仅作为交付纹理与 CAD 的**一致性交叉校验**，不作为尺寸来源。

## 4. `tgul_3v3_zones.json` 数据格式设计

文件名与位置：`sim/server/static/tgul_maps/tgul_3v3_zones.json`（与 `tgul_3v3.json` 同目录，随静态目录一起提供）。

> 状态：**T1 已实现**。首版只收录有出处的区域，轮廓未提取的一律 `aabb_only`。
> **T2 已实现**：Python 与 JS 的 `point_in_polygon` 共用 `sim/tests/fixtures/tgul_zone_point_cases.json` 的 23 个用例；边界算命中，洞的边界算洞内。

```json
{
  "schema_version": 1,
  "map": "tgul_3v3",
  "coordinate_system": {
    "unit": "m",
    "origin": "inner-field south-west corner",
    "x": "east, 0..12",
    "y": "north, 0..8",
    "frame": [0.0, 0.0, 12.0, 8.0]
  },
  "source": {
    "file": "RMUL2027_3V3_V1.0.0.stp",
    "sha256": "7d47c1b6a6a0253a732e46cb122bb84410b11d5134bcb5658104299db4a48ca4",
    "model": "00_RMUL_2027_3V3_STU_V100",
    "method": "step_faces.py 面级多边形重建 + diag_bands.py 高度分层",
    "records": ["recon_3v3.txt", "bands.txt", "markers3d.txt"]
  },
  "status_vocabulary": {
    "measured": "轮廓来自 STEP 面，可直接参与点包含判定",
    "aabb_only": "只有包围盒；真实轮廓待提取，不得据此判定可达",
    "pending": "尚无官方测量，仅占位"
  },
  "zones": [
    {
      "id": "field.inner",
      "kind": "playable_frame",
      "label": "内场可行驶区",
      "status": "measured",
      "blocks_motion": false,
      "polygon": [[0, 0], [12, 0], [12, 8], [0, 8]],
      "evidence": "bands.txt: z=0 地面面; 围墙环 12.6x8.6 减 12x8 = 12.360 m2 与实测一致"
    },
    {
      "id": "control.central",
      "kind": "control_zone",
      "label": "中央 3x3 控制区",
      "status": "measured",
      "z_mm": 7,
      "blocks_motion": false,
      "polygon": [[4.5, 2.5], [7.5, 2.5], [7.5, 5.5], [4.5, 5.5]],
      "evidence": "bands.txt: z=7mm 面 9.000 m2 与 3.0x3.0 AABB 面积相等"
    },
    {
      "id": "terrain.highland_south",
      "kind": "terrain",
      "label": "南侧高地",
      "status": "aabb_only",
      "z_mm": 200,
      "blocks_motion": null,
      "aabb": [7.5, 0.94, 9.5, 5.0],
      "evidence": "bands.txt: z=200mm 面 6.350 m2，AABB 8.120 m2（78.2%），非矩形"
    },
    {
      "id": "spawn.unknown",
      "kind": "base_marking",
      "label": "官方机器人出生点",
      "status": "pending",
      "blocks_motion": null,
      "polygon": null,
      "evidence": "STEP 中不存在；需从官方规则手册录入，不得推断"
    }
  ]
}
```

### 字段约定

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 稳定标识，`域.名称` 形式，只允许小写字母、数字、下划线、点 |
| `kind` | 是 | `playable_frame` / `obstacle` / `passable` / `control_zone` / `terrain` / `base_marking` |
| `label` | 是 | 界面显示名 |
| `status` | 是 | `measured` / `aabb_only` / `pending` |
| `blocks_motion` | 是 | `true` / `false` / `null`（`null` 表示未知，见下） |
| `polygon` | `measured` 必填 | 闭合环，至少 3 点，逆时针，首尾不重复；坐标必须在 `frame` 内 |
| `aabb` | `aabb_only` 必填 | `[x0, y0, x1, y1]`，仅用于可视化，不参与阻挡判定 |
| `z_mm` | 否 | 面高（相对主地面） |
| `clearance_mm` | 否 | 可通行净高（隧道等） |
| `evidence` | 是 | 一句话说明这一条的数据出处，便于复核 |

### 未知量的处理规则（本轮定死，不留解释空间）

1. `blocks_motion = true` 要求 `status = measured`：**只有拿到真实轮廓才允许据此禁止位置**。
2. `blocks_motion = false` 表示已确认可通行，与轮廓是否测量无关（例如「允许上高地」已确认，轮廓仍是包围盒）。
3. `blocks_motion = null` 表示可通行性未知。判定时 `null` **不阻挡**，但必须产生一条 `unknown_zone` 警告。
4. 不允许用 `aabb` 代替 `polygon` 做点包含判定；`aabb_only` 区域不参与几何判定，只用于画布上的示意框。

## 5. 校验矩阵：已验证 / 仅视觉确认 / 待从 STEP 再测量

### 5.1 已验证（可复算，有独立核对）

| 项 | 证据 |
| --- | --- |
| 内框 12.000 × 8.000 m、外框 12.600 × 8.600 m、围墙厚 0.300 m、顶高 0.420 m | STEP SHA-256 与 `tgul_3v3.json` 声明一致；`CARTESIAN_POINT` 复算得 12600/8600；**围墙顶环实测面 12.360 m² = 12.6×8.6 − 12×8**，三项互相印证 |
| 中央控制区是 3.000 × 3.000 m 方形，面高 7 mm | `bands.txt` z=7 mm 面 9.000 m²，与 3.0×3.0 完全相等 |
| 两条隧道地面薄板各 2.000 × 0.800 m，面高 0.5 mm | 实测 1.600 m² × 2 条，与 2.0×0.8 完全相等；位置 x 2.50–4.50 / y 7.06–7.86 与 x 7.50–9.50 / y 0.14–0.94 |
| 红方标识 0.92–1.56 / 6.65–7.33，蓝方 10.44–11.08 / 0.67–1.35 | `markers3d.txt`；像素反算交叉校验偏差 2–9 cm |
| 底图 1500×1000、比例 1.5 与 12/8 一致 | `final_sizes.txt` + PNG 头 + `check_public_readiness` 结构校验通过 |
| 八台演示出生点都不在官方基地标识内 | 第 2.2 节数值比对 |
| 该 STEP 全平面无样条，轮廓可精确重建 | `recon_3v3.txt`：1274 面全部 `PLANE`，3069 条边全部 `LINE` |

### 5.2 仅视觉确认（看图得出，未契约化）

- 高地在场地的对角分布（南侧一块、北侧一块）以及它们各自的 L 形缺口；
- 隧道板与高地、围挡之间的相对关系（谁在谁下面、哪里能穿过）；
- 补给区位于西北角与东南角，形状不是完整矩形；
- 底图的烘焙阴影与官方地面标识只影响观感，不影响坐标。

这些结论**不能**直接写成 `polygon`。

### 5.3 待从 STEP 再测量（本轮结论：一律标记待测量）

| 区域 | 已知 | 缺口 | 判定依据 |
| --- | --- | --- | --- |
| 南/北高地平面 | AABB 2.00×4.06 m、z=200 mm | 实测面 6.350 m²，AABB 8.120 m²（78.2%）→ 有缺口，非矩形 | 面积比 ≠ 100% |
| 高地控制区 | AABB 1.20×1.20 m、z=201.2 mm | 实测 1.347 m²（93.5%） | 面积比 ≠ 100% |
| 补给区 | AABB 2.50×2.00 m、z=3 mm | 实测 4.512 m²（90.2%） | 面积比 ≠ 100% |
| 中央控制区面层 | z=10 mm | 实测 8.416 m²（93.5%） | 面积比 ≠ 100% |
| 隧道侧壁/顶板与 250–270 mm 台阶 | 仅有 AABB 与面高 | 完整轮廓与净高分布 | 尚未提取 |
| 障碍物通行性阈值 | **高地已确认可通行（维护者确认）** | 250–270 mm 台阶与隧道净高的通行性仍未定 | 规则问题，不是测量问题 |
| 官方机器人出生点与朝向 | **出生点位于西北角与东南角的阵营地贴上（维护者确认）** | 精确出生区尺寸、上场三台与替补的站位、初始朝向仍未录入 | STEP 只有地贴，没有出生站位 |

## 6. 实现计划（每轮只做一个小任务）

约束：不修改 `MQTT`、Qt 客户端、比赛规则；保留 `tgul` 命名；不开发 1V1。

### T1 — 区域数据文件与加载器（最小实现）

- 新增 `sim/server/static/tgul_maps/tgul_3v3_zones.json`，只写入第 5.1 节的已测项，其余按 5.3 标 `aabb_only` / `pending`。
- 新增 `sim/server/tgul2027_zones.py`：`load_zones(mode)`、schema 校验（闭合环、逆时针、点在 `frame` 内、`id` 唯一、`status` 与 `polygon`/`aabb` 的必填关系）、`frame` 与 `tgul_3v3.json` 一致性检查。
- 测试：合法加载、逐条非法用例（开放环、顺时针、越界点、重复 id、`measured` 缺 `polygon`、`aabb_only` 缺 `aabb`）。
- 验收：新增单测全绿；`GET /tgul_maps/tgul_3v3_zones.json` 返回 200。
- **注意**：该文件位于已登记的素材组 `sim/server/static/tgul_maps` 下，新增后会改变该组快照，必须同步更新 `tools/release/public_assets.json` 并跑 `check_public_readiness`，否则 CI 变红。

### T2 — `point_in_polygon`（已实现）

- Python：`zones.point_in_polygon(x, y, polygon)` 与 `zones.zones_at(x, y)`；边界上的点视为**命中**（约定入内）。
- JS：`tgul_map_geometry.js` 增加同语义 `pointInPolygon`，供画布侧复用。
- 测试：凸多边形、凹多边形、顶点、边上、外部、跨日界线式的退化输入；Python 与 JS 用**同一组用例和期望值**，保证两端语义一致。
- 验收：两端用例通过；无 `measured` 区域的坐标不会被误判为内部。

### T3 — 无效位置检测

- 新增 `zones.classify_position(x, y)` → `{"valid": bool, "reasons": [...], "unknown_zones": [...]}`。
- 接入点：`TGULStateManager.set_robot_position()`（服务端最终判定）与前端 `onDrag`（先本地提示）。
- 策略按第 4 节：`blocks_motion === true` 才拒绝；未知区域放行并附警告。
- 测试：场内空地、越界、`measured` 障碍内、`aabb_only` 区域内（应放行 + 警告）、边界点。
- 验收：现有 `set_robot_position` 合法/非法用例不回归；新增用例全绿。

### T4 — 区域进入/离开事件

- 新增 `zones.diff_zone_state(previous, current)` → `[{robot_id, zone_id, action: "enter"|"leave", at}]`，同一帧内按 `robot_id`、`zone_id` 稳定排序。
- 接入 `TGULMatchSimulationEngine._apply_current_frame()`，仅用于状态与前端展示，**不进入 MQTT**。
- 测试：进入、离开、同一帧跨越多个区域、原地不动不产生事件、边界抖动去抖。
- 验收：事件序列与手工构造的期望一致；演示帧的 `positions`/`hp` 行为不变。

### T5 — 画布区域叠加（可选，最后做）

- 在 minimap 上按 `kind` 画半透明轮廓；`aabb_only` 用虚线框并标注“待测量”。
- 与现有样式切换共存：区域叠加独立开关，不改变 `image_styles` 语义。
- 验收：三种回归（样式切换、拖拽、重置）全部保持；`calibrated` 文案不变。

### 每轮的固定回归清单

1. `python -m unittest discover -s sim/tests -t sim -p 'test_*.py'`（当前基线 52 项）
2. `node --test sim/tests/test_map_geometry.js sim/tests/test_tgul_map_geometry.js`（当前 8 项）
3. `python tools/release/check_runtime_resources.py`
4. `python tools/release/check_public_readiness.py`（涉及静态素材时必须先更新快照）
5. `python tools/release/check_docs.py`

## 7. 不回归承诺（本轮与后续每轮）

| 能力 | 约束 |
| --- | --- |
| 地图样式切换 | `image_styles` 语义不变；新增文件不得改动 `tgul_3v3.png` / `tgul_3v3_cad.png` |
| 拖拽 | `TGULMapGeometry` 与 `onDrag` 的世界↔画布换算不变；区域判定只做附加检查 |
| 重置 | `reset_match_simulation()` 后位置仍回到出生点（已验证） |
| 巡逻演示 | `PATROL_CYCLE_SEC`、幅度收紧、替补静止的行为不变 |
| 旧模式 | 非 `--tgul-mode` 启动路径完全不受影响 |

## 8. 需要产品/规则侧确认的问题

1. ~~障碍通行性阈值~~ → **已确认：允许上高地**。高地记为 `blocks_motion: false`，属可通行地形；
   250–270 mm 台阶与隧道净高的通行性仍待定。
2. ~~官方出生点位置~~ → **已确认：出生点在左上角（西北）与右下角（东南）**，即两块阵营地贴处。
   剩余待录入项：精确出生区尺寸、上场三台与替补的站位、初始朝向。
3. **未知区域策略**：第 4 节默认「未知不阻挡 + 警告」。若现场更希望「未知即禁止」，
   需要改成拒绝并提示，这是一行策略开关。

> 第 1、2 条是维护者的规则确认，**不是 STEP 测量的产物**；数据文件里以 `confirmed_by` 字段标注来源。
