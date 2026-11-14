# TGUL Round 3 — 安装脚本 v3.1 修复版

## 修复原因
旧版安装脚本在 `drawMinimap()` 中采用中文注释+邻近语句的逐字匹配。
若用户文件中的注释或换行变化，会抛出 `expected 1 anchor, found 0`。

新版使用 `drawMinimap()` 到 `getMousePos(evt)` 函数之间的限定区域，
按实际的 `ctx.clearRect()`、`ctx.save()`、机器人坐标表达式定位，
支持中文注释被删除或改变。若找不到期望的绘图逻辑，仍安全退出。

## 安装到已 Clone 的仓库
解压 ZIP 覆盖仓库根目录的 `apply_tgul_round3.py`：
```bash
cd /home/wangyifan/RM27_Client
cp apply_tgul_round3.py apply_tgul_round3.py.before-hotfix
python3 -m zipfile -e tgul_round3_hotfix.zip .
source sim/.venv/bin/activate
python apply_tgul_round3.py
python -m unittest discover -s sim/tests -t sim -p 'test_*.py' -v
node --check sim/server/static/app.js
node --test sim/tests/test_tgul_map_geometry.js
git diff --check
```

## 验证范围
使用与原源码相同的结构、不同中文注释和缺失绘图命令等合成夹具测试：
- 注释修改或删除：安装成功，Node.js 语法检查通过
- 重复执行：无二次修改
- 关键绘图调用缺失：安装失败且输入源码不变
- 10 项 Python 规则/地图集成样例测试通过

**由于无法直接访问用户本机源码，尚不能保证完全适配所有个人修改。
如再次失败，请提供 `app.js` 的具体函数片段及新错误信息。**
