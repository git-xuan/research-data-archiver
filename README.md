# 科研数据归档助手

面向科研数据管理的桌面工具：按官方分类树把散落的科研数据**规范化归档**，
自动生成**《科研数据元信息采集》台账**，并支持**抽样自查**与**问题清单导出**。

Windows 与 macOS 均可运行；提供 Windows 单文件 exe 与 macOS `.app` / `.dmg` 的构建脚本。

---

## 功能

工具按四个页面串成一条工作流：

| 页面 | 做什么 |
|---|---|
| **① 初始化归档目录** | 选一个空目录作为归档根，在分类树里**勾选要创建的分类**——一级 / 二级 / 三级都能只挑一部分，不勾的不会建出来；勾了子目录会自动带上其父目录。支持「全选 / 全不选」、实时显示"将创建 一级 x 个 · 二级 y 个 · 合计 n 个"，需要补建时再勾上点『补齐勾选的分类目录』，已建目录与已有数据不受影响。同时写入《归档说明.md》（只列实际创建的目录）与归档索引 |
| **② 文件归档** | 扫描文件夹或拖入文件 → 在列表里勾选 → 选一级/二级分类 → 复制归档。**不删除原始文件**；已归档的文件显示 `[已归档]` 且不可再勾选，**不会重复复制**；目标目录已有同名同大小文件时按已归档直接跳过 |
| **③ 归档自查** | 检查范围可精确到**任意一级子文件夹**；支持「全部文件」或「按二级分类随机抽样」，**抽样比例、每类保底数、每类封顶数都由用户自定**；勾选问题文件后一键导出 CSV 清单 |
| **④ 数据台账** | 每次归档后**自动生成《科研数据元信息采集》里对应的一行**，可导出**列序与官方文件完全一致**的 xlsx，直接复制粘贴回官方表。表格 10 列保证可读宽度，放不下时底部有**横向滚动条**，也可拖动表头调宽 |

> **表格列宽规则**：列少的表按比例**铺满窗口**（拖宽一列，其余自动让位，右侧不留白）；
> 列多的表（数据台账 10 列）**不会把列压到读不清**——放不下时出现横向滚动条，滚动即可看全。

### 界面

| 初始化归档目录 | 文件归档 |
|---|---|
| ![初始化](screenshots/1-初始化归档目录.png) | ![归档](screenshots/2-文件归档.png) |

| 归档自查 | 数据台账 |
|---|---|
| ![自查](screenshots/3-归档自查-抽样.png) | ![台账](screenshots/6-数据台账.png) |

---

## 直接运行（源码）

```bash
pip install -r requirements.txt
python app.py
```

macOS 用户可直接双击 `mac/run_on_mac.command`（首次会自动建虚拟环境并装依赖）。

## 打包

### Windows → 单文件 exe

```bash
python build.py
# 产物：dist/科研数据归档助手.exe
```

### macOS → .app / .dmg

**必须在 macOS 上执行**（PyInstaller 不是交叉编译器，Windows/Linux 无法产出 macOS 二进制）：

```bash
bash mac/build_mac.sh
# 产物：dist-mac/科研数据归档助手.app
#       dist-mac/科研数据归档助手.dmg
```

可选环境变量：`ARCH=arm64|universal2`、`SKIP_DMG=1`（只出 .app）、`PYTHON=/usr/bin/python3`。

### 没有 Mac，怎么拿 macOS 安装包？

用仓库里现成的 GitHub Actions 工作流 `.github/workflows/build-macos.yml`：

1. 把本仓库推到 GitHub；
2. 打开仓库的 **Actions** 页面 → 选「**构建 macOS 安装包**」→ **Run workflow**；
3. 跑完后在该次运行页面底部下载 artifact：
   - `rdarchiver-macos-arm64`（Apple Silicon 的 .dmg 与 .zip）
   - `rdarchiver-macos-x86_64`（Intel 的 .dmg 与 .zip）

打一个 `v*` 形式的标签（如 `v1.1.0`）再推送，还会**自动创建 Release** 并把安装包附上去。

> 关于 runner 标签：`macos-13` 已于 2025-12-04 完全退役、`macos-14` 于 2026-11-02 EOL，
> 因此工作流使用 `macos-15`(arm64) 与 `macos-15-intel`(x86_64)。

---

## 把安装包发给别人

可以。CI 产出的 `.dmg`（内含 App + `Applications` 软链 + `首次打开请看这里.txt`）就是标准的
macOS 分发包；`.zip` 也已把说明文件一并打进去，可以直接转发。

**唯一要注意的是 Apple 的 Gatekeeper**：本项目没有 Apple 开发者证书，未做**公证（notarize）**，
所以对方第一次打开会被拦一次。PyInstaller 会对 `.app` 做 **ad-hoc 签名**（不给证书时
`codesign -s -`），所以 App 能跑，只是拿不到 Apple 的"可信"背书。

### 对方（macOS 15 及以上）的放行步骤

> ⚠️ **「右键 → 打开」这个老办法从 macOS 15 (Sequoia) 起已被 Apple 取消**，别再用它。

**方式一（推荐，不用敲命令）**
1. 把 App 拖进「应用程序」
2. 双击打开，弹出「无法打开 / 无法验证开发者」后点「完成」
3. 打开 **系统设置 → 隐私与安全性**，往下滚到「安全性」
4. 看到「已阻止使用"科研数据归档助手"…」→ 点「**仍要打开**」→ 再确认一次，输入开机密码
5. 之后即可正常双击打开

**方式二（终端一条命令）**
```bash
xattr -cr "/Applications/科研数据归档助手.app"
```

### 想彻底免掉这一步？

只能走 Apple 官方路径，没有别的办法：

1. 加入 **Apple Developer Program**（99 美元/年）
2. 申请 **Developer ID Application** 证书，导出为 `.p12`
3. 在 CI 里注入证书与 Apple ID 凭据（仓库 Secrets），把构建改成：
   ```bash
   # 1) 用开发者证书签名（替换掉 PyInstaller 的 ad-hoc 签名）
   codesign --force --deep --options=runtime --timestamp \
            --sign "Developer ID Application: 你的名字 (TEAMID)" \
            "科研数据归档助手.app"
   # 2) 打成 dmg 后提交公证
   xcrun notarytool submit "科研数据归档助手.dmg" \
         --apple-id "$APPLE_ID" --team-id "$TEAM_ID" --password "$APP_PWD" --wait
   # 3) 把公证票据钉进去（关键，否则离线也照样拦）
   xcrun stapler staple "科研数据归档助手.dmg"
   ```
4. 之后任何人下载双击即可打开，不再有任何提示。

> 顺带说明：**打成 `.pkg` 安装包并不能绕过这一步**——未签名的 `.pkg` 同样会被 Gatekeeper 拦住
> （提示"安装包不符合 Gatekeeper 策略"），而且还要输管理员密码，体验反而更差。
> 对未签名的应用来说，`.dmg` +「拖进应用程序」才是最合适的分发格式。

### 不想让使用者操作任何一步？

把安装包**通过 U 盘 / 局域网共享 / AirDrop 之外的本地拷贝**给同事即可：
macOS 的隔离属性（`com.apple.quarantine`）是**下载程序**（浏览器、邮件、微信）打上的，
从 U 盘或网络共享直接拷贝过去的文件不带这个标记，双击就能开，没有任何提示。
一旦经由聊天工具或网盘传输，就会被标记，需要走上面的放行步骤。

---

## 归档区结构

初始化后在归档根目录下生成：

```
归档根目录/
├── 文献与情报数据/            ← 5 个一级分类
│   ├── 学术文献/              ← 30 个二级分类
│   └── ...
├── 实验与过程数据/
├── 表征与测试数据/
├── 计算模拟与模型输出数据/
├── 生产数据/
├── 归档说明.md                ← 自动生成，含分类树与使用说明
└── _归档索引/                 ← 软件的数据目录，请勿手工改动
    ├── manifest.json          ← 已归档文件索引 + 台账填报配置
    ├── 归档日志.csv            ← 每次归档的追溯记录
    └── 科研数据元信息台账.csv    ← 台账号（导出 xlsx 的源）
```

分类名中的 `/` 等 Windows 非法字符会替换为全角字符（如 `粒度/颗粒/粉末分析` → `粒度／颗粒／粉末分析`），
**以保证 Windows 与 macOS 归档出的目录名完全一致**，同一份数据可跨平台流转。

---

## 推送前自检

改完代码准备推送前，建议先跑一遍：

```bash
python mac/preflight.py
```

它会检查那些「本机不暴露、到 CI 才炸」的问题：`.gitignore` 是否挡住构建产物、
shell 脚本换行符是否为 LF（Windows 的 `core.autocrlf` 会造成 CRLF 而让 mac 端报
`\r: command not found`）、工作流 runner 标签是否仍可用、依赖是否齐全等。

---

## 依赖

- Python 3.10+
- PySide6（界面）
- openpyxl（台账导出 xlsx，**漏装会导致该功能不可用**）
- PyInstaller（仅打包时需要）
