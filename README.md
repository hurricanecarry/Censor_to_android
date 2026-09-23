# Unity 游戏《社区审查》(The Censor) Android 移植复盘：资源提取 · 构建流水线 · 渲染缺陷定位

> 把一个**只发行 Windows 端**的 Unity 商业游戏（下称 **Censor**）搬到 Android 真机跑通，并定位、修复了一个**只在 Android 上出现**的画面缺陷。
> 本仓库只收录**我自己写的工具脚本与复盘文档**，不含任何游戏素材、资源包、安装包或反编译产物。

**English (short):** A retrospective on porting a Windows-only Unity game to Android: rebuilding 68 AssetBundles from extracted resources, building a 944 MB IL2CPP/ARM64 APK, and tracking down an Android-only rendering defect (colored block artifacts) down to the texture importer's `alphaIsTransparency` flag interacting with a premultiplied-alpha additive render path — verified by pixel-level statistics (343,579 stray pixels → 0). Tooling and documentation only; **no game assets are included**.

---

## 结果一览（都有可复核的产物作依据）

| 项目             | 数值                                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| 交付安装包       | 944,438,242 B（≈900 MiB），IL2CPP / ARM64，minSdk 22                                              |
| 重建资源包       | 68 个 bundle / 369,982,345 B：RootPackage 63 个（351,656,148 B）+ DLCPackage 5 个（18,326,197 B） |
| Android 画质等级 | 默认质量 2 → 5（与原版 Windows 一致）                                                             |
| 缺陷量化         | 出货包内纹理"alpha=0 但 RGB≠0"的像素数：**343,579 → 0**                                           |
| 图集修复         | **240 份**纹理 meta 关闭 `alphaIsTransparency`（两个批次：123 + 117）                             |
| 着色器修复       | 7 个特效着色器的混合/写深度设置                                                                   |
| DLC 地址表       | 从原版二进制 manifest 还原 **37/37** 条并全部命中                                                 |

---

## 1. 问题现象

从原包提取资源、重建资源包、出 Android 包后，游戏能启动、场景能进，但真机上出现**大量彩色块状碎片**（壁纸、立绘、骨骼动画上都有），Windows 原版没有。

## 2. 诊断探针（这一步是整件事的关键）

做了两类可复核的探针：

1. **运行时探针**：在游戏内加一个可开关的诊断开关（用编译宏 `CENSOR_PORT_DIAGNOSTICS` 隔离，**不污染正式包**）。真机侧通过 `persistentDataPath` 下的控制文件 + **每次随机 nonce** 下发指令，探针回传运行时几何/材质数据（骨骼动画顶点的 alpha/RGB 分布等）。
   - 用随机 nonce 是为了保证"这一次的结果"确实对应"这一次的指令"，避免读到上一次的残留。
2. **离线像素统计**：Python 脚本直接把出货 APK 里的纹理解出来逐像素统计，数"**alpha = 0 但 RGB ≠ 0**"的像素——这正是"扩色"缺陷的指纹。

## 3. 审计了什么

- **资源包结构**：`env.container` 路径 → 资源的映射（注意 AssetBundle 里的容器路径是**小写**的），二进制 manifest 的地址表（`dlcpkg` 地址里粘了一个长度字节，只在 `ord(addr[-1]) == len(path)` 时才该剥掉）。
- **纹理导入设置**：逐份核对 `TextureImporter` 的 `alphaIsTransparency`、sRGB、meshType 等字段，并与原版逐字段对照。
- **材质 → 着色器 → 贴图**的引用链：找出哪些材质真的会走"叠加（additive）"分支。
- **反编译两份 Spine 运行库 DLL 做逐版本对照**：确认两份 `MeshGenerator` 一致，从而**排除"运行库本身有 bug"**这条假设。

## 4. 根因

**`alphaIsTransparency = 1` 的 PMA 图集，会把可见像素的 RGB"扩色"进全透明像素区**；而预乘 alpha 的叠加（additive）渲染路径会**读到这些 RGB**，于是本该透明的地方被画成了彩色方块。

- 同一份 PNG 在两个工程里字节完全一致，差别只在导入设置 → 可用**单变量 A/B/A**验证。
- 期间有一个被推翻的假设（"色彩空间 sRGB 配错了"）已记录并撤回，见 `操作手册.md`。

## 5. 修复与验证

1. 关闭问题图集的 `alphaIsTransparency`（240 份 meta，两个批次）。
2. 修正 7 个特效着色器的混合与写深度设置（`Blend` 可配、`ZWrite Off`、`Cull Off`）。
3. 验证：出货包内纹理的"异常像素"计数 **343,579 → 0**；压缩格式（ETC2）下降 99.7–99.9% 且**贴图属性零变化**；真机逐场景复验。

## 6. 目录结构

```
操作手册.md          完整流程 + 命令与坑速查（照着走一遍 / 查表用）
tools/editor/        自己写的 Unity 编辑器脚本（C#）：打包、资源包规则、索引、探针、校验
tools/python/
  forensics/         像素级取证：纹理差异、区域比对、拼图、异常像素统计
  bundles/           APK / AssetBundle / 容器审计
  manifests/         地址表生成与校验（含 DLC）
  shaders/           着色器与材质状态对照、引用链
  identity/          资源身份与字段级对照
  verify/            出货校验、灰度推进
ledger/BUILD_LEDGER.tsv   构建台账（版本 / 大小 / 校验值 / 变更点，路径已脱敏）
```

## 7. 工具链

Unity 2022.3（IL2CPP / ARM64）· YooAsset（AssetBundle 构建与清单）· Spine 运行库 · Python（自写取证脚本）· adb / logcat（真机取证）· ilspycmd（反编译 Mono 程序集）· capstone（反汇编）· Pillow / numpy（像素统计）

## 8. 复现说明与免责声明

- 本仓库**不包含**任何游戏素材、AssetBundle、APK、纹理、音频、反编译产物或第三方付费插件（如 AllIn1SpriteShader 的着色器本体）。
- 文档与脚本用于**说明方法**，不是"一键复刻工具"；要复现请自备**你拥有合法授权**的游戏副本与开发环境。
- 文中路径已脱敏为 `<BUILD_DIR>` / `<UNITY_PROJECT>` / `<ORIGINAL_BUILD>` 之类的占位符。
- 若你是权利人并认为本仓库有不当之处，请提 issue，会立刻处理。

## 9. 许可

代码部分以 MIT 许可发布，见 `LICENSE`；文档以 CC BY 4.0 发布。详见 `NOTICE.md`。

## 10. 文档中的占位符

文中与脚本里出现的路径占位符含义如下（原始绝对路径已移除）：

| 占位符                     | 含义                                        |
| -------------------------- | ------------------------------------------- |
| `<BUILD_DIR>`              | 构建与产物操作目录（APK、日志、备份、脚本） |
| `<DOCS_DIR>`               | 文档目录                                    |
| `<UNITY_PROJECT>`          | Unity 工程目录                              |
| `<ORIGINAL_BUILD>`         | 原始 Windows 版本安装目录（**未收录**）     |
| `<PY_DEPS>`                | 第三方解码库目录（UnityPy 等）              |
| `<EVIDENCE_DIR>`           | 证据目录：像素对照图、数据表（**未收录**）  |
| `<ANDROID_SDK>` / `<HOME>` | Android SDK 与用户主目录                    |

> 证据图片与数据表**不在本仓库**：图里含游戏画面（版权素材），数据表体积较大且含游戏资源名。
