"""売上データ集計ツール

店舗ごとの売上ファイル（CSV・Excel）を読み込み、店舗別・カテゴリ別・月別に集計して
Excel ファイルに出力するツールです。

使い方:
    python sales_tool.py
    python sales_tool.py --input 入力フォルダ --output 出力フォルダ
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

# このファイルがあるフォルダを基準にする。
# こうすると、どのフォルダから実行しても input フォルダを正しく見つけられる。
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

# 読み込みに対応しているファイルの種類（拡張子）
SUPPORTED_SUFFIXES = (".csv", ".xlsx")

# 売上ファイルに必要な列
REQUIRED_COLUMNS = ["日付", "店舗名", "商品名", "カテゴリ", "単価", "数量", "金額"]
NUMBER_COLUMNS = ["単価", "数量", "金額"]


class InputDataError(Exception):
    """入力データの問題で処理を続けられないときのエラー（使う人に原因を伝える）。"""


def find_input_files(folder: Path) -> list[Path]:
    """フォルダの中から、読み込み対象のファイルを探して名前順に返す。"""
    if not folder.is_dir():
        raise InputDataError(f"入力フォルダが見つかりません: {folder}")

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
    try:
        if path.suffix.lower() == ".csv":
            # encoding="utf-8-sig" は、先頭に BOM（UTF-8 の目印）があってもなくても読める指定。
            df = pd.read_csv(path, encoding="utf-8-sig")
        else:
            df = pd.read_excel(path)
    except UnicodeDecodeError as e:
        # Excel で「CSV（コンマ区切り）」として保存すると Shift_JIS になり、ここに来ることが多い
        raise InputDataError(
            f"{path.name}: 文字コードが UTF-8 ではありません。"
            "Excel で「CSV UTF-8（コンマ区切り）」を選んで保存し直してください。"
        ) from e
    except Exception as e:
        # 壊れたファイルなど、その他の理由で読み込めなかった場合
        raise InputDataError(f"{path.name}: ファイルを読み込めませんでした（{e}）") from e

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise InputDataError(f"{path.name}: 必要な列がありません: {', '.join(missing)}")

    # CSV の日付は「文字」、Excel の日付は「日付の値」として読み込まれる。
    # 形式がバラバラだと月別の集計ができないため、ここで日付の値にそろえる。
    # errors="coerce" で、日付として読めない値は止めずに「空（NaT）」にし、後のチェックで知らせる。
    df["日付"] = pd.to_datetime(df["日付"], errors="coerce")
    # 数値の列も同じく、数値として読めない値（「１００」「-」など）は空（NaN）にする
    for col in NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[REQUIRED_COLUMNS]


def check_data(df: pd.DataFrame, source: str) -> list[str]:
    """入力ミスが疑われる行を探し、「ファイル名 行番号: 内容」の形の警告一覧を返す。"""
    warnings = []
    for index, row in df.iterrows():
        # Excel で見たときの行番号（1行目は見出しなので、データは2行目から始まる）
        line = f"{source} {index + 2}行目"

        blank = [col for col in REQUIRED_COLUMNS if pd.isna(row[col])]
        if blank:
            warnings.append(f"{line}: 空欄または読み取れない値があります（{', '.join(blank)}）")
            continue  # 値が欠けていると下のチェックは正しく判定できないため、次の行へ

        negative = [col for col in NUMBER_COLUMNS if row[col] < 0]
        if negative:
            warnings.append(f"{line}: マイナスの値があります（{', '.join(negative)}）")
        if row["単価"] * row["数量"] != row["金額"]:
            warnings.append(
                f"{line}: 金額が単価×数量と一致しません"
                f"（金額 {row['金額']:,.0f} / 単価×数量 {row['単価'] * row['数量']:,.0f}）"
            )
    return warnings


def load_all(files: list[Path]) -> tuple[pd.DataFrame, list[str]]:
    """複数のファイルを読み込んで1つの表にまとめ、データチェックの警告一覧と一緒に返す。"""
    frames = []
    warnings = []
    for path in files:
        df = load_file(path)
        # 行番号を正しく伝えるため、結合する前にファイルごとにチェックする
        warnings += check_data(df, path.name)
        frames.append(df)
    # ignore_index=True で、行番号（インデックス）を 0 から振り直す。
    # 指定しないと、ファイルごとの行番号（0〜11 など）が重複してしまう。
    return pd.concat(frames, ignore_index=True), warnings


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


def summarize_by_week(df: pd.DataFrame) -> pd.DataFrame:
    """週ごと（月曜始まり）の売上合計・数量合計を計算し、古い週から順に並べて返す。"""
    # 各日付から「その週の月曜日」を求める。day_of_week は月曜=0〜日曜=6 なので、
    # その日数だけ日付を戻すと月曜日になる（例：2026-10-01(木) − 3日 = 2026-09-28(月)）。
    # normalize で時刻を 0:00 にそろえ、同じ日の売上が別の週として分かれないようにする。
    dates = df["日付"].dt.normalize()
    monday = dates - pd.to_timedelta(dates.dt.day_of_week, unit="D")
    summary = _sum_by(df.assign(週の月曜=monday), "週の月曜")
    summary = summary.sort_values("週の月曜", ignore_index=True)

    # 表やグラフで期間がひと目で分かるよう、「2026-09-28〜2026-10-04」の形の文字にする
    sunday = summary["週の月曜"] + pd.Timedelta(days=6)
    label = summary["週の月曜"].dt.strftime("%Y-%m-%d") + "〜" + sunday.dt.strftime("%Y-%m-%d")
    summary.insert(0, "週", label)  # 先頭（A列）に置く。グラフは A列を項目名に使うため
    return summary.drop(columns="週の月曜")


def make_report_name(df: pd.DataFrame) -> str:
    """データの期間から、出力ファイル名（例：売上集計_2026-09_2026-10.xlsx）を作る。"""
    months = df["日付"].dt.strftime("%Y-%m")
    first, last = months.min(), months.max()
    # 1か月分だけなら「2026-09」、複数月なら「2026-09_2026-10」とする。
    period = first if first == last else f"{first}_{last}"
    return f"売上集計_{period}.xlsx"


def _format_sheet(ws: Worksheet) -> None:
    """Excel のシートを見やすく整える（見出しの装飾・数値の書式・列幅）。"""
    header_font = Font(bold=True)
    header_fill = PatternFill(fill_type="solid", fgColor="DDEBF7")

    for column in ws.columns:
        header = column[0]
        header.font = header_font
        header.fill = header_fill
        ws.column_dimensions[header.column_letter].width = 14

        # 2行目以降（データ部分）の表示形式を、列の内容に合わせて設定する
        for cell in column[1:]:
            if header.value == "日付":
                cell.number_format = "yyyy/mm/dd"
            elif isinstance(cell.value, (int, float)):
                cell.number_format = "#,##0"  # 3桁区切り（例：49,690）

    # 見出し行を固定し、下にスクロールしても見出しが見えるようにする
    ws.freeze_panes = "A2"


def _add_bar_chart(ws: Worksheet, title: str) -> None:
    """集計シート（A列：項目名、B列：売上合計）の右側に、売上合計の棒グラフを追加する。"""
    chart = BarChart()
    chart.title = title
    chart.y_axis.title = "売上合計（円）"
    chart.y_axis.numFmt = "#,##0"
    # 縦軸を 0 から始める。自動のままだと値が近いとき（例：49,690 と 49,430）に
    # 途中から始まり、わずかな差が大きな差に見えてしまうため。
    chart.y_axis.scaling.min = 0
    chart.legend = None  # 系列が「売上合計」1つだけなので凡例は不要
    # 最近の Excel では、これを指定しないと軸（目盛りや項目名）が表示されないことがある
    chart.x_axis.delete = False
    chart.y_axis.delete = False

    last_row = ws.max_row
    # グラフにする範囲：B列（売上合計）の値と、A列（店舗名など）の項目名
    values = Reference(ws, min_col=2, min_row=1, max_row=last_row)  # 1行目の見出しを系列名に使う
    labels = Reference(ws, min_col=1, min_row=2, max_row=last_row)
    chart.add_data(values, titles_from_data=True)
    chart.set_categories(labels)

    chart.width, chart.height = 16, 8  # 大きさ（cm）
    ws.add_chart(chart, "E2")


def write_report(df: pd.DataFrame, path: Path) -> None:
    """集計結果と全データを、シートを分けて1つの Excel ファイルに書き出す。"""
    # シート名と、そのシートに書く表の組み合わせ
    sheets = {
        "店舗別": summarize_by_store(df),
        "カテゴリ別": summarize_by_category(df),
        "月別": summarize_by_month(df),
        "全データ": df,
    }

    path.parent.mkdir(parents=True, exist_ok=True)  # output フォルダがなければ作る
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, table in sheets.items():
            # index=False で、pandas の行番号（0, 1, 2…）を Excel に書かないようにする
            table.to_excel(writer, sheet_name=sheet_name, index=False)
            _format_sheet(writer.sheets[sheet_name])
            # 集計シートにはグラフを付ける（全データは明細なので付けない）
            if sheet_name != "全データ":
                _add_bar_chart(writer.sheets[sheet_name], f"{sheet_name}の売上合計")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """コマンドで指定された入力フォルダ・出力フォルダを受け取る（省略時は input / output）。"""
    parser = argparse.ArgumentParser(description="店舗ごとの売上ファイルを集計して Excel に出力します。")
    parser.add_argument("--input", type=Path, default=INPUT_DIR, help="売上ファイルを置いたフォルダ")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="集計結果を保存するフォルダ")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """ツール全体の処理。成功したら 0、エラーで止まったら 1 を返す。"""
    args = parse_args(argv)
    try:
        files = find_input_files(args.input)
        if not files:
            raise InputDataError(f"読み込むファイル（.csv / .xlsx）がありません: {args.input}")
        print(f"{len(files)} 件のファイルが見つかりました")
        for path in files:
            print(f"  - {path.name}")

        df, warnings = load_all(files)
        print(f"合計 {len(df)} 行 / 売上合計 {df['金額'].sum():,.0f} 円")

        if warnings:
            print(f"\n【注意】確認が必要なデータが {len(warnings)} 件あります（集計には含めています）")
            for warning in warnings:
                print(f"  - {warning}")

        print("\n【店舗別】")
        print(summarize_by_store(df))
        print("\n【カテゴリ別】")
        print(summarize_by_category(df))
        print("\n【月別】")
        print(summarize_by_month(df))

    except InputDataError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    output_path = args.output / make_report_name(df)
    try:
        write_report(df, output_path)
    except PermissionError:
        # 同じ名前の出力ファイルを Excel で開いたままにしていると、上書き保存できない
        print(
            f"エラー: {output_path.name} に保存できません。"
            "Excel でこのファイルを開いている場合は、閉じてからもう一度実行してください。",
            file=sys.stderr,
        )
        return 1

    print(f"\n集計結果を保存しました: {output_path}")
    return 0


# このファイルを直接実行したときだけ main() を動かす（テストから読み込んだときは動かさない）。
# sys.exit に main() の戻り値を渡し、成功（0）か失敗（1）かを呼び出し元に伝える。
if __name__ == "__main__":
    sys.exit(main())
