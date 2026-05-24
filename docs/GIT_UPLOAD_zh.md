# 如何把本地修改上传到 GitHub

第一次已经 `git init` / 加过远程的话，后面**只用提交你改动的文件**，不必每次上传整个项目。

## 1. 看状态

在项目根目录执行：

```bash
git status
```

会列出**已修改 / 新建 / 删除**的文件。

## 2. 只添加本次要提交的文件

可以按文件加，也可以用路径：

```bash
git add install-online.sh install.sh docs/ONE_LINE_INSTALL.md tools/panel_api_probe/
git add docs/GIT_UPLOAD_zh.md
```

不要 `git add` 不该进仓库的文件（密钥、数据库、`_ _pycache_ _` 等）。若 `.gitignore` 已写好，一般用 `git status` 检查一下即可。

也可以先 `git add -p` 按块挑选（注意不要用于需要交互确认的自动化场景）。

## 3. 提交

```bash
git commit -m "install: neutral paths; skip CLI menu by default; add API probe"
```

如果你没有要求使用 HEREDOC 写长说明，单行 `-m` 即可。

## 4. 推送到 GitHub

主分支常为 `main`：

```bash
git push origin main
```

若是第一次推当前分支，可能需要：

```bash
git push -u origin main
```

## 5. 「只上传修改过的」是什么意思？

Git 本就是**增量**：`push` 只传相对于远程**新的 commit** 里的改动，不会重新传整个仓库。  
你要做的是：**只把本轮相关的文件放进暂存区**（`git add`），这样既清晰又安全。
