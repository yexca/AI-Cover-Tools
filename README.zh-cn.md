# AI Cover Tools

语言：[English](README.md) | [简体中文](README.zh-cn.md) | [日本語](README.ja.md)

AI Cover Tools 是一个面向本地 AI 翻唱素材处理的 Windows 工具集。它目前主要覆盖训练前的音频准备阶段：提取干声、切分训练片段、检查素材质量、统计时长、分析音高和做峰值标准化。

当前已可用的功能：

- 图形界面：分离、切分、工具、设置、关于。
- 分离：基于 `python-audio-separator` 和配置的模型链，批量去伴奏、去和声、去混响、去噪，或保留指定声部。
- 切分：把音频按静音和时长规则切成更适合训练的数据片段。
- 工具：频谱图音质检查、文件夹总时长、音高报告、峰值标准化。

训练和推理页面已经预留，但目前仍是占位功能。训练声音模型和最终推理生成翻唱，暂时建议配合 Applio 等成熟工具完成。

## 快速开始

先运行安装脚本：

```bat
run-install.bat
```

安装脚本会在项目目录下创建或复用本地环境 `env`，并安装 GUI、PyTorch、FFmpeg、音频分离和工具依赖。正常使用不需要依赖系统 Python。

安装完成后启动图形界面：

```bat
run-gui.bat
```

如果你只想运行命令行分离流程，可以使用：

```bat
run.bat
```

## 推荐流程

1. 将原始歌曲或人声素材放入 `inputs`。
2. 在 GUI 的“分离”页提取更干净的人声。
3. 在“工具”页检查音质、总时长、音高范围，并按需要做标准化。
4. 在“切分”页生成训练用短片段。
5. 使用外部训练工具训练模型并推理。

## GUI 功能

### 分离

“分离”页用于编辑和运行模型处理链。你可以添加多个模型模块，并设置：

- 模型文件名
- 要保留的声部
- 声部别名
- pitch shift
- batch size、overlap、segment size 等常用参数

GUI 会把设置写入 `user_data/gui_separate_config.py`，然后调用同一套命令行分离流程。分离输出会先写入 `outputs`，完成后归档到 `archives/outputs-YYYYmmdd-HHMMSS`。

### 切分

“切分”页会递归扫描输入文件夹，并把音频切成训练友好的片段。默认输入为 `inputs`，默认输出为 `outputs`，默认格式为 `wav`。

常用参数：

- Threshold：静音阈值
- Minimum Length：最短片段长度
- Minimum Interval：最短静音间隔
- Hop Size：分析步长
- Maximum Size Length：保留静音的最大长度

支持读取常见音频格式，例如 `wav`、`flac`、`mp3`、`m4a`、`ogg`、`opus`、`wma`、`aiff`。输出格式支持 `wav`、`flac`、`mp3`。

### 工具

“工具”页包含四个独立功能：

- 音质检查：生成类似 Spek 的频谱图，长音频会按 10 分钟分段。
- 总时长：统计文件夹内所有支持音频的总时长。
- 音高报告：使用 Praat 或 RMVPE 分析数据集音高范围和分布。
- 标准化：使用峰值标准化批量处理音频，并保留原始目录结构。

工具输出通常写入你选择的目录，或写入 `outputs` 下对应的工具子目录。

### 设置

“设置”页目前提供界面外观预览，例如背景图、模糊、文字颜色和背景遮罩。当前这些设置是实时预览，还不是持久化配置。

## 命令行分离

命令行分离流程要求 `inputs` 下按一层文件夹分组：

```text
inputs/
  SingerA/
    song-a.wav
    song-b.mp3
  SingerB/
    take-001.flac
```

每个一级子文件夹会被视为一个独立分组。源文件不会被修改，程序会先把它们复制或转换为稳定编号的 WAV，再运行模型链。

常用命令：

```bat
run.bat
run.bat --dry-run
run.bat --preprocess-only
run.bat --download-models-only
run.bat --skip-model-download
```

你也可以指定配置文件：

```bat
run.bat --config config.py
```

## 输出位置

项目常用目录：

```text
inputs/      放入待处理音频
outputs/     当前运行中的输出，以及切分和工具输出
archives/    分离流程完成后的归档
models/      分离模型缓存
user_data/   GUI 预设和 GUI 生成的配置
img/         GUI 图标和背景图
```

一次分离归档中通常会包含：

- `<group>-inputs1`：预处理后的编号 WAV。
- `<group>-outputs<step>-<label>`：每一步模型的原始输出。
- `<group>-inputs<next>`：传递给下一步的目标声部。
- `<group>-end`：该分组最终保留的 WAV。
- `<group>-rename-map.md`：原始文件名和编号文件名的对应表。
- `manifest.json`：本次运行的记录。
- `run-YYYYmmdd-HHMMSS.log`：本次运行的日志。

## 配置模型链

命令行默认读取 `config.py`。最常修改的是 `MODEL_PIPELINE`：

```python
MODEL_PIPELINE = [
    {
        "label": "vocals",
        "model_filename": "mel_band_roformer_kim_ft3_unwa.ckpt",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "vocal"],
        "pitch_shift": 0,
    },
]
```

字段含义：

- `label`：这一步的名称，会用于输出文件夹和文件名。
- `model_filename`：要加载或下载的模型文件名。
- `keep_stem`：保留并传递给下一步的目标声部。
- `stem_aliases`：模型输出中可能出现的声部别名。
- `pitch_shift`：该步骤的音高偏移。

常用全局参数也在 `config.py` 中：

```python
MODEL_BATCH_SIZE = 16
MODEL_OVERLAP = 2
MODEL_SEGMENT_SIZE = 256
MODEL_OVERRIDE_SEGMENT_SIZE = False
```

更完整的配置说明见 [documents/configuration.md](documents/configuration.md)。

## 注意事项

- 第一次安装和第一次使用部分模型时需要联网。
- CUDA 版 PyTorch 会优先安装；如果失败，安装脚本会尝试回退到可用依赖。
- RMVPE 音高分析第一次使用时会下载 `rmvpe.onnx`。如果网络不可用，可以先使用 Praat 方案。
- 分离流程会按配置清理或复用 `outputs`，重要结果请以 `archives` 中的归档为准。

## 开发文档

面向二次开发的文档在 [documents/README.md](documents/README.md)。其中包含架构、环境、GUI、分离、切分、工具和配置说明。
