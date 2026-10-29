@echo off
chcp 65001 > nul
rem ↑ 日本語を正しく表示するため、画面の文字コードを UTF-8 に切り替える

rem 売上データ集計ツールを、ダブルクリックだけで実行するためのファイル

rem このファイルがあるフォルダに移動する（どこから起動しても同じ動きにするため）
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [エラー] 仮想環境 .venv が見つかりません。
    echo README の「インストール」の手順を先に行ってください。
    echo.
    pause
    exit /b 1
)

rem %* は、このファイルに渡された指定（--input など）をそのままツールに渡すという意味
".venv\Scripts\python.exe" sales_tool.py %*

rem ツールはエラーのとき終了コード 1 を返すので、それで成功・失敗を見分ける
if errorlevel 1 (
    echo.
    echo 集計できませんでした。上のメッセージを確認してください。
) else (
    echo.
    echo 集計が完了しました。
    rem 保存先を指定していないときだけ、標準の output フォルダを開く
    if "%~1"=="" explorer output
)

echo.
pause
