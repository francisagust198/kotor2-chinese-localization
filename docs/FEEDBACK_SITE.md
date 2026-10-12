# 玩家反馈网页

公开入口：https://francisagust198.github.io/kotor2-chinese-localization/

页面由本仓库 `main` 分支的 `/docs` 目录通过 GitHub Pages 发布。入口为 `index.html`，样式为 `feedback.css`，表单逻辑为 `feedback.mjs`；不需要服务器密钥或构建依赖。

玩家填写后转到 GitHub 的新 Issue 页面，登录后可补充截图并确认提交。网页本身不创建 Issue，也不接收截图或存档。反馈公开保存在仓库 Issues，维护者可讨论、分类并跟踪修订。无 GitHub 账号的玩家可使用工坊讨论区。

浏览器可保留本机草稿，玩家可以关闭此功能或清空草稿。较长正文不会截断：自动带入链接超过长度阈值时，改为复制或下载正文，手动粘贴到 GitHub 提交页。页面不会把打开草稿、复制或下载称为“已提交”。

维护时同步更新页面的版本、进度与实际验证范围，不应把格式检查或部分实机验证描述为全量人工终审或完整流程测试。

本地预览：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

表单链接和长文本退路检查：

```powershell
node --test tools/test_feedback.mjs
```

请勿在浏览器代码中加入 GitHub Token。提交流程的人工测试应停在 Issue 草稿页面，避免创建公开测试垃圾反馈。
