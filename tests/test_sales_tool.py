"""sales_tool.py のテスト

テスト用のデータはすべて架空のもので、pytest が用意する一時フォルダ（tmp_path）に作る。
そのため、input フォルダや output フォルダには影響しない。
"""

from datetime import date

import pandas as pd
import pytest

import sales_tool

COLUMNS = ["日付", "店舗名", "商品名", "カテゴリ", "単価", "数量", "金額"]


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

    df = sales_tool.load_all(sales_tool.find_input_files(tmp_path))

    assert len(df) == 3
    assert list(df.index) == [0, 1, 2]  # 行番号が振り直されている


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


# --- 出力 -----------------------------------------------------------------

def test_ファイル名に期間が入る(sales):
    assert sales_tool.make_report_name(sales) == "売上集計_2026-09_2026-10.xlsx"

    one_month = sales[sales["日付"].dt.month == 9]
    assert sales_tool.make_report_name(one_month) == "売上集計_2026-09.xlsx"


def test_write_report_は4つのシートを出力する(sales, tmp_path):
    path = tmp_path / "out" / "report.xlsx"  # out フォルダはまだ存在しない

    sales_tool.write_report(sales, path)

    sheets = pd.read_excel(path, sheet_name=None)
    assert list(sheets) == ["店舗別", "カテゴリ別", "月別", "全データ"]
    assert len(sheets["全データ"]) == 4


# --- サンプルデータを使った全体の確認 -----------------------------------------

def test_サンプルデータの集計結果が手計算と一致する():
    df = sales_tool.load_all(sales_tool.find_input_files(sales_tool.INPUT_DIR))

    assert len(df) == 64
    assert df["金額"].sum() == 99120

    store = sales_tool.summarize_by_store(df).set_index("店舗名")["売上合計"]
    assert store.to_dict() == {"西店": 36680, "南店": 33630, "東店": 28810}

    category = sales_tool.summarize_by_category(df).set_index("カテゴリ")["売上合計"]
    assert category.to_dict() == {"飲料": 40660, "日用品": 30520, "文具": 27940}

    month = sales_tool.summarize_by_month(df).set_index("年月")["売上合計"]
    assert month.to_dict() == {"2026-09": 49690, "2026-10": 49430}
