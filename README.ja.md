# AI Cover Tools

言語: [English](README.md) | [简体中文](README.zh-cn.md) | [日本語](README.ja.md)

AI Cover Tools は、ローカル環境で AI カバー用の音声素材を準備するための Windows 向けツールキットです。現在は学習前の音声処理を中心に、ボーカル抽出、学習用クリップへのスライス、音質チェック、総再生時間の集計、ピッチ分析、ピーク正規化を扱います。

現在利用できる機能:

- GUI: Separate、Slicer、Tools、Settings、About。
- Separate: `python-audio-separator` と設定済みのモデルチェーンを使い、伴奏、ハーモニー、リバーブ、ノイズの除去や、指定したステムの保持をバッチ処理します。
- Slicer: 無音区間と長さの設定に基づいて、音声を学習しやすいクリップへ分割します。
- Tools: スペクトログラムによる音質チェック、フォルダー内音声の総再生時間、ピッチレポート、ピーク正規化。

Train と Inference ページは GUI 上に用意されていますが、現時点ではプレースホルダーです。音声モデルの学習と最終的なカバー生成には、当面 Applio などの成熟した外部ツールの利用をおすすめします。

## クイックスタート

まずインストーラーを実行します:

```bat
run-install.bat
```

インストーラーはプロジェクト内のローカル環境 `env` を作成または再利用し、GUI、PyTorch、FFmpeg、音声分離、各種ツール用の依存関係をインストールします。通常利用ではシステム Python に依存しません。

インストール後、GUI を起動します:

```bat
run-gui.bat
```

コマンドラインの分離ワークフローだけを実行する場合:

```bat
run.bat
```

## 推奨フロー

1. 元曲やボーカル素材を `inputs` に入れます。
2. GUI の Separate ページで、よりクリーンなボーカルを抽出します。
3. Tools ページで音質、総再生時間、ピッチ範囲を確認し、必要に応じて正規化します。
4. Slicer ページで学習用の短いクリップを生成します。
5. 外部の音声モデルツールで学習と推論を行います。

## GUI 機能

### Separate

Separate ページでは、順序付きのモデル処理チェーンを編集して実行できます。複数のモデルモジュールを追加し、次の項目を設定できます:

- モデルファイル名
- 保持するステム
- ステムの別名
- pitch shift
- batch size、overlap、segment size などの共通設定

GUI は設定を `user_data/gui_separate_config.py` に書き出し、同じコマンドライン分離ワークフローを呼び出します。分離結果はまず `outputs` に書き込まれ、正常終了後に `archives/outputs-YYYYmmdd-HHMMSS` へアーカイブされます。

### Slicer

Slicer ページは入力フォルダーを再帰的にスキャンし、音声を学習向けのクリップへ分割します。デフォルト入力は `inputs`、デフォルト出力は `outputs`、デフォルト形式は `wav` です。

主な設定:

- Threshold: 無音判定のしきい値
- Minimum Length: 最短クリップ長
- Minimum Interval: 最短無音区間
- Hop Size: 解析ステップ幅
- Maximum Size Length: 保持する無音の最大長

入力形式は `wav`、`flac`、`mp3`、`m4a`、`ogg`、`opus`、`wma`、`aiff` などに対応しています。出力形式は `wav`、`flac`、`mp3` に対応しています。

### Tools

Tools ページには 4 つの独立したユーティリティがあります:

- 音質チェック: Spek 風のスペクトログラム画像を生成します。長い音声は 10 分ごとに分割されます。
- 総再生時間: フォルダー内の対応音声ファイルの総再生時間を集計します。
- ピッチレポート: Praat または RMVPE でデータセットのピッチ範囲と分布を分析します。
- 正規化: 元のフォルダー構造を保ったまま、音声を一括でピーク正規化します。

ツールの出力は、選択した出力先、または `outputs` 配下の各ツール用フォルダーに書き込まれます。

### Settings

Settings ページでは、背景画像、ぼかし、文字色、背景ティントなどの外観をライブプレビューできます。現在の実装ではプレビュー専用で、まだ永続化されません。

## コマンドライン分離

コマンドライン分離ワークフローでは、`inputs` の直下にグループ用フォルダーを置きます:

```text
inputs/
  SingerA/
    song-a.wav
    song-b.mp3
  SingerB/
    take-001.flac
```

各第 1 階層フォルダーが 1 つのグループとして扱われます。元ファイルは変更されません。ワークフローはまず素材を安定した番号付き WAV にコピーまたは変換し、その後で設定済みのモデルチェーンを実行します。

よく使うコマンド:

```bat
run.bat
run.bat --dry-run
run.bat --preprocess-only
run.bat --download-models-only
run.bat --skip-model-download
```

設定ファイルを指定することもできます:

```bat
run.bat --config config.py
```

## 出力先

よく使うプロジェクトフォルダー:

```text
inputs/      処理する音声素材
outputs/     実行中の出力、Slicer 出力、Tools 出力
archives/    分離ワークフロー完了後のアーカイブ
models/      分離モデルのキャッシュ
user_data/   GUI プリセットと GUI 生成設定
img/         GUI アイコンと背景画像
```

分離アーカイブには通常、次の内容が含まれます:

- `<group>-inputs1`: 前処理済みの番号付き WAV。
- `<group>-outputs<step>-<label>`: 各モデルステップの生出力。
- `<group>-inputs<next>`: 次のステップへ渡される対象ステム。
- `<group>-end`: そのグループの最終 WAV。
- `<group>-rename-map.md`: 元ファイル名と番号付きファイル名の対応表。
- `manifest.json`: 実行記録。
- `run-YYYYmmdd-HHMMSS.log`: 実行ログ。

## モデルチェーン設定

コマンドラインはデフォルトで `config.py` を読み込みます。もっともよく編集するのは `MODEL_PIPELINE` です:

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

各フィールドの意味:

- `label`: 出力フォルダー名やファイル名に使われるステップ名。
- `model_filename`: 読み込みまたはダウンロードするモデルファイル名。
- `keep_stem`: 保持して次のステップへ渡す対象ステム。
- `stem_aliases`: モデル出力に現れる可能性があるステムの別名。
- `pitch_shift`: このステップで使うピッチシフト。

共通のグローバル設定も `config.py` にあります:

```python
MODEL_BATCH_SIZE = 16
MODEL_OVERLAP = 2
MODEL_SEGMENT_SIZE = 256
MODEL_OVERRIDE_SEGMENT_SIZE = False
```

完全な設定リファレンスは [documents/configuration.md](documents/configuration.md) を参照してください。

## 注意事項

- 初回インストールや一部モデルの初回利用にはネットワーク接続が必要です。
- CUDA 版 PyTorch が優先してインストールされます。失敗した場合、インストーラーは利用可能な依存関係へフォールバックします。
- RMVPE ピッチ分析は初回利用時に `rmvpe.onnx` をダウンロードします。ネットワークが使えない場合は Praat を使用してください。
- 分離ワークフローは設定に応じて `outputs` を削除または再利用することがあります。完了済みの重要な結果は `archives` 内のアーカイブを基準にしてください。

## 開発者向けドキュメント

二次開発向けのドキュメントは [documents/README.md](documents/README.md) にあります。アーキテクチャ、環境、GUI、分離、Slicer、Tools、設定について説明しています。
