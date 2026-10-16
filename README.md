# KOTOR II 简体中文本地化

《星球大战：旧共和国武士Ⅱ》Steam Windows 版汉化项目，配合 TSLRCM + M4-78EP 合并版使用。

- [汉化 MOD](https://steamcommunity.com/sharedfiles/filedetails/?id=3816191703)
- [汉化问题反馈网页](https://francisagust198.github.io/kotor2-chinese-localization/)（填写后登录 GitHub 提交，可附截图）
- [英文前置：TSLRCM + M4-78EP](https://steamcommunity.com/sharedfiles/filedetails/?id=1402798020)
- [MOD 汉化教程与可视化工具](docs/MOD_TRANSLATION_TUTORIAL.md)
- [高帧修复与中文缓存兼容](https://steamcommunity.com/sharedfiles/filedetails/?id=3816551034)

欢迎个人、译者和专业团队参考技术方案，参与翻译与校对、接手维护，或为其他 KOTOR II MOD 制作汉化补丁。可以通过 Issues 讨论问题，或提交 Pull Request；新团队也可以 Fork 后独立维护，并保留来源与致谢。

## 使用汉化

订阅英文前置和汉化，在 Steam 的创意工坊加载顺序中将汉化放在前置之后。高帧修复与中文缓存兼容组件需要按其工坊说明手动安装根目录 DLL；仅订阅不会自动安装这个组件。

仓库是维护与交接资料，不是可以直接复制到游戏里的成品包。实际游玩请使用工坊版本。

## MOD 汉化工作台

[下载 Windows 工作台 0.2.1](downloads/KOTOR2_MODTranslator_021.zip)，无需 Python。支持 MOD 汉化 / 原版文本修正二选一、手动与 CSV 编辑、配置兼容 API 的 AI 草稿翻译，并打包为独立汉化 MOD。详见 [教程](docs/MOD_TRANSLATION_TUTORIAL.md)。共享文本接口仍为候选，实机验收尚待完成。

## 仓库内容

| 目录 | 内容 |
| --- | --- |
| `translations/final` | 当前已发布版本对应的中文译文、稳定 ID、英文来源摘要及审校状态 |
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

公开资料对应汉化 **0.5.20-untranslated-fix**，使用 16 列四级灰度组合字形和兼容的交替透明步进，过程动画及对话字幕目标字号为 1.5 倍。字体与文本需要同时更新。

原生兼容组件 **0.1.3** 默认开启中文缓存兼容与字体缩放计量修复（显式设置为 0 时仍关闭）。若在 2560×1440 下出现菜单偏移或说明挤成窄列，请更新该组件的根目录 DLL。2K 主菜单与技能说明已确认恢复正常；其他分辨率仍需实机复核。

已完成新版完整回交文本的接入、全量来源与格式检查、发布文件及字形覆盖核验。本轮复核在回交稿基础上修订 5,897 条记录；全量结构检查不等于每句对白均完成独立人工复核。部分菜单、存档、区域切换和对话末项选择已有实机验证；新版文本的完整剧情流程及全部长对白逐句语义复核尚未完成。

玩家可通过[反馈网页](https://francisagust198.github.io/kotor2-chinese-localization/)整理问题、复现步骤和游戏环境，然后登录 GitHub 附上截图并提交 Issue。无 GitHub 账号可在工坊讨论区反馈。网页维护方式见[说明](docs/FEEDBACK_SITE.md)。

0.5.17 完成人名一致性专项校订，修订 563 条记录。全称、名、姓分别按原文统一，清除“长堂”“黑贝”等旧译和重复姓氏，并补回部分遗漏的人名。姓名规则与维护注意事项见[人名术语说明](glossary/NAME_TERMINOLOGY.md)。构建会核查已知姓名变体，避免旧的部分名称扩写规则再次追加姓氏。字体、字形编码和界面资源保持；完整剧情测试与全部对白逐句复核仍未完成。

## 许可与致谢

项目自编代码使用 [MIT](LICENSE)。汉化文本、游戏原文、第三方代码和字体分别遵循其来源和版权，见 [版权范围](COPYRIGHT.md)。

感谢 TSLRCM 与 M4-78EP 制作团队。高帧修复基于 D3M0 / High FPS Fixes 1.0.1，运行库来自 Lane Dibello 与 Kotor Patch Manager 贡献者。字体采用阿里巴巴普惠体，译名参考来源见 `glossary/sources.jsonl`。

感谢3DM汉化团队，本MOD在本地化工作中借鉴和参考了原3DM汉化

0.5.15 将对话回复区域上移一行，改善选项较多时末项无法用鼠标选择的问题。1080p 下已确认末项可准确高亮和点击；字号、行距及 1.5 倍字幕保持。其他分辨率仍需实机复核。

0.5.16 接入新的完整回交文本，完成全量来源、标记和格式核对，并修正漏译、错配、战斗提示变量与名称一致性。补入 66 个字形编码，现有字体与界面资源保持。存档转换工具 1.0.1 增加近期版本缓存识别库，可由工坊单独更新。全量结构检查不等于每句对白均完成独立人工复核；新译文的完整游戏流程仍待验证。

0.5.18 修订 178 条对白与相关文本，按语境核对术语、错别字和否定关系；Bonus Mission 使用“附加任务”。[本轮校订说明](核查记录.md)。完整剧情测试及全部对白逐句人工复核仍未完成。

0.5.19 修复八项技能的属性标题与正文粘连、段落及数字空格；只改空白与换行，规则与数值不变。实际技能页面显示仍待用户验收。

0.5.20 补译 M4-78 的 7 条内嵌短句对白，统一军械库终端“计数值”提示及物品、角色译名。本轮按英文来源哈希核对，保留动作备注、声音引用和未改动资源；完整剧情仍需继续实机复核。
