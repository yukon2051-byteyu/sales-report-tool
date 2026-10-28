"""売上データ集計ツール

店舗ごとの売上ファイル（CSV・Excel）を読み込み、集計するツールです。
現在はステップ5：店舗別・カテゴリ別・月別の集計を作る段階です。
"""

from pathlib import Path

import pandas as pd

# このファイルがあるフォルダを基準にする。
# こうすると、どのフォルダから実行しても input フォルダを正しく見つけられる。
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"

# 読み込みに対応しているファイルの種類（拡張子）
SUPPORTED_SUFFIXES = (".csv", ".xlsx")


def find_input_files(folder: Path) -> list[Path]:
    """フォルダの中から、読み込み対象のファイルを探して名前順に返す。"""
    files = []
    for path in folder.iterdir():
        # Excel でファイルを開いている間にできる一時ファイル（~$ で始まる）は対象外。
        # 中身が売上データではないため、読み込むとエラーになる。
        if path.name.startswith("~$"):
            continue
        if path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
    return sorted(files)


def load_file(path: Path) -> pd.DataFrame:
    """CSV または Excel ファイルを読み込み、表（DataFrame）として返す。"""
    if path.suffix.lower() == ".csv":
        # encoding="utf-8-sig" は、先頭に BOM（UTF-8 の目印）があってもなくても読める指定。
        df = pd.read_csv(path, encoding="utf-8-sig")
    else:
        df = pd.read_excel(path)

    # CSV の日付は「文字」、Excel の日付は「日付の値」として読み込まれる。
    # 形式がバラバラだと月別の集計ができないため、ここで日付の値にそろえる。
    df["日付"] = pd.to_datetime(df["日付"])
    return df


def load_all(files: list[Path]) -> pd.DataFrame:
    """複数のファイルを読み込み、1つの表にまとめて返す。"""
    frames = [load_file(path) for path in files]
    # ignore_index=True で、行番号（インデックス）を 0 から振り直す。
    # 指定しないと、ファイルごとの行番号（0〜11 など）が重複してしまう。
    return pd.concat(frames, ignore_index=True)


def _sum_by(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """key の列でグループに分け、金額と数量を合計する（各集計で共通の処理）。"""
    # groupby(key) で key ごとのグループに分け、各グループの金額と数量を合計する。
    # Excel のピボットテーブルで「行に key、値に金額と数量の合計」を指定するのと同じ処理。
    # as_index=False で、key を行番号ではなく通常の列として残す。
    summary = df.groupby(key, as_index=False)[["金額", "数量"]].sum()
    return summary.rename(columns={"金額": "売上合計", "数量": "数量合計"})


def summarize_by_store(df: pd.DataFrame) -> pd.DataFrame:
    """店舗ごとの売上合計・数量合計を計算し、売上の多い順に並べて返す。"""
    summary = _sum_by(df, "店舗名")
    return summary.sort_values("売上合計", ascending=False, ignore_index=True)


def summarize_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """カテゴリごとの売上合計・数量合計を計算し、売上の多い順に並べて返す。"""
    summary = _sum_by(df, "カテゴリ")
    return summary.sort_values("売上合計", ascending=False, ignore_index=True)


def summarize_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """月ごとの売上合計・数量合計を計算し、古い月から順に並べて返す。"""
    # 日付（例：2026-09-15）から「2026-09」という年月の文字を作り、新しい列として追加する。
    # assign は元の表を変えずに、列を足した新しい表を作る。
    with_month = df.assign(年月=df["日付"].dt.strftime("%Y-%m"))
    summary = _sum_by(with_month, "年月")
    return summary.sort_values("年月", ignore_index=True)


def main() -> None:
    files = find_input_files(INPUT_DIR)
    print(f"{len(files)} 件のファイルが見つかりました")
    for path in files:
        print(f"  - {path.name}")

    df = load_all(files)
    print(f"合計 {len(df)} 行 / 売上合計 {df['金額'].sum():,} 円")

    print("\n【店舗別】")
    print(summarize_by_store(df))
    print("\n【カテゴリ別】")
    print(summarize_by_category(df))
    print("\n【月別】")
    print(summarize_by_month(df))


# このファイルを直接実行したときだけ main() を動かす（テストから読み込んだときは動かさない）
if __name__ == "__main__":
    main()
