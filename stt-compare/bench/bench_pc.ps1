<#
.SYNOPSIS
  Atlas STT bench for the owner's PC (Windows 11, Ryzen 7 9700X, RX 9070 XT). About 5 minutes of running after the
  one-off downloads (~3 GB of models and Python packages). Installs nothing system-wide.

.DESCRIPTION
  Everything goes into .\work\ next to this script: a portable uv (Python manager), private Python 3.12 environments, the
  models, and the results. Delete .\work\ afterwards to remove all of it. Nothing talks to Home Assistant, Ollama's
  settings or any device; it only reads the synthetic test clips in ..\testset\audio and writes ..\pc-results\<stamp>\.

  Stages (all on 60 synthetic clips of 2-5 s speech, the same audio as the sandbox results):
    1. CPU, through the real Wyoming server (wyoming-faster-whisper 3.8.1), 8 threads:
         Parakeet TDT 0.6B v2 int8 (sherpa-onnx)        <- the recommendation
         Qwen3-ASR 0.6B int4 with the house-name prompt  <- the runner-up
         faster-whisper large-v3-turbo int8              <- the Whisper reference
    2. GPU via DirectML (onnxruntime-directml): Parakeet TDT 0.6B v2 (fp32, ~2.5 GB download) - skip with -SkipDirectML
    3. GPU via Vulkan: whisper.cpp large-v3-turbo q5_0, only if you pass -WhisperCppDir pointing at a Vulkan build's
       bin folder (whisper.cpp publishes no official Windows Vulkan binaries). Flash attention is off (-nfa): it crashes
       whisper-server on RX 9070 XT / Windows (whisper.cpp issue #3806).
    4. Scores everything and writes summary.md. Send that folder back (or let PC Steward commit it to the branch).

.EXAMPLE
  cd stt-compare\bench ; powershell -ExecutionPolicy Bypass -File .\bench_pc.ps1
  # with Ollama's model loaded and generating at the same time (GPU/CPU contention check):
  powershell -ExecutionPolicy Bypass -File .\bench_pc.ps1 -LlmLoad -OllamaModel gemma4:12b
#>
param(
  [switch]$SkipDirectML,
  [string]$WhisperCppDir = "",
  [switch]$LlmLoad,
  [string]$OllamaModel = "",
  [int]$Threads = 8
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $here "work"
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$out = Join-Path (Join-Path $here "..\pc-results") $stamp
New-Item -ItemType Directory -Force -Path $work, $out | Out-Null
$env:UV_CACHE_DIR = Join-Path $work "uv-cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $work "python"
$env:HF_HOME = Join-Path $work "hf"
$env:PYTHONUTF8 = "1"
if ($OllamaModel) { $env:OLLAMA_MODEL = $OllamaModel }

# 1. portable uv (https://github.com/astral-sh/uv, MIT/Apache-2.0)
$uv = Join-Path $work "uv\uv.exe"
if (-not (Test-Path $uv)) {
  Write-Host "Downloading uv ..."
  $zip = Join-Path $work "uv.zip"
  Invoke-WebRequest -Uri "https://github.com/astral-sh/uv/releases/download/0.9.5/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip
  Expand-Archive -Force $zip (Join-Path $work "uv")
}

function New-Env($name, [string[]]$packages) {
  $venv = Join-Path $work $name
  if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    & $uv venv --python 3.12 $venv | Out-Host
    & $uv pip install --python (Join-Path $venv "Scripts\python.exe") @packages | Out-Host
  }
  return (Join-Path $venv "Scripts\python.exe")
}

$common = @("soundfile==0.13.1", "psutil==7.1.0", "numpy<2.4", "jiwer==4.0.0", "regex", "huggingface_hub<1")
$llm = @(); if ($LlmLoad) { $llm = @("--llm-load") }
$driver = Join-Path $here "pc_bench.py"

# 2. CPU stage (the Wyoming server, as Home Assistant would use it)
$py = New-Env "env-wyoming" (@("wyoming-faster-whisper[sherpa,qwen3-asr]==3.8.1", "av==16.1.0") + $common)
Write-Host "== CPU stage (Parakeet, Qwen3-ASR, faster-whisper turbo) ..."
& $py $driver cpu $out --threads $Threads @llm

# 3. DirectML stage
if (-not $SkipDirectML) {
  $pyd = New-Env "env-directml" (@("onnx-asr[hub]==0.12.0", "onnxruntime-directml==1.23.0") + $common)
  Write-Host "== DirectML stage (Parakeet on the RX 9070 XT) ..."
  try { & $pyd $driver directml $out @llm } catch { Write-Warning "DirectML stage failed: $_" }
}

# 4. Vulkan stage
if ($WhisperCppDir) {
  Write-Host "== Vulkan stage (whisper.cpp turbo on the RX 9070 XT) ..."
  try { & $py $driver vulkan $out --whisper-cpp $WhisperCppDir --threads $Threads @llm } catch { Write-Warning "Vulkan stage failed: $_" }
} else {
  Write-Host "== Vulkan stage skipped (no -WhisperCppDir). GPU Whisper speed stays NO DATA from this PC."
}

# 5. score
& $py $driver score $out
Write-Host "Done. Results: $out\summary.md"
