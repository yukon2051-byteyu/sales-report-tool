"""app.py（Streamlit の画面）のテスト

AppTest は、ブラウザを開かずに画面を動かし、表示内容を確かめる Streamlit の仕組み。
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
import sales_tool

APP_PATH = str(Path(__file__).parent.parent / "app.py")
HEADER = "日付,店舗名,商品名,カテゴリ,単価,数量,金額\n"


def run_with_sample(monkeypatch, folder: Path) -> AppTest:
    """「サンプルデータで試す」の読み込み先を folder に差し替えて、画面を動かす。"""
    monkeypatch.setattr(sales_tool, "INPUT_DIR", folder)
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    return at.radio[0].set_value("サンプルデータで試す").run()


def test_初期表示はエラーなくアップロードを案内する():
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()

    assert not at.exception
    assert "必要な列" in at.info[0].value


def test_サンプルデータを選ぶと集計結果が表示される(monkeypatch):
    at = run_with_sample(monkeypatch, sales_tool.INPUT_DIR)

    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics == {"ファイル数": "6 件", "データ行数": "64 行", "売上合計": "99,120 円"}
    assert [t.label for t in at.tabs] == ["店舗別", "カテゴリ別", "月別", "週別", "全データ"]
    assert len(at.warning) == 0  # サンプルデータには入力ミスがない
    assert len(at.get("download_button")) == 1


def test_入力ミスがあると画面に警告を表示する(monkeypatch, tmp_path):
    (tmp_path / "test.csv").write_text(
        HEADER + "2026-09-01,A店,ペン,文具,100,2,200\n2026-09-02,A店,ペン,文具,100,2,999\n",
        encoding="utf-8",
    )

    at = run_with_sample(monkeypatch, tmp_path)

    assert not at.exception
    assert [w.value for w in at.warning] == [
        "test.csv 3行目: 金額が単価×数量と一致しません（金額 999 / 単価×数量 200）"
    ]
    assert len(at.get("download_button")) == 1  # 警告があっても集計結果は出す


def test_読み込めないファイルがあると画面にエラーを表示する(monkeypatch, tmp_path):
    (tmp_path / "test.csv").write_text("日付,金額\n2026-09-01,200\n", encoding="utf-8")

    at = run_with_sample(monkeypatch, tmp_path)

    assert not at.exception  # 想定外のエラーで画面が落ちていない
    assert "必要な列がありません" in at.error[0].value
    assert len(at.get("download_button")) == 0


class FakeUpload:
    """アップロードされたファイルの代わり（name と getvalue() だけを持つ）。"""

    def __init__(self, name: str):
        self.name = name

    def getvalue(self) -> bytes:
        return b"x"


def test_save_uploads_は元のファイル名で保存する(tmp_path):
    uploads = [FakeUpload("東店.csv"), FakeUpload("南店.xlsx"), FakeUpload("メモ.txt")]

    files = app.save_uploads(uploads, tmp_path)

    assert [p.name for p in files] == ["南店.xlsx", "東店.csv"]  # 対象外の .txt は除かれる
