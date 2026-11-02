"""可追溯新聞搜尋看板。執行：streamlit run app.py。

人工審核欄位代表維護者登錄的審核紀錄，程式不會自動證明主張真實。
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))
LOG = logging.getLogger(__name__)
MAX_BYTES = 2_000_000
STATUSES = {"待驗證", "已有支持證據", "有爭議", "已更正"}


class FeedError(Exception):
    """可向使用者呈現的資料擷取錯誤。"""


def now_iso():
    return datetime.now(TZ).isoformat(timespec="seconds")


def https_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    try:
        p = urlsplit(value)
        return (p.scheme == "https" and bool(p.hostname) and not p.username
                and not p.password and p.port in (None, 443))
    except ValueError:
        return False


def official_election_url(value):
    if not https_url(value):
        return False
    host = urlsplit(value).hostname.lower()
    return host == "cec.gov.tw" or host.endswith(".cec.gov.tw")


def text_required(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 不得空白")


def iso_date(value):
    if not isinstance(value, str):
        raise ValueError("日期須為 YYYY-MM-DD")
    return date.fromisoformat(value)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("時間須為含時區的 ISO 8601 字串")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("時間必須包含時區，例如 +08:00")
    if result > datetime.now(TZ) + timedelta(minutes=5):
        raise ValueError("紀錄時間不得在未來")
    return result


def validate_evidence(evidence):
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("必須附至少一筆證據")
    for e in evidence:
        if not isinstance(e, dict) or not https_url(e.get("url")):
            raise ValueError("證據須有有效 HTTPS 網址")
        for f in ("publisher", "excerpt", "source_type", "origin_id"):
            text_required(e.get(f), f)
        if iso_date(e["published_on"]) > datetime.now(TZ).date():
            raise ValueError("證據發布日期不得在未來")
        timestamp(e["checked_at"])


def validate_data(data):
    """嚴格驗證設定；任一錯誤即停止呈現人工資料，避免靜默使用錯誤值。"""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("不支援的資料格式版本")
    cfg = data["election"]
    year = cfg["target_year"]
    if type(year) is not int or not 2000 <= year <= 2100:
        raise ValueError("目標選舉年度不合法")
    if cfg["status"] not in {"尚未設定", "已人工核對公告"}:
        raise ValueError("選區設定狀態不合法")
    if cfg["status"] == "已人工核對公告":
        for f in ("district_name", "reviewer", "announcement_title", "announcement_excerpt"):
            text_required(cfg.get(f), f)
        if not isinstance(cfg.get("areas"), list) or not cfg["areas"]:
            raise ValueError("選區行政區不得空白")
        for area in cfg["areas"]:
            text_required(area, "行政區")
        if not official_election_url(cfg.get("announcement_url")):
            raise ValueError("選區須引用中選會或所屬選委會 HTTPS 正式公告")
        if cfg.get("applicable_year") != year:
            raise ValueError("公告適用年度必須等於目標選舉年度")
        if iso_date(cfg["announced_on"]) > datetime.now(TZ).date():
            raise ValueError("公告日期不得在未來")
        timestamp(cfg["reviewed_at"])

    for key in ("claims", "resource_targets", "progress", "maintenance"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"{key} 必須是陣列")
    ids = set()
    for claim in data["claims"]:
        text_required(claim.get("id"), "主張編號")
        if claim["id"] in ids:
            raise ValueError("主張編號重複")
        ids.add(claim["id"])
        text_required(claim.get("category"), "主張分類")
        text_required(claim.get("text"), "主張內容")
        if claim.get("status") not in STATUSES:
            raise ValueError("主張查核狀態不合法")
        # 待驗證主張只留在本地資料，畫面不公開其敘述。
        if claim["status"] != "待驗證":
            validate_evidence(claim.get("evidence"))
            text_required(claim.get("reviewer"), "審核者")
            text_required(claim.get("review_note"), "審核結論")
            timestamp(claim["reviewed_at"])

    for target in data["resource_targets"]:
        for f in ("issue", "approver", "decision_ref", "period"):
            text_required(target.get(f), f)
        value = target["allocation_percent"]
        if type(value) not in (int, float) or not 0 <= value <= 100:
            raise ValueError("配置目標須介於 0 與 100")
        if iso_date(target["approved_on"]) > datetime.now(TZ).date():
            raise ValueError("核定日期不得在未來")
    if data["resource_targets"]:
        if len({t["period"] for t in data["resource_targets"]}) != 1:
            raise ValueError("資源配置表必須使用同一統計期間")
        if abs(sum(t["allocation_percent"] for t in data["resource_targets"]) - 100) > 0.01:
            raise ValueError("資源配置目標合計須為 100%")

    for group in data["progress"]:
        text_required(group.get("name"), "工作名稱")
        text_required(group.get("register_ref"), "完整工作清冊依據")
        text_required(group.get("maintainer"), "清冊維護者")
        start, end = iso_date(group["period_start"]), iso_date(group["period_end"])
        if start > end:
            raise ValueError("統計期間起訖顛倒")
        updated = timestamp(group["updated_at"])
        if not isinstance(group.get("tasks"), list):
            raise ValueError("工作紀錄須為陣列")
        task_ids = set()
        for task in group["tasks"]:
            text_required(task.get("id"), "工作編號")
            if task["id"] in task_ids:
                raise ValueError("同一清冊的工作編號重複")
            task_ids.add(task["id"])
            text_required(task.get("record_ref"), "工作紀錄依據")
            if not start <= iso_date(task["registered_on"]) <= end:
                raise ValueError("工作登錄日期不在統計期間內")
            if iso_date(task["registered_on"]) > updated.astimezone(TZ).date():
                raise ValueError("工作登錄日期晚於清冊更新時間")
            if task.get("status") not in {"未完成", "已完成"}:
                raise ValueError("工作狀態不合法")
            if task["status"] == "已完成":
                completed = iso_date(task["completed_on"])
                if not iso_date(task["registered_on"]) <= completed <= end:
                    raise ValueError("完成日期不在合法期間內")
                if completed > updated.astimezone(TZ).date():
                    raise ValueError("完成日期晚於更新時間")
                text_required(task.get("completion_ref"), "完成佐證")
    for row in data["maintenance"]:
        for f in ("actor", "action", "reference"):
            text_required(row.get(f), f)
        timestamp(row["at"])
    return data


def load_data(path):
    raw = path.read_bytes()
    data = validate_data(json.loads(raw.decode("utf-8-sig")))
    return data, hashlib.sha256(raw).hexdigest()


def parse_feed(content, days, current=None):
    current = current or datetime.now(TZ)
    if len(content) > MAX_BYTES:
        raise FeedError("RSS 超過大小限制")
    # 不接受 DTD、實體宣告及非 UTF-8/XML 網頁，限制不可信 XML 的輸入。
    try:
        xml = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise FeedError("RSS 編碼不受支援") from exc
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise FeedError("RSS 包含不允許的 XML 宣告")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise FeedError("RSS 格式錯誤") from exc
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise FeedError("回應不是預期的 RSS 新聞資料")
    articles, seen = [], set()
    skipped = {"invalid": 0, "duplicate": 0, "outside_period": 0}
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        # 此端點只接受 Google News 搜尋紀錄連結；不自動連線至任意原站。
        if (not title or not https_url(link)
                or urlsplit(link).hostname.lower() != "news.google.com"):
            skipped["invalid"] += 1
            continue
        if (guid and guid in seen) or link in seen:
            skipped["duplicate"] += 1
            continue
        raw_date = (item.findtext("pubDate") or "").strip()
        published = None
        try:
            published = parsedate_to_datetime(raw_date)
            if published.tzinfo is None:
                published = None
            else:
                published = published.astimezone(TZ)
        except (ValueError, TypeError, OverflowError):
            pass
        if published and (published < current - timedelta(days=days)
                          or published > current + timedelta(minutes=5)):
            skipped["outside_period"] += 1
            continue
        source = item.find("source")
        source_url = source.get("url", "") if source is not None else ""
        articles.append({
            "title": title[:1000], "link": link, "guid": guid,
            "published_at": published.isoformat() if published else None,
            "publisher": ((source.text or "").strip() if source is not None else "") or "來源未提供",
            "publisher_url": source_url if https_url(source_url) else "",
            "verification": "內容尚未獨立查證",
        })
        seen.add(link)
        if guid:
            seen.add(guid)
    articles.sort(key=lambda a: a["published_at"] or "", reverse=True)
    return {"articles": articles, "fetched_at": current.isoformat(), "skipped": skipped}


@st.cache_data(ttl=1800, max_entries=64, show_spinner=False)
def fetch_news(keyword, days):
    """僅快取成功回應；例外向上傳遞，不轉成可快取的空結果。"""
    retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET"], respect_retry_after_header=False)
    try:
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=retries))
            with session.get(
                "https://news.google.com/rss/search",
                params={"q": keyword, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
                timeout=(5, 15), stream=True, allow_redirects=False,
            ) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise FeedError("新聞服務回傳非預期狀態")
                chunks, size = [], 0
                for chunk in response.iter_content(16384):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise FeedError("RSS 超過大小限制")
                    chunks.append(chunk)
                return parse_feed(b"".join(chunks), days)
    except requests.Timeout as exc:
        raise FeedError("新聞服務連線或讀取逾時") from exc
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "未知"
        raise FeedError(f"新聞服務 HTTP 錯誤：{code}") from exc
    except requests.RequestException as exc:
        raise FeedError("新聞服務連線失敗，請稍後再試") from exc


def progress_counts(group):
    tasks = group["tasks"]
    return sum(t["status"] == "已完成" for t in tasks), len(tasks)


def show_election(cfg):
    st.caption(f"目標選舉年度：{cfg['target_year']}")
    if cfg["status"] != "已人工核對公告":
        st.warning("選區尚未設定：須依目標年度正式公告完成核對，暫不顯示選區與候選人資格。")
        return
    st.write(f"選區：{cfg['district_name']}；行政區：{'、'.join(cfg['areas'])}")
    st.link_button("選委會正式公告", cfg["announcement_url"])
    st.text(f"公告：{cfg['announcement_title']}｜發布：{cfg['announced_on']}")
    st.text(f"公告摘錄：{cfg['announcement_excerpt']}")
    st.caption(f"人工核對者：{cfg['reviewer']}｜核對時間：{cfg['reviewed_at']}")


def main():
    st.set_page_config(page_title="新聞搜尋與資料查核看板", page_icon="📰", layout="wide")
    st.title("新聞搜尋與資料查核看板")
    st.warning("新聞搜尋結果／內容尚未獨立查證。取得新聞紀錄與查證內容真實性為不同流程。")
    st.caption("搜尋可能包含同名人物、轉載或不相關內容；媒體名稱、報導數量均不代表查證通過。")
    try:
        data, digest = load_data(BASE / "data.json")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        LOG.exception("Local dataset validation failed")
        st.error(f"資料設定載入失敗，已停止呈現：{exc}")
        st.stop()
    show_election(data["election"])
    st.sidebar.header("新聞搜尋設定")
    keyword = st.sidebar.text_input("監測關鍵字（不代表資格或身分已核實）", "蔡佩呈 泰山", max_chars=200).strip()
    days = st.sidebar.selectbox("已知發布日期的顯示期間（天）", [7, 30, 90], index=1)
    limit = st.sidebar.slider("顯示筆數", 5, 50, 10)
    refresh = st.sidebar.button("重新整理新聞數據")
    tab_news, tab_claims, tab_records, tab_audit = st.tabs(
        ["新聞搜尋結果", "主張與證據", "資源目標與工作紀錄", "來源與維護紀錄"])
    with tab_news:
        if not keyword:
            st.info("請輸入搜尋關鍵字。")
        else:
            key = (keyword, days)
            if refresh:
                fetch_news.clear(keyword, days)  # 必須在下一次讀取前清除此查詢。
            history = st.session_state.setdefault("last_success", {})
            try:
                with st.spinner("讀取新聞搜尋紀錄…"):
                    result = fetch_news(keyword, days)
                history[key] = result
                # 限制每個工作階段保存的查詢數量。
                while len(history) > 20:
                    del history[next(iter(history))]
            except FeedError as exc:
                LOG.warning("RSS retrieval failed: %s", exc)
                st.error(str(exc))
                result = history.get(key)
                if result is not None:
                    st.warning("以下為此查詢最後一次成功擷取的舊資料；本次更新失敗。")
                else:
                    st.info("此查詢尚無成功擷取紀錄。")
            if result is not None:
                st.caption(f"成功擷取時間（臺北時間）：{result['fetched_at']}｜快取最長 30 分鐘；不會自動定時更新")
                st.caption("依可解析發布日期篩選與排序；日期未知者保留並置後，無法確認是否在指定期間內。")
                articles = result["articles"]
                if not articles:
                    st.info("本次查詢未取得符合顯示條件的紀錄；不代表事件不存在。")
                else:
                    st.write(f"取得 {len(articles)} 筆紀錄，顯示前 {min(limit, len(articles))} 筆。")
                for number, article in enumerate(articles[:limit], start=1):
                    # RSS 標題是不可信文字，避免當成 Markdown 連結或格式解讀。
                    with st.expander(f"搜尋紀錄 {number}｜查看標題與來源"):
                        st.text(article["title"])
                        st.text(f"來源（RSS 提供，未驗證）：{article['publisher']}")
                        st.text(f"發布時間：{article['published_at'] or '未知／格式無法解析'}")
                        st.text("查核狀態：內容尚未獨立查證")
                        st.link_button("開啟 Google News 搜尋紀錄連結", article["link"])
                        if article["publisher_url"]:
                            st.link_button("RSS 所列來源網站（非原文驗證）", article["publisher_url"])
                        st.caption(f"RSS 紀錄識別碼：{article['guid'] or '未提供'}")
                st.caption(f"本次排除紀錄：{result['skipped']}。僅按連結／識別碼去重，尚未判定轉載關係。")
                st.download_button("匯出此次搜尋紀錄 JSON", json.dumps(result, ensure_ascii=False, indent=2),
                                   file_name="news_search.json", mime="application/json")
    with tab_claims:
        st.subheader("人工登錄主張與佐證")
        pending = sum(c["status"] == "待驗證" for c in data["claims"])
        st.info(f"待驗證主張 {pending} 筆；其敘述暫停公開。缺乏來源的舊版人物背景與 SWOT 已移除。")
        visible = [c for c in data["claims"] if c["status"] != "待驗證"]
        if not visible:
            st.info("尚無完成審核登錄的主張。")
        for claim in visible:
            with st.expander(f"{claim['id']}｜{claim['category']}｜{claim['status']}"):
                st.text(claim["text"])
                st.text(f"人工審核：{claim['reviewer']}｜{claim['reviewed_at']}")
                st.text(f"審核結論：{claim['review_note']}")
                for ev in claim["evidence"]:
                    st.text(f"來源：{ev['publisher']}｜類型：{ev['source_type']}｜原始來源編號：{ev['origin_id']}")
                    st.text(f"發布：{ev['published_on']}｜檢查：{ev['checked_at']}")
                    st.text(f"證據摘錄：{ev['excerpt']}")
                    st.link_button("檢視證據", ev["url"])
        st.caption("審核狀態由資料維護者登錄；程式僅檢查欄位完整性，不會自動核實證據、獨立性或真實性。")
    with tab_records:
        st.subheader("團隊議題資源配置目標")
        st.caption("僅表示經核定的內部配置目標，不代表民意、支持度或調查結果。")
        if data["resource_targets"]:
            st.dataframe(data["resource_targets"], hide_index=True)
        else:
            st.info("尚無資料：未提供核定人、日期與配置依據，故不顯示百分比。")
        st.subheader("實際工作紀錄統計")
        if not data["progress"]:
            st.info("尚無資料：未提供實際工作清冊及完成佐證。")
        for group in data["progress"]:
            done, total = progress_counts(group)
            st.write(group["name"])
            st.text(f"統計期間：{group['period_start']} 至 {group['period_end']}｜更新：{group['updated_at']}")
            st.text(f"維護者：{group['maintainer']}｜清冊依據：{group['register_ref']}")
            if total:
                st.progress(done / total, text=f"完成件數／總件數：{done}／{total}")
                st.dataframe(group["tasks"], hide_index=True)
            else:
                st.info("尚無資料：清冊中沒有工作紀錄。")
        st.caption("分母僅為登錄清冊的工作件數；不等於全區人口、里長總數或完整案件母體。")
    with tab_audit:
        st.subheader("來源與查核流程")
        st.write("搜尋發現 → 原始證據核對 → 人工審核 → 發布與更正追蹤。")
        st.write("選區以目標年度選委會正式公告為準；工程依主管機關文件；人口依官方統計；人物經歷與實績依可追溯紀錄。")
        st.write("官方或媒體網域只用於識別來源，不能直接證明個別主張。相同稿件轉載不算獨立佐證。")
        st.link_button("中選會（來源入口，非特定年度公告）", "https://www.cec.gov.tw/")
        st.link_button("新北捷運工程局（來源入口，非個別進度證據）", "https://www.dorts.ntpc.gov.tw/")
        st.link_button("台灣事實查核中心（輔助查核入口）", "https://tfc-taiwan.org.tw/")
        st.subheader("資料維護紀錄")
        if data["maintenance"]:
            st.dataframe(data["maintenance"], hide_index=True)
        else:
            st.info("尚無資料維護紀錄。")
        st.text(f"目前 data.json 的 SHA-256：{digest}")
        st.caption("雜湊用於比對版本，不是資料真實性或審核身分的認證。維護紀錄為本地人工登錄，非不可竄改稽核系統。")


if __name__ == "__main__":
    main()
