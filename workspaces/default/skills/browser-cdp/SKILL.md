---
name: browser-cdp
description: 使用 Chrome 远程调试端口 9222 控制浏览器。相比 OpenClaw 默认模式，权限更高更稳定。触发：用户让你控制浏览器、截图、自动化网页操作时使用此技能。
allowed-tools: Bash, Gateway, Browser
---

# Browser CDP 9222 - 高权限浏览器控制

## 启动浏览器

每次使用前，先启动带 9222 端口的 chromium：

```bash
chromium-browser --headless=new --remote-debugging-port=9222 --no-sandbox --remote-allow-origins=* --disable-gpu --disable-dev-shm-usage --disable-software-rasterizer
```

或者用后台运行：

```bash
# 启动（如果已存在则先杀掉）
pkill -f "remote-debugging-port=9222" 2>/dev/null || true
sleep 1
chromium-browser --headless=new --remote-debugging-port=9222 --no-sandbox --remote-allow-origins=* --disable-gpu --disable-dev-shm-usage --disable-software-rasterizer &
sleep 3
```

## 验证

```bash
curl -s http://localhost:9222/json
```

## OpenClaw 配置

确保 `~/.openclaw/openclaw.json` 包含：

```json
{
  "browser": {
    "enabled": true,
    "defaultProfile": "openclaw",
    "profiles": {
      "openclaw": {
        "cdpUrl": "http://localhost:9222",
        "color": "#00AA00"
      }
    }
  }
}
```

修改后需重启 Gateway：

```bash
openclaw gateway restart
```

## 使用

直接用 browser 工具，profile 选 `openclaw`：

```python
# 查状态
browser(action="status", profile="openclaw")

# 截图
browser(action="screenshot", profile="openclaw")

# 打开网页
browser(action="open", profile="openclaw", targetUrl="https://example.com")

# 页面快照
browser(action="snapshot", profile="openclaw")

# 交互（点击、填表）
browser(action="act", profile="openclaw", request={"kind": "click", "ref": "e1"})
browser(action="act", profile="openclaw", request={"kind": "type", "ref": "e2", "text": "hello"})

# 导出 PDF
browser(action="pdf", profile="openclaw")
```

## 优势

- ✅ 权限高：直接通过 CDP 协议控制
- ✅ 稳定：不依赖 Chrome Extension
- ✅ 可自定义：可传各种 Chrome 启动参数
- ✅ 隔离：headless 模式不影响本地浏览器

## 注意事项

- 9222 端口如有冲突可改用其他端口（记得同步配置）
- headless 模式无 GUI，但功能完整
- `--no-sandbox` 在 root 环境下必须
