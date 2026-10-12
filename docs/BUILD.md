# 本地构建

需要自己的 Steam KOTOR II 安装及未改动的英文 TSLRCM + M4-78EP 合并版（工坊 1402798020）。`project.json` 的 `game` 指向游戏目录，`workshop` 指向 `steamapps/workshop/content/208580`。配置文件不会提交到 Git。

```powershell
Copy-Item project.example.json project.json
python -m pip install -r requirements.txt
python tools/validate_public_data.py
python -m unittest discover -s tools -p "test_*.py"
python tools/build_public_mod.py --output build/chs
```

构建工具从本机提取英文原文。原文 SHA-256、语音和字段来源不一致时停止；不退回旧汉化。输出目录必须是尚不存在的新目录。

`docs/ci-example.yml` 提供自动检查配方。维护者可将其放入 `.github/workflows/` 启用 GitHub Actions；当前仓库先保留本地检查流程。

`content/dialog.tlk` 为前置 MOD 中文表，`base-reference/dialog.tlk` 只供原版参考，不能同时覆盖到工坊内容。字体从仓库图集和 TXI 配方生成 TGA/TPC；GUI 从本机资源应用经过摘要验证的配方；GFF 从本机英文资源按定位修改。

输出不含编译后的存档工具 EXE或其他第三方二进制，也不自动安装到游戏。构建报告逐条检查 TLK/GFF，并与字体、GUI 配方核对；完整成品与工坊版本仍可能因文档、工具和历史打包过程有所不同。

如果要读取双语记录，可运行 `python tools/restore_english_sources.py --output build/bilingual`。英文只恢复到本机输出目录，供校对和交接，不要随仓库重新上传整个原文表。

## 存档工具

```powershell
python tools/save_cache_converter.py
```

工具会尝试发现游戏和汉化订阅目录，使用 `data/save-cache-catalog.json.gz`。先退出游戏再扫描或生成副本。打包 EXE 可使用 PyInstaller，需把该目录中的摘要库以 `save-cache-catalog.json.gz` 名称加入资源。

## 原生组件

`native/` 是 32 位 Windows DLL 入口源码。使用支持 x86 Windows 的 C 编译器，链接 bcrypt/user32，并使用 `highfps_loader.def` 导出表，定义 `WORKSHOP_ID=L"3816551034"`。例如安装 Zig 后：

```powershell
zig cc -target x86-windows-gnu -Os -shared -s '-DWORKSHOP_ID=L"3816551034"' native/highfps_loader.c native/highfps_loader.def -lbcrypt -luser32 -o build/dinput8.dll
```

此 DLL不修改 EXE，仅允许匹配签名的补丁。中文消息兼容通过 `[Chinese Text Fix] MessageBufferFix=1` 启用。高帧负载由订阅提供；源码的签名表不是完整的上游运行库。修改 DLL 后必须重新测试，不能用编译成功替代运行验收。

0.1.2 另提供 `[Chinese Text Fix] FontScaleFix=1`。它只修正本项目组合字体的累计宽度计量，保留普通非组合字体的原转换；用于改善非整数缩放下的居中与换行。两个开关可分别启用。

字体原生测试可编译 `native/font_scale_selftest.c` 为 x86 Windows EXE 并运行。包含 6 种比例、576 个完整字形边界、x87 调用约定、重复扫描、普通字体回退和签名冲突/内存保护检查；这些离线结果不替代游戏内验证。
