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


# --- 文章にする ---------------------------------------------------------------

def make_summary(**changes) -> weekly_comment.WeekSummary:
    """テスト用の WeekSummary を作る（今週は 10/26（月）〜10/31（土）の6日分）。changes で一部を変えられる。"""
    values = dict(
        start=date(2026, 10, 26), last_day=date(2026, 10, 31), days=6,
        sales=40260, prev_sales=28850, change_rate=(40260 - 28850) / 28850,
        top_store="西店", top_store_sales=15250, top_category="文具", top_category_sales=14980,
    )
    values.update(changes)
    return weekly_comment.WeekSummary(**values)


def test_増えた週の文章():
    assert weekly_comment.make_comment(make_summary()) == (
        "今週（10/26（月）〜10/31（土）の6日分）の売上は 40,260円でした。\n"
        "前週の同じ期間（10/19（月）〜10/24（土））の 28,850円と比べて、39.5%増えました。\n"
        "店舗別では西店（15,250円）、カテゴリ別では文具（14,980円）の売上が最も多くなりました。"
    )


def test_1週間分そろった週で減った場合の文章():
    summary = make_summary(last_day=date(2026, 11, 1), days=7, sales=30000, prev_sales=40000, change_rate=-0.25)

    lines = weekly_comment.make_comment(summary).split("\n")

    assert lines[0] == "今週（10/26（月）〜11/1（日））の売上は 30,000円でした。"  # 「○日分」は付けない
    assert lines[1] == "前週の同じ期間（10/19（月）〜10/25（日））の 40,000円と比べて、25.0%減りました。"


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        (dict(prev_sales=None, change_rate=None), "前週のデータがないため、前週との比較はしていません。"),
        (dict(prev_sales=0, change_rate=None), "前週の同じ期間（10/19（月）〜10/24（土））は売上がなかったため、増減率は出していません。"),
        (dict(sales=28850, change_rate=0.0), "前週の同じ期間（10/19（月）〜10/24（土））の 28,850円と同じでした。"),
    ],
)
def test_前週と比べられない場合や変化がない場合の文章(changes, expected):
    lines = weekly_comment.make_comment(make_summary(**changes)).split("\n")

    assert lines[1] == expected
