"""売上データ集計ツール

店舗ごとの売上ファイル（CSV・Excel）を読み込み、集計するツールです。
現在はステップ2：CSV ファイル1つを読み込んで表示する段階です。
"""

from pathlib import Path

import pandas as pd

# このファイルがあるフォルダを基準にする。
# こうすると、どのフォルダから実行しても input フォルダを正しく見つけられる。
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"


def load_csv(path: Path) -> pd.DataFrame:
    """CSV ファイルを読み込み、表（DataFrame）として返す。"""
    # encoding="utf-8-sig" は、先頭に BOM（UTF-8 の目印）があってもなくても読める指定。
    # BOM 付きの CSV を "utf-8" で読むと、1列目の列名に見えない記号が混ざることがあるため。
    return pd.read_csv(path, encoding="utf-8-sig")


def main() -> None:
    path = INPUT_DIR / "2026-09_東店.csv"
    df = load_csv(path)

    print(f"読み込んだファイル: {path.name}")
    print(f"行数: {len(df)} 行")
    print(df)


# このファイルを直接実行したときだけ main() を動かす（テストから読み込んだときは動かさない）
if __name__ == "__main__":
    main()
