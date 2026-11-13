# OSD 与 SAIM 最终 checkpoint

本仓库的 [Releases](https://github.com/Ecipsed/jianghuai/releases/tag/checkpoints-20261113) 提供四组最终部署模型：

| 方法 | ViT-B/32 | LLaMA-3.2-1B-Instruct |
|---|---|---|
| OSD 微调 + Task Arithmetic | 八任务最终模型 | 七任务最终模型 |
| SA-BCD 微调 + SAIM 合并 | 八任务最终模型 | 七任务最终模型 |

原始权重按字节保存，未量化、未转换；ViT 附带八个固定分类头，LLaMA 附带 config、tokenizer 和 SFT 协议。最终推理 checkpoint 不包含完整优化器恢复状态。

权重作为 Release 附件提供。每种方法的 tar 分为三卷，每卷小于 2 GB；下载三个分卷后恢复即可。仓库中的 `checkpoint-manifest.json` 记录分卷、归档及每个原始文件的 SHA-256。

## 下载

可以在 Release 页面手动下载分卷，也可以在本仓库根目录运行以下命令。若只需一种方法，将 `osd saim` 改为 `osd` 或 `saim`。

```bash
mkdir -p checkpoint-assets
release_url="https://github.com/Ecipsed/jianghuai/releases/download/checkpoints-20261113"
for method in osd saim; do
  for part in 001 002 003; do
    asset="${method}-checkpoints-20261113.tar.part-${part}"
    curl --fail --location --retry 3 --continue-at - \
      "${release_url}/${asset}" -o "checkpoint-assets/${asset}"
  done
done
```

## 校验并恢复目录

只依赖 Python 3 标准库，不会加载模型或占用 GPU：

```bash
python3 restore_checkpoints.py --assets checkpoint-assets --dest .
# 仅恢复一种方法：添加 --method osd 或 --method saim
# 仅检查分卷：添加 --verify-only
```

恢复后的布局：

```text
continual-pretrain/
├── osd/checkpoint/
│   ├── vit-b-32/{model_final.pt,heads/,provenance.json}
│   ├── llama-1b/{model_after_task_7/,provenance.json}
│   ├── MANIFEST.json
│   └── README.md
└── saim/checkpoint/
    ├── vit-b-32/{model_final.pt,heads/,provenance.json}
    ├── llama-1b/{model_after_task_7/,provenance.json}
    ├── MANIFEST.json
    └── README.md
```

已有代码/结果包也以 `continual-pretrain/` 为顶层目录，可合并到同一目录。恢复脚本会校验已有文件；遇到内容不同的文件会停止，避免覆盖。

全部分卷约 10.1 GiB，恢复后 checkpoint 合计约 10.1 GiB。完成后可自行删除 `checkpoint-assets/` 中的分卷。模型来源：[OpenAI CLIP](https://github.com/openai/CLIP)、[LLaMA-3.2-1B-Instruct](https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct)。
