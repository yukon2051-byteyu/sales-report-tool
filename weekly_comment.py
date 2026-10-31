"""「今週の売上の特徴」コメントを作るための部品

売上データから、いちばん新しい週（今週）と前週の数字をまとめます。
数字の計算はすべて Python で行い、文章にするのはその後の処理に任せます。
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class WeekSummary:
    """今週の売上を、前週と比べてまとめた結果。"""

    start: date  # 今週の月曜日
    last_day: date  # 今週のデータがある最後の日
    days: int  # 今週の日数（月曜日から last_day まで。7 なら1週間すべて）
    sales: int  # 今週の売上合計
    prev_sales: int | None  # 前週の同じ期間の売上合計（前週のデータがなければ None）
    change_rate: float | None  # 前週比の増減率（例：0.1 は 10%増、-0.2 は 20%減）
    top_store: str  # 今週の売上がいちばん多い店舗
    top_store_sales: int
    top_category: str  # 今週の売上がいちばん多いカテゴリ
    top_category_sales: int


def _top(df: pd.DataFrame, key: str) -> tuple[str, int]:
    """key ごとの売上合計がいちばん多い項目と、その売上合計を返す。"""
    totals = df.groupby(key)["金額"].sum()
    return totals.idxmax(), int(totals.max())


def summarize_latest_week(df: pd.DataFrame) -> WeekSummary:
    """データの中でいちばん新しい週（月曜始まり）を今週として、前週と比べた数字をまとめる。"""
    # 時刻を 0:00 にそろえた日付で比べる（週別集計と同じ考え方）
    dates = df["日付"].dt.normalize()
    last_day = dates.max()
    start = last_day - pd.Timedelta(days=last_day.day_of_week)  # 今週の月曜日
    this_week = df[(dates >= start) & (dates <= last_day)]

    # 前週は「今週と同じ曜日まで」に絞る。
    # 今週が途中まで（例：月〜土）しかないときに前週の7日分と比べると、
    # 実際より減ったように見えてしまうため、同じ日数どうしで比べる。
    one_week = pd.Timedelta(days=7)
    prev_week = df[(dates >= start - one_week) & (dates <= last_day - one_week)]

    sales = int(this_week["金額"].sum())
    if prev_week.empty:
        prev_sales, change_rate = None, None
    else:
        prev_sales = int(prev_week["金額"].sum())
        # 前週の売上が 0 円のときは、割り算ができないので増減率を出さない
        change_rate = (sales - prev_sales) / prev_sales if prev_sales else None

    top_store, top_store_sales = _top(this_week, "店舗名")
    top_category, top_category_sales = _top(this_week, "カテゴリ")

    return WeekSummary(
        start=start.date(),
        last_day=last_day.date(),
        days=(last_day - start).days + 1,
        sales=sales,
        prev_sales=prev_sales,
        change_rate=change_rate,
        top_store=top_store,
        top_store_sales=top_store_sales,
        top_category=top_category,
        top_category_sales=top_category_sales,
    )
