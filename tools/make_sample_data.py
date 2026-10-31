"""デモ用の架空の売上データを作るプログラム

2026年5月〜10月の6か月分、3店舗の売上データを input フォルダに作ります。
店舗名・商品名・数量はすべて架空のものです。

使い方:
    python tools/make_sample_data.py

乱数の種（SEED）を固定しているので、何度実行しても同じデータになります。
同じ名前のファイルがある場合は上書きします。
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

INPUT_DIR = Path(__file__).parent.parent / "input"
START = date(2026, 5, 1)
END = date(2026, 10, 31)
SEED = 2026

# 店舗名と、保存するファイル形式・店舗の規模（数量にかける倍率）
STORES = {
    "東店": {"suffix": ".csv", "scale": 0.8},
    "西店": {"suffix": ".csv", "scale": 1.2},
    "南店": {"suffix": ".xlsx", "scale": 1.0},
}

# 商品名: (カテゴリ, 単価, 1行あたりの数量の範囲)
PRODUCTS = {
    "ノートA": ("文具", 200, (2, 8)),
    "ボールペンB": ("文具", 120, (3, 12)),
    "ファイルC": ("文具", 150, (2, 8)),
    "お茶D": ("飲料", 130, (5, 15)),
    "コーヒーE": ("飲料", 150, (4, 12)),
    "ティッシュF": ("日用品", 250, (2, 6)),
    "洗剤G": ("日用品", 380, (1, 4)),
}


def make_rows(rng: random.Random, store: str, day: date) -> list[dict]:
    """1店舗・1日分の売上の行を作る（1〜3商品）。"""
    rows = []
    for product in rng.sample(list(PRODUCTS), k=rng.randint(1, 3)):
        category, price, (low, high) = PRODUCTS[product]
        quantity = rng.randint(low, high) * STORES[store]["scale"]
        # 実際の店舗にありそうな傾向を入れて、週ごと・月ごとの違いに意味を持たせる
        if day.weekday() >= 5:  # 土日は来店が多い
            quantity *= 1.5
        if category == "飲料" and day.month in (7, 8):  # 夏は飲料がよく売れる
            quantity *= 1.5
        quantity = max(1, round(quantity))
        rows.append({
            "日付": day,
            "店舗名": store,
            "商品名": product,
            "カテゴリ": category,
            "単価": price,
            "数量": quantity,
            "金額": price * quantity,  # 入力ミスのないデータにするため、必ず単価×数量にする
        })
    return rows


def main() -> None:
    rng = random.Random(SEED)
    rows = []
    day = START
    while day <= END:
        for store in STORES:
            rows += make_rows(rng, store, day)
        day += timedelta(days=1)
    df = pd.DataFrame(rows)

    INPUT_DIR.mkdir(exist_ok=True)
    # 実際の業務と同じように「月ごと・店舗ごと」に1ファイルずつ保存する
    month = pd.to_datetime(df["日付"]).dt.strftime("%Y-%m")
    for (ym, store), part in df.groupby([month, "店舗名"]):
        path = INPUT_DIR / f"{ym}_{store}{STORES[store]['suffix']}"
        if path.suffix == ".csv":
            # utf-8-sig は BOM 付きの UTF-8。Excel で開いても文字化けしない
            part.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            part.to_excel(path, index=False)
        print(f"{path.name}: {len(part)} 行")
    print(f"合計 {len(df)} 行を {INPUT_DIR} に保存しました")


if __name__ == "__main__":
    main()
