# Paper-Wiki

Paper-Wiki 是一个个人科研论文知识库项目。当前代码只实现 **Layer 0 原始资料解析** 和 **Layer 1 单篇论文三件套生成**：

- `summary.md`：论文精读摘要
- `prior_works.json`：直接前作与思想谱系
- `sci_pattern.json`：科学创新范式分类

当前版本不会更新 `wiki/`，也不会构建向量库、图谱查询或 HTTP API。

## 目录约定

```text
raw/{paper-slug}/
  论文 LaTeX 源文件，只读

artifacts/{paper-slug}/
  summary.md
  prior_works.json
  sci_pattern.json

prompts/
  LLM prompt 模板和科学范式 taxonomy
```

`paper-slug` 就是论文目录名，例如 `GraphWalker`。

## 1. 创建环境

本项目使用 conda 管理 Python 环境：

```bash
conda create -n paper-wiki -c conda-forge --override-channels python=3.11 -y
conda activate paper-wiki
```

安装依赖和本地命令：

```bash
pip install -r requirements.txt
pip install --no-build-isolation -e .
```

如果你的默认 pip 镜像缺包，可以使用官方 PyPI：

```bash
pip install -i https://pypi.org/simple -r requirements.txt
pip install -i https://pypi.org/simple --no-build-isolation -e .
```

## 2. 配置模型

在项目根目录创建或修改 `.env`：

```bash
MODEL_NAME=你的模型名
BASE_URL=你的 OpenAI-compatible API 地址
API_KEY=你的 API Key
```

也兼容 OpenAI 官方变量名：

```bash
OPENAI_MODEL=你的模型名
OPENAI_BASE_URL=你的 API 地址
OPENAI_API_KEY=你的 API Key
```

不要把 `.env` 或密钥内容提交到版本控制。

## 3. 放入论文

把论文 LaTeX 源码放到 `raw/{paper-slug}/` 下。解析器会优先寻找：

1. `main.tex`
2. `paper.tex`
3. `article.tex`
4. 包含 `\begin{document}` 的 `.tex` 文件
5. 最大的 `.tex` 文件

解析器会递归内联 `\input{...}` 和 `\include{...}`。

## 4. 先做 Layer0 解析检查

在真正调用模型前，建议先运行：

```bash
paper-wiki parse GraphWalker
```

默认会输出 INFO 级别日志，能看到入口文件、内联文件数量、章节命中情况等关键进度。需要更细的调试信息时使用：

```bash
paper-wiki parse GraphWalker --verbose
```

你需要关注输出里的这些字段：

- `entry_file`：是否识别到了正确主文件
- `source_files`：是否内联了预期的章节文件
- `matched_sections`：是否命中 `introduction`、`related_work`、`method`、`experiments`
- `estimated_tokens`：输入给 LLM 的大致 token 规模

## 5. 生成 Layer1 三件套

确认 parse 没问题后运行：

```bash
paper-wiki ingest GraphWalker
```

如果目标目录已经有产物，默认不会覆盖。需要重生成时使用：

```bash
paper-wiki ingest GraphWalker --overwrite
```

如果模型调用或 JSON 校验失败，CLI 会输出当前失败阶段和错误信息。需要异常堆栈和更详细的内部日志时使用：

```bash
paper-wiki ingest GraphWalker --overwrite --verbose
```

生成结果位于：

```text
artifacts/GraphWalker/summary.md
artifacts/GraphWalker/prior_works.json
artifacts/GraphWalker/sci_pattern.json
```

## 6. 人工审查

生成后的文件还不能直接进入未来 Layer2 图谱，尤其是 `prior_works.json`。

建议检查：

- `summary.md` frontmatter 中 `title`、`authors`、`contribution_type` 是否正确
- `summary.md` 正文是否有明显幻觉或遗漏
- `prior_works.json` 中论文标题、年份、作者、角色是否真实准确
- `sci_pattern.json` 的主要范式是否符合你的判断

人工确认后，未来 Layer2 才应该把 `reviewed` 产物纳入 wiki、图谱或 RAG 索引。

## 7. 运行测试

```bash
pytest
```

当前测试覆盖：

- LaTeX 入口文件识别、`\input` 内联和章节匹配
- Pydantic schema 校验
- mock LLM 的端到端 ingest 流程

## 8. 日志说明

CLI 使用 Python 标准库 logging，不需要额外安装依赖。

默认日志级别是 `INFO`，会显示：

- LaTeX 解析开始和结束
- 入口文件识别结果
- 四类目标章节是否命中
- 每个 Layer1 产物的生成阶段
- LLM 调用开始和完成
- 产物写入路径

`--verbose` 会切到 `DEBUG`，额外显示：

- 实际内联的 `.tex` 文件列表
- `\input` / `\include` 内联细节
- JSON schema 校验重试信息
- CLI 异常堆栈

日志不会输出 `.env` 中的 API Key。

## 9. 常见问题

### 找不到 conda 包

可以改用 `conda-forge`：

```bash
conda create -n paper-wiki -c conda-forge --override-channels python=3.11 -y
```

### pip 镜像缺包

使用官方 PyPI：

```bash
pip install -i https://pypi.org/simple -r requirements.txt
```

### parse 没有命中章节

检查主文件是否正确，或 LaTeX 章节标题是否过于特殊。当前关键词在 `src/paper_wiki/ingestion/latex_parser.py` 的 `TARGET_SECTIONS` 中维护。

### ingest 报 JSON 校验失败

说明模型输出不符合 schema。代码会自动重试数次；仍失败时可以换更强模型，或调整对应 generator 的 prompt。
