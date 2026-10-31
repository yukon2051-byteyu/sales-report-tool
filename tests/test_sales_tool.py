"""sales_tool.py のテスト

テスト用のデータはすべて架空のもので、pytest が用意する一時フォルダ（tmp_path）に作る。
そのため、input フォルダや output フォルダには影響しない。
全体の確認には、手で検算できる小さな固定データ（tests/data、2か月×3店舗・64行）を使う。
"""

import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import sales_tool

COLUMNS = ["日付", "店舗名", "商品名", "カテゴリ", "単価", "数量", "金額"]

# テスト専用の固定データ。input/ のデモ用データを入れ替えても、テストの結果が変わらないようにする
TEST_DATA_DIR = Path(__file__).parent / "data"


def make_sales(rows: list[list]) -> pd.DataFrame:
    """テスト用の売上データ（読み込み後と同じ形）を作る。"""
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["日付"] = pd.to_datetime(df["日付"])
    return df


@pytest.fixture
def sales() -> pd.DataFrame:
    """2店舗・2か月分の小さな架空データ。"""
    return make_sales([
        ["2026-09-01", "A店", "ペン", "文具", 100, 2, 200],
        ["2026-09-15", "B店", "お茶", "飲料", 150, 4, 600],
        ["2026-10-01", "A店", "お茶", "飲料", 150, 1, 150],
        ["2026-10-20", "A店", "ノート", "文具", 200, 3, 600],
    ])


# --- ファイルを探す・読み込む ---------------------------------------------

def test_find_input_files_は対象のファイルだけを返す(tmp_path):
    # c.CSV は「拡張子が大文字でも対象になるか」を確かめるためのファイル
    for name in ["b.csv", "a.xlsx", "c.CSV", "~$a.xlsx", "memo.txt"]:
        (tmp_path / name).write_text("x")

    names = [p.name for p in sales_tool.find_input_files(tmp_path)]

    # 一時ファイル（~$）と対象外の拡張子（.txt）は除かれ、名前順に並ぶ
    assert names == ["a.xlsx", "b.csv", "c.CSV"]


def test_load_file_はCSVの日付を日付の値にそろえる(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text(
        "日付,店舗名,商品名,カテゴリ,単価,数量,金額\n2026-09-01,A店,ペン,文具,100,2,200\n",
        encoding="utf-8-sig",
    )

    df = sales_tool.load_file(path)

    assert list(df.columns) == COLUMNS
    assert pd.api.types.is_datetime64_any_dtype(df["日付"])


def test_load_file_はExcelを読み込める(tmp_path):
    path = tmp_path / "test.xlsx"
    pd.DataFrame([[date(2026, 9, 1), "A店", "ペン", "文具", 100, 2, 200]], columns=COLUMNS).to_excel(
        path, index=False
    )

    df = sales_tool.load_file(path)

    assert len(df) == 1
    assert pd.api.types.is_datetime64_any_dtype(df["日付"])


def test_load_all_は複数ファイルを結合する(tmp_path):
    header = "日付,店舗名,商品名,カテゴリ,単価,数量,金額\n"
    (tmp_path / "1.csv").write_text(header + "2026-09-01,A店,ペン,文具,100,2,200\n", encoding="utf-8")
    (tmp_path / "2.csv").write_text(
        header + "2026-09-02,B店,ペン,文具,100,1,100\n2026-09-03,B店,ペン,文具,100,3,300\n",
        encoding="utf-8",
    )

    df, warnings = sales_tool.load_all(sales_tool.find_input_files(tmp_path))

    assert len(df) == 3
    assert list(df.index) == [0, 1, 2]  # 行番号が振り直されている
    assert warnings == []


# --- エラー処理 -------------------------------------------------------------

def test_入力フォルダがないとエラー(tmp_path):
    with pytest.raises(sales_tool.InputDataError, match="入力フォルダが見つかりません"):
        sales_tool.find_input_files(tmp_path / "存在しないフォルダ")


def test_必要な列がないとエラー(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text("日付,店舗名,金額\n2026-09-01,A店,200\n", encoding="utf-8")

    with pytest.raises(sales_tool.InputDataError, match="必要な列がありません: 商品名, カテゴリ, 単価, 数量"):
        sales_tool.load_file(path)


def test_ShiftJISのCSVは保存し直すよう案内する(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text(
        "日付,店舗名,商品名,カテゴリ,単価,数量,金額\n2026-09-01,A店,ペン,文具,100,2,200\n",
        encoding="shift_jis",
    )

    with pytest.raises(sales_tool.InputDataError, match="CSV UTF-8"):
        sales_tool.load_file(path)


def test_ファイルが1つもないと終了コード1(tmp_path, capsys):
    assert sales_tool.main(["--input", str(tmp_path)]) == 1
    assert "読み込むファイル" in capsys.readouterr().err


# --- データのチェック ---------------------------------------------------------

def test_check_data_は問題のある行をファイル名と行番号つきで知らせる(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text(
        "日付,店舗名,商品名,カテゴリ,単価,数量,金額\n"
        "2026-09-01,A店,ペン,文具,100,2,200\n"   # 2行目：問題なし
        "2026-09-02,A店,ペン,文具,100,-1,-100\n"  # 3行目：マイナス
        "2026-09-03,A店,ペン,文具,100,2,300\n"   # 4行目：金額の不一致
        "9月4日,A店,ペン,文具,100,,200\n",        # 5行目：日付が読めない・数量が空欄
        encoding="utf-8",
    )

    warnings = sales_tool.check_data(sales_tool.load_file(path), "test.csv")

    assert warnings == [
        "test.csv 3行目: マイナスの値があります（数量, 金額）",
        "test.csv 4行目: 金額が単価×数量と一致しません（金額 300 / 単価×数量 200）",
        "test.csv 5行目: 空欄または読み取れない値があります（日付, 数量）",
    ]


# --- 集計 -----------------------------------------------------------------

def test_店舗別の集計(sales):
    result = sales_tool.summarize_by_store(sales)

    # 売上の多い順：A店 200+150+600=950、B店 600
    assert result["店舗名"].tolist() == ["A店", "B店"]
    assert result["売上合計"].tolist() == [950, 600]
    assert result["数量合計"].tolist() == [6, 4]


def test_カテゴリ別の集計(sales):
    result = sales_tool.summarize_by_category(sales)

    # 飲料 600+150=750、文具 200+600=800 → 文具が先
    assert result["カテゴリ"].tolist() == ["文具", "飲料"]
    assert result["売上合計"].tolist() == [800, 750]


def test_月別の集計(sales):
    result = sales_tool.summarize_by_month(sales)

    assert result["年月"].tolist() == ["2026-09", "2026-10"]
    assert result["売上合計"].tolist() == [800, 750]


def test_週別の集計は月曜始まりで月をまたいでも同じ週にまとめる():
    df = make_sales([
        ["2026-09-27", "A店", "ペン", "文具", 100, 1, 100],  # 日曜日：前の週の最終日
        ["2026-09-28", "A店", "ペン", "文具", 100, 2, 200],  # 月曜日：新しい週の始まり
        ["2026-09-30", "B店", "ペン", "文具", 100, 3, 300],  # 水曜日（9月）
        ["2026-10-01", "B店", "ペン", "文具", 100, 4, 400],  # 木曜日（10月）：月をまたいでも同じ週
    ])

    result = sales_tool.summarize_by_week(df)

    assert list(result.columns) == ["週", "売上合計", "数量合計"]
    assert result["週"].tolist() == ["2026-09-21〜2026-09-27", "2026-09-28〜2026-10-04"]
    assert result["売上合計"].tolist() == [100, 900]  # 200+300+400=900
    assert result["数量合計"].tolist() == [1, 9]


# --- 出力 -----------------------------------------------------------------

def test_ファイル名に期間が入る(sales):
    assert sales_tool.make_report_name(sales) == "売上集計_2026-09_2026-10.xlsx"

    one_month = sales[sales["日付"].dt.month == 9]
    assert sales_tool.make_report_name(one_month) == "売上集計_2026-09.xlsx"


def test_write_report_は5つのシートを出力する(sales, tmp_path):
    path = tmp_path / "out" / "report.xlsx"  # out フォルダはまだ存在しない

    sales_tool.write_report(sales, path)

    sheets = pd.read_excel(path, sheet_name=None)
    assert list(sheets) == ["店舗別", "カテゴリ別", "月別", "週別", "全データ"]
    assert len(sheets["全データ"]) == 4


def test_write_report_は集計シートにグラフを入れる(sales, tmp_path):
    path = tmp_path / "report.xlsx"

    sales_tool.write_report(sales, path)

    # xlsx は複数のファイルを zip でまとめた形式で、グラフは xl/charts/ の中に保存される。
    # （openpyxl は読み込み時にグラフを読まないため、zip の中身を直接確かめる）
    with zipfile.ZipFile(path) as z:
        charts = sorted(n for n in z.namelist() if n.startswith("xl/charts/chart"))
        titles = [z.read(n).decode("utf-8") for n in charts]
    assert len(charts) == 4
    assert any("店舗別の売上合計" in t for t in titles)
    assert any("月別の売上合計" in t for t in titles)
    assert any("週別の売上合計" in t for t in titles)


# --- 固定データを使った全体の確認 ---------------------------------------------

def test_main_は指定した出力フォルダに保存して終了コード0(tmp_path):
    assert sales_tool.main(["--input", str(TEST_DATA_DIR), "--output", str(tmp_path)]) == 0
    assert (tmp_path / "売上集計_2026-09_2026-10.xlsx").exists()


def test_固定データの集計結果が手計算と一致する():
    df, warnings = sales_tool.load_all(sales_tool.find_input_files(TEST_DATA_DIR))

    assert warnings == []  # 固定データには入力ミスがない
    assert len(df) == 64
    assert df["金額"].sum() == 99120

    store = sales_tool.summarize_by_store(df).set_index("店舗名")["売上合計"]
    assert store.to_dict() == {"西店": 36680, "南店": 33630, "東店": 28810}

    category = sales_tool.summarize_by_category(df).set_index("カテゴリ")["売上合計"]
    assert category.to_dict() == {"飲料": 40660, "日用品": 30520, "文具": 27940}

    month = sales_tool.summarize_by_month(df).set_index("年月")["売上合計"]
    assert month.to_dict() == {"2026-09": 49690, "2026-10": 49430}

    # 週別：9/1(火)〜10/31(土) のデータは、8/31(月)始まりから 10/26(月)始まりまでの9週に分かれる。
    # どの週にも入らない行や、二重に数える行がないことを、合計の一致で確かめる。
    week = sales_tool.summarize_by_week(df)
    assert len(week) == 9
    assert week["週"].iloc[0] == "2026-08-31〜2026-09-06"
    assert week["売上合計"].sum() == 99120
