"""売上データ集計ツールの画面（Streamlit）

ブラウザ上でファイルを選び、集計結果の表示と Excel レポートのダウンロードができます。
集計の処理は sales_tool.py の関数をそのまま使います。

起動方法:
    streamlit run app.py
"""

import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import sales_tool

SOURCE_UPLOAD = "ファイルをアップロード"
SOURCE_SAMPLE = "サンプルデータで試す"


def save_uploads(uploaded_files: list, folder: Path) -> list[Path]:
    """アップロードされたファイルを一時フォルダに保存し、そのパスの一覧を返す。"""
    # sales_tool の関数はファイルのパスを受け取る作りなので、いったん保存してから渡す。
    # 元のファイル名で保存するので、警告メッセージにも元のファイル名が表示される。
    for file in uploaded_files:
        (folder / file.name).write_bytes(file.getvalue())
    # 保存したフォルダを、コマンド版と同じ方法で探す（Excel の一時ファイルの除外なども同じになる）
    return sales_tool.find_input_files(folder)


def make_report_bytes(df: pd.DataFrame, folder: Path) -> tuple[str, bytes]:
    """Excel レポートを一時フォルダに作り、ダウンロード用にファイル名と中身を返す。"""
    path = folder / sales_tool.make_report_name(df)
    sales_tool.write_report(df, path)
    return path.name, path.read_bytes()


def bar_chart(table: pd.DataFrame, key: str) -> alt.Chart:
    """集計表から売上合計の棒グラフを作る（並び順は表と同じ、縦軸は 0 から）。"""
    return (
        alt.Chart(table)
        .mark_bar()
        .encode(
            # sort=None で、表の並び順（売上の多い順・古い月から順）のまま表示する
            x=alt.X(f"{key}:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("売上合計:Q", title="売上合計（円）", axis=alt.Axis(format=","),
                    scale=alt.Scale(zero=True)),
            tooltip=[key, alt.Tooltip("売上合計:Q", format=","), alt.Tooltip("数量合計:Q", format=",")],
        )
    )


def show_summary(table: pd.DataFrame, key: str) -> None:
    """集計表と棒グラフを左右に並べて表示する。"""
    left, right = st.columns([2, 3])
    left.dataframe(table.style.format("{:,}", subset=["売上合計", "数量合計"]), hide_index=True)
    right.altair_chart(bar_chart(table, key), use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="売上データ集計ツール", layout="wide")
    st.title("売上データ集計ツール")
    st.caption("店舗ごとの売上ファイル（CSV・Excel）をまとめて読み込み、店舗別・カテゴリ別・月別に集計します。")

    source = st.radio("データの選び方", [SOURCE_UPLOAD, SOURCE_SAMPLE], horizontal=True)

    # with を抜けると一時フォルダは中身ごと自動で削除される
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)

        if source == SOURCE_UPLOAD:
            uploaded = st.file_uploader(
                "売上ファイルを選んでください（複数選択できます）",
                type=["csv", "xlsx"],
                accept_multiple_files=True,
            )
            if not uploaded:
                st.info("必要な列：日付・店舗名・商品名・カテゴリ・単価・数量・金額（CSV は UTF-8 で保存）")
                return
            upload_dir = work_dir / "upload"
            upload_dir.mkdir()
            files = save_uploads(uploaded, upload_dir)
        else:
            files = sales_tool.find_input_files(sales_tool.INPUT_DIR)
            st.caption("input フォルダの架空のサンプルデータ（2026年9月〜10月・3店舗）を使っています。")

        try:
            df, warnings = sales_tool.load_all(files)
        except sales_tool.InputDataError as e:
            st.error(f"エラー: {e}")
            return

        # --- 概要 ---
        col1, col2, col3 = st.columns(3)
        col1.metric("ファイル数", f"{len(files)} 件")
        col2.metric("データ行数", f"{len(df):,} 行")
        col3.metric("売上合計", f"{df['金額'].sum():,.0f} 円")

        if warnings:
            with st.expander(f"⚠ 確認が必要なデータが {len(warnings)} 件あります（集計には含めています）", expanded=True):
                for warning in warnings:
                    st.warning(warning)

        # --- 集計結果 ---
        tab_store, tab_category, tab_month, tab_all = st.tabs(["店舗別", "カテゴリ別", "月別", "全データ"])
        with tab_store:
            show_summary(sales_tool.summarize_by_store(df), "店舗名")
        with tab_category:
            show_summary(sales_tool.summarize_by_category(df), "カテゴリ")
        with tab_month:
            show_summary(sales_tool.summarize_by_month(df), "年月")
        with tab_all:
            st.dataframe(df, hide_index=True, column_config={"日付": st.column_config.DateColumn(format="YYYY/MM/DD")})

        # --- ダウンロード ---
        report_name, report_bytes = make_report_bytes(df, work_dir)
        st.download_button(
            "Excel レポートをダウンロード",
            data=report_bytes,
            file_name=report_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )


# Streamlit は画面を操作するたびにこのファイルを実行し直す（そのとき __name__ は "__main__" になる）。
# テストから import したときは画面の処理を動かさないよう、条件をつけて main() を呼ぶ。
if __name__ == "__main__":
    main()
