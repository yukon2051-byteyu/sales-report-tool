"""weekly_comment.py のテスト（データはすべて架空）"""

from datetime import date

import pandas as pd
import pytest

import weekly_comment

COLUMNS = ["日付", "店舗名", "商品名", "カテゴリ", "単価", "数量", "金額"]


def make_sales(rows: list[list]) -> pd.DataFrame:
    """テスト用の売上データ（読み込み後と同じ形）を作る。"""
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["日付"] = pd.to_datetime(df["日付"])
    return df


def test_今週が途中までなら前週も同じ曜日までで比べる():
    df = make_sales([
        ["2026-09-21", "A店", "ペン", "文具", 100, 10, 1000],   # 前週の月曜：比べる対象
        ["2026-09-25", "A店", "ペン", "文具", 100, 50, 5000],   # 前週の金曜：今週は水曜までなので対象外
        ["2026-09-28", "A店", "お茶", "飲料", 100, 8, 800],     # 今週の月曜
        ["2026-09-30", "B店", "ペン", "文具", 100, 7, 700],     # 今週の水曜（データの最終日）
    ])

    result = weekly_comment.summarize_latest_week(df)

    assert result.start == date(2026, 9, 28)
    assert result.last_day == date(2026, 9, 30)
    assert result.days == 3
    assert result.sales == 1500
    assert result.prev_sales == 1000  # 9/25（金）の 5,000円は含めない
    assert result.change_rate == pytest.approx(0.5)  # (1500 - 1000) / 1000 = 50%増
    assert (result.top_store, result.top_store_sales) == ("A店", 800)
    assert (result.top_category, result.top_category_sales) == ("飲料", 800)


def test_今週が日曜まであれば1週間分どうしで比べる():
    df = make_sales([
        ["2026-09-21", "A店", "ペン", "文具", 100, 10, 1000],   # 前週の月曜
        ["2026-09-27", "A店", "ペン", "文具", 100, 10, 1000],   # 前週の日曜
        ["2026-09-28", "A店", "ペン", "文具", 100, 10, 1000],   # 今週の月曜
        ["2026-10-04", "A店", "ペン", "文具", 100, 5, 500],     # 今週の日曜
    ])

    result = weekly_comment.summarize_latest_week(df)

    assert result.days == 7
    assert result.sales == 1500
    assert result.prev_sales == 2000
    assert result.change_rate == pytest.approx(-0.25)  # 25%減


def test_前週のデータがなければ前週比は出さない():
    df = make_sales([
        ["2026-09-28", "A店", "ペン", "文具", 100, 10, 1000],
    ])

    result = weekly_comment.summarize_latest_week(df)

    assert result.sales == 1000
    assert result.prev_sales is None
    assert result.change_rate is None
