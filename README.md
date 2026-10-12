# KOTOR II 简体中文本地化

《星球大战：旧共和国武士Ⅱ》Steam Windows 版汉化项目，配合 TSLRCM + M4-78EP 合并版使用。

- [汉化 MOD](https://steamcommunity.com/sharedfiles/filedetails/?id=3816191703)
- [英文前置：TSLRCM + M4-78EP](https://steamcommunity.com/sharedfiles/filedetails/?id=1402798020)
- [高帧修复与中文缓存兼容](https://steamcommunity.com/sharedfiles/filedetails/?id=3816551034)

欢迎个人、译者和专业团队参考技术方案，参与翻译与校对、接手维护，或为其他 KOTOR II MOD 制作汉化补丁。可以通过 Issues 讨论问题，或提交 Pull Request；新团队也可以 Fork 后独立维护，并保留来源与致谢。

## 使用汉化

订阅英文前置和汉化，在 Steam 的创意工坊加载顺序中将汉化放在前置之后。高帧修复与中文缓存兼容组件需要按其工坊说明手动安装根目录 DLL；仅订阅不会自动安装这个组件。

仓库是维护与交接资料，不是可以直接复制到游戏里的成品包。实际游玩请使用工坊版本。

## 仓库内容

| 目录 | 内容 |
| --- | --- |
| `translations/final` | 已发布 0.5.14 对应的中文译文、稳定 ID、英文来源摘要及审校状态 |
| `glossary` | 译名表和参考来源，供讨论与校对；其状态不保证与每一条现行译文一致 |
| `tools` | TLK/GFF、字体资源、GUI、存档转换及本地构建工具 |
| `data` | 当前字形映射、GFF 定位、GUI/字体配方、历史文本摘要库 |
| `fonts` | 已发布字体图集和 TXI 配方；不包含字体源文件 |
| `native` | 高帧入口、中文消息缓冲兼容代码及签名表 |
| `docs` | 构建、接手、第三方 MOD 扩展与存档说明 |
| `licenses` | 第三方代码与阿里巴巴普惠体的版权文件 |

共 153,698 条记录：原版参考 74,024、前置 MOD 74,071、GFF 5,603 组（对应 7,022 处）。这些数字包括内部标签、变量和参考条目，不等于不同的玩家可见台词数量。

完整英文原文、游戏 EXE、模块原文件、原汉化补丁包、个人存档和运行日志不随仓库发布。构建时从本机安装的游戏和英文前置读取原文，并核对 SHA-256。

## 开发与构建

Python 3.10+，安装依赖后将 `project.example.json` 复制为 `project.json`，填写游戏与 Workshop 路径。

```powershell
python -m pip install -r requirements.txt
python tools/validate_public_data.py
python -m unittest discover -s tools -p "test_*.py"
python tools/build_public_mod.py --output build/chs
```

构建只写入指定输出目录，不安装或上传资源。详见 [构建说明](docs/BUILD.md)。译文回交与维护入口见 [接手说明](docs/MAINTAINER_HANDOFF.md)，扩展其他 MOD 见 [MOD 汉化指南](docs/OTHER_MODS.md)。

## 当前状态

公开资料对应汉化 **0.5.14-subtitle150**，使用 16 列四级灰度组合字形和兼容的交替透明步进，过程动画及对话字幕目标字号为 1.5 倍。字体与文本需要同时更新。

原生兼容组件 **0.1.2** 新增字体缩放计量修复。若在 2560×1440 下出现菜单偏移或说明挤成窄列，请更新该组件的根目录 DLL，并在 `[Chinese Text Fix]` 中设置 `FontScaleFix=1`。2K 主菜单与技能说明已确认恢复正常；其他分辨率仍需实机复核。

已完成发布文件校验、完整 TLK 和 GFF 位置校验，以及部分菜单、存档和区域切换测试。0.5.14 的字幕视觉与完整剧情流程仍需实机复核。数据中的 `needs_context`、保留英文和术语候选需要逐条判断，不应自动视为全部漏译。

## 许可与致谢

项目自编代码使用 [MIT](LICENSE)。汉化文本、游戏原文、第三方代码和字体分别遵循其来源和版权，见 [版权范围](COPYRIGHT.md)。

感谢 TSLRCM 与 M4-78EP 制作团队。高帧修复基于 D3M0 / High FPS Fixes 1.0.1，运行库来自 Lane Dibello 与 Kotor Patch Manager 贡献者。字体采用阿里巴巴普惠体，译名参考来源见 `glossary/sources.jsonl`。

感谢3DM汉化团队，本MOD在本地化工作中借鉴和参考了原3DM汉化
