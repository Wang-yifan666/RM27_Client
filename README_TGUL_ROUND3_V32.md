# TGUL 2027 第三轮地图安装修复版 v3.2

## 解决的问题
先前安装脚本用注释和具体的 `const x`、`const y` 代码定位 `drawMinimap()`，
在用户本地 `app.js` 不同于假定版本时出现：
`app.js/drawMinimap robots: expected exactly one semantic match, found 0`。

v3.2 不匹配原函数体内部的注释/代码，而是定位函数声明，将原始方法完整保留并改名为：
`drawLegacyMinimap`、`startLegacyDrag`、`onLegacyDrag`，
再为 TGUL 模式新增包装方法。路径编辑器也使用独立包装方法。

## 安装前提
已将 `tgul_round3.zip` 解压到仓库根目录，但旧脚本因为报错没有写入源码。
已完成第二轮 `TGULStateManager` 的安装和测试。

## 操作
将此 ZIP 放到 `/home/wangyifan/RM27_Client/` 目录，然后：

    cd /home/wangyifan/RM27_Client
    cp apply_tgul_round3.py apply_tgul_round3.py.previous
    python3 -m zipfile -e tgul_round3_hotfix_v32.zip .
    source sim/.venv/bin/activate
    python apply_tgul_round3.py
    node --check sim/server/static/app.js
    node --test sim/tests/test_tgul_map_geometry.js
    python -m unittest discover -s sim/tests -t sim -p 'test_*.py' -v
    git diff --check

预期安装消息：

    TGUL round 3 map integration installed.

## 回归验证
使用合成的上游 Web 结构执行：
- 中文注释更换、删除
- 原机器人坐标计算表达式修改
- 原方法保留的 Vue 方法调用与代码语法测试
- 地图坐标反算、拖拽位置更新与原版方法回退
- 缺失关键函数时不修改原文件
- 重复安装检测
- Python 地图适配 10 项模拟接口测试

注意：这是针对已核对的仓库方法签名进行的适配；用户的
`app.js` 实际内容尚未上传，不能声称已在用户本机验证。
如果仍失败，请提供原文件 `drawMinimap()`、`startDrag()`、`onDrag()`
的代码片段而非继续尝试模糊替换。

## 后续导图
使用 SolidWorks 打开官方 STEP、正交上视图、导出 PNG；
图像裁剪到真实场地内边界，并核对尺寸、方向、红蓝侧。
保存为 `sim/server/static/tgul_maps/tgul_3v3.png` 等。
