import json
import sys
import time
import requests
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
from datetime import datetime
from etf_theme_keywords import get_etf_keywords
from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID         = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET     = os.getenv("NAVER_CLIENT_SECRET")
TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_SHEET_WEBAPP_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
ANTHROPIC_API_KEY       = os.getenv("ANTHROPIC_API_KEY")
# etf_holdings.json 읽기
with open("etf_holdings.json", "r", encoding="utf-8") as f:
    etf_holdings = json.load(f)

app = QApplication(sys.argv)
kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
loop = QEventLoop()

INCLUDE_KEYWORDS = [
    "반도체", "AI", "인공지능", "소버린AI", "온디바이스",
    "2차전지", "배터리", "전고체",
    "방산", "K방산", "우주항공", "UAM",
    "원자력", "원전", "SMR",
    "전력", "신재생에너지", "수소", "태양광", "ESS", "친환경",
    "조선", "바이오", "헬스케어", "의료",
    "로봇", "휴머노이드",
    "소프트웨어", "IT", "인터넷", "플랫폼",
    "5G", "네트워크", "메타버스",
    "자동차", "전기차", "화장품", "뷰티",
    "엔터", "콘텐츠", "게임", "미디어",
    "K-POP", "KPOP", "웹툰",
    "삼성그룹", "현대차그룹", "LG그룹",
    "한화그룹", "포스코그룹", "두산그룹",
    "카카오그룹", "5대그룹",
    "철강", "건설", "기계장비",
    "에너지화학", "여행레저", "푸드",
    "골프", "북미공급망",
]

EXCLUDE_AFTER = [
    "미국", "차이나", "글로벌", "일본", "유럽",
    "중국", "한중", "SOLACTIVE", "합성",
    "레버리지", "인버스", "채권혼합", "커버드콜", "타겟",
    "S&P", "나스닥", "NYSE", "필라델피아",
    "채권", "리츠", "대만", "ESG", "MZ소비",
    "K200", "아시아AI", "밸류알파", "그룹채권",
    "삼성그룹밸류", "200 건설", "200 철강",
    "200 에너지", "200 IT", "200 헬스케어", "200IT",
    "코스닥150IT", "코스닥150바이오", "코리아플랫폼",
    "코스피대형주", "코스피TR", "코스피중형주",
    "코리아TOP10", "Top10동일가중",
    "V&S셀렉트", "중형주저변동", "가치주", "우량주",
    "주도업종", "성장주", "블루칩",
    "우량업종", "경기방어", "우선주", "지주회사",
    "BBIG", "KODEX 코스피", "PLUS 코스피",
    "TIGER 코스피", "RISE 코스피", "ACE 코스피",
]

def is_valid_etf(name):
    if not any(kw in name for kw in INCLUDE_KEYWORDS):
        return False
    if any(kw in name for kw in EXCLUDE_AFTER):
        return False
    return True

def calc_supply_score(foreign_days, inst_days):
    if foreign_days > 10:    f_score = 25
    elif foreign_days == 10: f_score = 20
    elif foreign_days == 7:  f_score = 16
    elif foreign_days == 5:  f_score = 12
    elif foreign_days == 3:  f_score = 8
    elif foreign_days == 2:  f_score = 5
    elif foreign_days == 1:  f_score = 3
    else:                    f_score = 0

    if inst_days > 10:    g_score = 20
    elif inst_days == 10: g_score = 16
    elif inst_days == 7:  g_score = 13
    elif inst_days == 5:  g_score = 10
    elif inst_days == 3:  g_score = 6
    elif inst_days == 2:  g_score = 4
    elif inst_days == 1:  g_score = 2
    else:                 g_score = 0

    bonus = 5 if foreign_days >= 1 and inst_days >= 1 else 0
    return min(f_score + g_score + bonus, 50)

# ════════════════════════════════════════
# Gemini 뉴스 감성 분석
# ════════════════════════════════════════
def analyze_news_with_claude(etf_name: str, news_texts: list) -> tuple:
    if not news_texts:
        return 0, "뉴스 없음"

    news_str = "\n".join(news_texts[:5])
    prompt = f"""한국 주식 ETF 뉴스 분석 전문가입니다.

ETF명: {etf_name}
뉴스 목록:
{news_str}

위 뉴스들이 '{etf_name}' ETF에 미치는 영향을 분석해주세요.
반드시 아래 JSON 형식으로만 답하세요. 다른 텍스트 절대 금지:
{{"score": 숫자, "reason": "한줄이유"}}

score 기준:
+20 ~ +25: 매우 긍정 (대형 수주, 정책 수혜, 강한 호재)
+10 ~ +19: 긍정 (계약, 성장, 수출 증가)
+1  ~ +9:  약간 긍정
0:          중립
-1  ~ -9:  약간 부정
-10 ~ -19: 부정 (실적 악화, 규제)
-20 ~ -25: 매우 부정 (대형 악재, 수사, 파산)"""

    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json"
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages":   [{"role": "user", "content": prompt}]
            },
            timeout=15
        )
        text = res.json()["content"][0]["text"]
        text = text.strip().replace("```json","").replace("```","").strip()
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]
        data = json.loads(text)
        return int(data["score"]), data.get("reason", "")
    except Exception as e:
        print(f"    Claude 오류: {e}")
        return 0, "분석실패"
# ════════════════════════════════════════
# 뉴스 수집 + Gemini 분석
# ════════════════════════════════════════
def fetch_etf_news(etf_name: str) -> tuple:
    keywords = get_etf_keywords(etf_name)
    if not keywords:
        return 0, []

    query = keywords[0]
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
            },
            params={"query": query, "display": 20, "sort": "date"},
            timeout=10
        )
        items = res.json().get("items", [])
    except:
        return 0, []

    headlines = []
    for item in items[:10]:
        title = item.get("title", "")
        desc  = item.get("description", "")
        for tag in ["<b>","</b>","&amp;","&lt;","&gt;"]:
            title = title.replace(tag, "")
            desc  = desc.replace(tag, "")
        headlines.append(title + " " + desc)

    score, reason = analyze_news_with_claude(etf_name, headlines)
    print(f"    → Claude: {score:+d}pt ({reason})")
    return score, [h.split(" ")[0] for h in headlines[:3]]

# ════════════════════════════════════════
# 텔레그램 + 구글시트 + picks
# ════════════════════════════════════════
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or "여기에" in TELEGRAM_BOT_TOKEN:
        print(message)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID,
                  "text": message, "parse_mode": "HTML"},
            timeout=10)
        print("텔레그램 전송 완료")
    except Exception as e:
        print(f"텔레그램 실패: {e}")

def save_to_sheet(picks):
    if not GOOGLE_SHEET_WEBAPP_URL or "여기에" in GOOGLE_SHEET_WEBAPP_URL:
        return
    try:
        res = requests.post(GOOGLE_SHEET_WEBAPP_URL, json={
            "type": "etf_pick",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data": picks
        }, timeout=15)
        print(f"구글시트 저장: {res.status_code}")
    except Exception as e:
        print(f"구글시트 실패: {e}")

def save_picks(final_picks):
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open("picks.json", "r", encoding="utf-8") as f:
            all_picks = json.load(f)
    except:
        all_picks = []
    all_picks = [p for p in all_picks if not p.get("date","").startswith(today)]
    for p in final_picks:
        all_picks.append({
            "date":        today,
            "time":        datetime.now().strftime("%H:%M"),
            "corp_name":   p["name"],
            "stock_code":  p["code"],
            "final_score": p["total_score"],
            "buy_price":   0,
            "etf_name":    p["etf_name"],
        })
    all_picks = all_picks[-300:]
    with open("picks.json", "w", encoding="utf-8") as f:
        json.dump(all_picks, f, ensure_ascii=False, indent=2)
    print(f"picks.json 저장: {len(final_picks)}개")

def format_telegram(top5, top_etfs):
    now = datetime.now().strftime("%m/%d %H:%M")
    lines = [f"📊 <b>ETF 대장주 분석</b> ({now})\n"]
    lines.append("🔹 <b>선정 ETF</b>")
    for e in top_etfs[:3]:
        lines.append(
            f"  {e['name']} {e['change']:+.2f}% "
            f"수급:{e['supply_score']}pt "
            f"뉴스:{e.get('news_score',0):+d}pt"
        )
    lines.append("\n🎯 <b>최종 추천 종목</b>")
    for i, s in enumerate(top5, 1):
        lines.append(
            f"{i}. <b>{s['name']}</b> ({s['code']})\n"
            f"   등락:{s['change']:+.2f}% "
            f"수급:{s['etf_supply_score']}pt "
            f"뉴스:{s['news_score']:+d}pt "
            f"총점:{s['total_score']}pt\n"
            f"   [{s['etf_name']}]"
        )
    lines.append("\n⚠️ 장 후반 유지력 확인 후 최종 판단")
    return "\n".join(lines)

# ════════════════════════════════════════
# 키움 변수
# ════════════════════════════════════════
etf_list    = []
stock_list  = []
top5_etfs   = []
phase       = ["etf_supply"]
current_idx = [0]

def on_login(err_code):
    if err_code == 0:
        print("✅ 키움 로그인 성공")
        codes = kiwoom.dynamicCall("GetCodeListByMarket(QString)", "8")
        for code in codes.split(";"):
            if not code:
                continue
            name = kiwoom.dynamicCall("GetMasterCodeName(QString)", code)
            if is_valid_etf(name):
                etf_list.append({
                    "code":         code,
                    "name":         name,
                    "change":       0,
                    "foreign_days": 0,
                    "inst_days":    0,
                    "supply_score": 0,
                    "news_score":   0,
                    "headlines":    [],
                })
        print(f"ETF 목록: {len(etf_list)}개")
        print(f"\nPHASE 1: ETF 수급 수집 시작")
        fetch_next()

def fetch_next():
    today = datetime.now().strftime("%Y%m%d")

    # PHASE 1: ETF 수급 수집
    if phase[0] == "etf_supply":
        if current_idx[0] >= len(etf_list):
            supply_etfs = sorted(
                [e for e in etf_list if e["supply_score"] > 0],
                key=lambda x: x["supply_score"], reverse=True)
            print(f"\n수급 있는 ETF: {len(supply_etfs)}개")
            for e in supply_etfs[:10]:
                print(f"  {e['name']:35s} "
                      f"외:{e['foreign_days']}일 "
                      f"기:{e['inst_days']}일 "
                      f"수급:{e['supply_score']}pt")

            print(f"\nPHASE 2: ETF 뉴스 수집 + Claude 분석 시작")
            for e in supply_etfs:
                news_score, headlines = fetch_etf_news(e["name"])
                e["news_score"] = news_score
                e["headlines"]  = headlines
                print(f"  {e['name']:35s} 뉴스:{news_score:+d}pt")

            phase[0] = "etf_change"
            current_idx[0] = 0
            fetch_next()
            return

        etf = etf_list[current_idx[0]]
        kiwoom.dynamicCall("SetInputValue(QString, QString)", "일자", today)
        kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", etf["code"])
        kiwoom.dynamicCall("SetInputValue(QString, QString)", "금액수량구분", "1")
        kiwoom.dynamicCall("SetInputValue(QString, QString)", "매매구분", "0")
        kiwoom.dynamicCall("SetInputValue(QString, QString)", "단위구분", "1")
        kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)",
                          "ETF수급", "opt10060", 0, "0101")

    # PHASE 3: ETF 등락률 수집
    elif phase[0] == "etf_change":
        if current_idx[0] >= len(etf_list):
            qualified = [e for e in etf_list
                        if e["supply_score"] > 0 and e["change"] > 0]

            if not qualified:
                print("\n조건 충족 ETF 없음 → 상승률 기준으로만 진행")
                qualified = [e for e in etf_list if e["change"] > 0]

            for e in qualified:
                e["etf_total"] = (
                    e["supply_score"] +
                    e["news_score"] +
                    min(e["change"] * 0.5, 10)
                )

            top5 = sorted(qualified,
                         key=lambda x: x["etf_total"],
                         reverse=True)[:5]
            top5_etfs.extend(top5)

            print(f"\n[선정된 상위 ETF]")
            for e in top5:
                print(f"  {e['name']:35s} "
                      f"등락:{e['change']:+.2f}% "
                      f"수급:{e['supply_score']}pt "
                      f"뉴스:{e['news_score']:+d}pt "
                      f"합계:{e['etf_total']:.1f}pt")

            seen = set()
            for etf in top5:
                code = etf["code"]
                if code in etf_holdings:
                    for s in etf_holdings[code]["stocks"]:
                        if s["code"] not in seen and len(s["code"]) == 6:
                            seen.add(s["code"])
                            stock_list.append({
                                "code":         s["code"],
                                "name":         s["name"],
                                "etf_name":     etf["name"],
                                "etf_change":   etf["change"],
                                "etf_supply":   etf["supply_score"],
                                "etf_news":     etf["news_score"],
                                "weight":       s["weight"],
                                "change":       0,
                                "total_score":  0,
                            })

            print(f"\nPHASE 4: 구성종목 등락률 수집 ({len(stock_list)}개)")
            phase[0] = "stock_change"
            current_idx[0] = 0
            fetch_next()
            return

        etf = etf_list[current_idx[0]]
        kiwoom.dynamicCall("SetInputValue(QString, QString)",
                          "종목코드", etf["code"])
        kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)",
                          "ETF등락률", "opt10001", 0, "0201")

    # PHASE 4: 구성종목 등락률 수집
    elif phase[0] == "stock_change":
        if current_idx[0] >= len(stock_list):
            calc_total_scores()
            print_result()
            loop.quit()
            return

        stock = stock_list[current_idx[0]]
        kiwoom.dynamicCall("SetInputValue(QString, QString)",
                          "종목코드", stock["code"])
        kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)",
                          "종목등락률", "opt10001", 0, "0301")

def on_tr(*args):
    trcode = args[2]
    rqname = args[1]

    # ETF 수급
    if rqname == "ETF수급":
        cnt = kiwoom.dynamicCall(
            "GetRepeatCnt(QString, QString)", trcode, rqname)
        days = []
        for i in range(min(cnt, 60)):
            try:
                f = int(kiwoom.dynamicCall(
                    "GetCommData(QString, QString, int, QString)",
                    trcode, rqname, i, "외국인투자자").strip() or 0)
                g = int(kiwoom.dynamicCall(
                    "GetCommData(QString, QString, int, QString)",
                    trcode, rqname, i, "기관계").strip() or 0)
                days.append({"foreign": f, "inst": g})
            except:
                days.append({"foreign": 0, "inst": 0})

        foreign_days = 0
        for d in days:
            if d["foreign"] > 0: foreign_days += 1
            else: break
        inst_days = 0
        for d in days:
            if d["inst"] > 0: inst_days += 1
            else: break

        supply_score = calc_supply_score(foreign_days, inst_days)
        etf_list[current_idx[0]]["foreign_days"]  = foreign_days
        etf_list[current_idx[0]]["inst_days"]     = inst_days
        etf_list[current_idx[0]]["supply_score"]  = supply_score

        if current_idx[0] % 30 == 0:
            print(f"  ETF 수급 진행: {current_idx[0]}/{len(etf_list)}")

        current_idx[0] += 1
        time.sleep(0.4)
        fetch_next()

    # ETF 등락률
    elif rqname == "ETF등락률":
        rate = kiwoom.dynamicCall(
            "GetCommData(QString, QString, int, QString)",
            trcode, rqname, 0, "등락율").strip()
        try:
            etf_list[current_idx[0]]["change"] = float(rate)
        except:
            etf_list[current_idx[0]]["change"] = 0
        current_idx[0] += 1
        time.sleep(0.3)
        fetch_next()

    # 구성종목 등락률
    elif rqname == "종목등락률":
        rate = kiwoom.dynamicCall(
            "GetCommData(QString, QString, int, QString)",
            trcode, rqname, 0, "등락율").strip()
        try:
            stock_list[current_idx[0]]["change"] = float(rate)
        except:
            stock_list[current_idx[0]]["change"] = 0
        s = stock_list[current_idx[0]]
        print(f"  {s['name']:15s} {s['change']:+.2f}%")
        current_idx[0] += 1
        time.sleep(0.3)
        fetch_next()

def calc_total_scores():
    """최종 점수 계산 (총 100pt)"""
    for s in stock_list:
        # ETF 강도 (10pt)
        etf_score = min(s["etf_change"] * 0.5, 10)

        # ETF 수급 (40pt)
        etf_supply_score = min(s["etf_supply"], 40)

        # ETF 뉴스 Gemini (25pt) - 부정이면 감점 가능
        news_score = max(min(s["etf_news"], 25), -25)

        # 구성종목 상승률 (25pt)
        c = s["change"]
        if c >= 15:   change_score = 25
        elif c >= 10: change_score = 20
        elif c >= 7:  change_score = 15
        elif c >= 5:  change_score = 10
        elif c >= 3:  change_score = 5
        elif c > 0:   change_score = 2
        else:         change_score = 0

        total = etf_score + etf_supply_score + news_score + change_score
        s["total_score"]       = round(total, 1)
        s["etf_score"]         = round(etf_score, 1)
        s["etf_supply_score"]  = etf_supply_score
        s["news_score"]        = news_score
        s["change_score"]      = change_score

def print_result():
    print("\n" + "="*60)
    print("[ETF별 대장주 선정]")
    print("="*60)

    for etf in top5_etfs:
        etf_code = etf["code"]
        if etf_code not in etf_holdings:
            continue
        etf_stock_codes = [s["code"] for s in etf_holdings[etf_code]["stocks"]]
        candidates = [s for s in stock_list if s["code"] in etf_stock_codes]
        candidates.sort(key=lambda x: x["total_score"], reverse=True)

        print(f"\n▶ {etf['name']} "
              f"등락:{etf['change']:+.2f}% "
              f"수급:{etf['supply_score']}pt "
              f"뉴스:{etf['news_score']:+d}pt")
        for i, s in enumerate(candidates[:3], 1):
            star = "🏆" if i == 1 else f"{i}위"
            print(f"   {star} {s['name']:15s} "
                  f"등락:{s['change']:+.2f}% "
                  f"총점:{s['total_score']}pt")

    print("\n" + "="*60)
    print("🎯 최종 대장주 추천 TOP 5")
    print("="*60)
    all_candidates = sorted(stock_list,
                            key=lambda x: x["total_score"],
                            reverse=True)
    seen = set()
    rank = 1
    top5 = []
    for s in all_candidates:
        if s["name"] not in seen:
            seen.add(s["name"])
            top5.append(s)
            print(f"  {rank}위 {s['name']:15s} "
                  f"총점:{s['total_score']:4.1f}pt "
                  f"등락:{s['change']:+.2f}% "
                  f"수급:{s['etf_supply_score']}pt "
                  f"뉴스:{s['news_score']:+d}pt "
                  f"[{s['etf_name']}]")
            rank += 1
            if rank > 5:
                break

    # 저장 + 발송
    send_telegram(format_telegram(top5, top5_etfs))
    save_to_sheet([{
        "corp_name":   s["name"],
        "stock_code":  s["code"],
        "final_score": s["total_score"],
        "etf_name":    s["etf_name"],
        "change":      s["change"],
        "supply_score":s["etf_supply_score"],
        "news_score":  s["news_score"],
    } for s in top5])
    save_picks(top5)

kiwoom.OnEventConnect[int].connect(on_login)
kiwoom.OnReceiveTrData.connect(on_tr)
kiwoom.dynamicCall("CommConnect()")
loop.exec_()