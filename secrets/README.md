## 这里放本地密钥（不要提交到 git）

### MinerU 云端 Precision Extract Token

请在本目录创建文件：

`medrag/secrets/mineru_token.env`

内容只需要一行（不要引号、不要多余空格）：

```
MINERU_TOKEN=<把你的 token 粘在这里>
```

说明：

- `medrag/.gitignore` 已忽略 `secrets/`，避免误提交。
- 你也可以不配文件，直接在终端 `export MINERU_TOKEN=...`（但不够“长期稳定”）。
