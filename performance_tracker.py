import json
import time
import requests
import sys
import os
from datetime import datetime, timedelta
from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
from dotenv import load_dotenv

load_dotenv()
# ── 설정값 ───────────────────────────────
GOOGLE_SHEET_WEBAPP_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID")

app = QApplication(sys.argv)
kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
loop = QEventLoop()

stock_list  = []
current_idx = [0]

def on_login(err_code):
    if err_code == 0:
        print("✅ 키움 로그인 성공")
        load_yesterday_picks()
        if not stock_list:
            print("어제 picks 없음")
            loop.quit()
            return
        print(f"어제 picks: {len(stock_list)}개")
        fetch_next()

def load_yesterday_picks():
    """picks.json에서 어제 날짜 종목 로드"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 월요일이면 금요일 데이터 가져오기
    if datetime.now().weekday() == 0:
        yesterday = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    try:
        with open("picks.json", "r", encoding="utf-8") as f:
            all_picks = json.load(f)
    except:
        print("picks.json 없음")
        return

    yesterday_picks = [p for p in all_picks
                      if p.get("date", "").startswith(yesterday)]

    print(f"어제({yesterday}) picks: {len(yesterday_picks)}개")

    for p in yesterday_picks:
        stock_list.append({
            "date":        p["date"],
            "corp_name":   p["corp_name"],
            "stock_code":  p["stock_code"],
            "final_score": p["final_score"],
            "buy_price":   p.get("buy_price", 0),
            "etf_name":    p.get("etf_name", ""),
            "open":        0,
            "high":        0,
            "low":         0,
            "close":       0,
            "change_rate": 0,
            "result":      ""
        })

def fetch_next():
    if current_idx[0] >= len(stock_list):
        calc_results()
        loop.quit()
        return

    stock = stock_list[current_idx[0]]
    today = datetime.now().strftime("%Y%m%d")
    kiwoom.dynamicCall("SetInputValue(QString, QString)",
                      "종목코드", stock["stock_code"])
    kiwoom.dynamicCall("SetInputValue(QString, QString)",
                      "기준일자", today)
    kiwoom.dynamicCall("SetInputValue(QString, QString)",
                      "수정주가구분", "1")
    kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)",
                      "주식일봉", "opt10081", 0, "0401")

def on_tr(*args):
    trcode = args[2]
    rqname = args[1]

    if rqname == "주식일봉":
        cnt = kiwoom.dynamicCall(
            "GetRepeatCnt(QString, QString)", trcode, rqname)

        if cnt > 0:
            # 오늘 데이터 (index 0)
            close = kiwoom.dynamicCall(
                "GetCommData(QString, QString, int, QString)",
                trcode, rqname, 0, "현재가").strip().lstrip("-")
            open_ = kiwoom.dynamicCall(
                "GetCommData(QString, QString, int, QString)",
                trcode, rqname, 0, "시가").strip().lstrip("-")
            high = kiwoom.dynamicCall(
                "GetCommData(QString, QString, int, QString)",
                trcode, rqname, 0, "고가").strip().lstrip("-")
            low = kiwoom.dynamicCall(
                "GetCommData(QString, QString, int, QString)",
                trcode, rqname, 0, "저가").strip().lstrip("-")

            try:
                close = int(close)
                open_ = int(open_)
                high  = int(high)
                low   = int(low)
            except:
                close = open_ = high = low = 0

            # 어제 종가 (index 1) → 매수 기준가
            if cnt > 1:
                prev_close = kiwoom.dynamicCall(
                    "GetCommData(QString, QString, int, QString)",
                    trcode, rqname, 1, "현재가").strip().lstrip("-")
                try:
                    prev_close = int(prev_close)
                except:
                    prev_close = close

                change_rate = round(
                    (close - prev_close) / prev_close * 100, 2
                ) if prev_close > 0 else 0
            else:
                change_rate = 0
                prev_close  = close

            stock_list[current_idx[0]]["open"]        = open_
            stock_list[current_idx[0]]["high"]        = high
            stock_list[current_idx[0]]["low"]         = low
            stock_list[current_idx[0]]["close"]       = close
            stock_list[current_idx[0]]["buy_price"]   = prev_close
            stock_list[current_idx[0]]["change_rate"] = change_rate

            name = stock_list[current_idx[0]]["corp_name"]
            print(f"  {name:15s} 시:{open_:,} 고:{high:,} "
                  f"저:{low:,} 종:{close:,} "
                  f"등락:{change_rate:+.2f}%")

        current_idx[0] += 1
        time.sleep(0.3)
        fetch_next()

def calc_results():
    """결과 계산 + 출력 + 저장"""
    print("\n" + "="*55)
    print("📊 D+1 성과 추적 결과")
    print("="*55)

    total_return = 0
    win = 0
    lose = 0

    for s in stock_list:
        change = s["change_rate"]
        if change >= 3:
            result = "✅ 수익"
            win += 1
        elif change <= -3:
            result = "❌ 손실"
            lose += 1
        else:
            result = "➖ 보합"

        s["result"] = result
        total_return += change

        print(f"  {s['corp_name']:15s} "
              f"등락:{change:+.2f}% "
              f"{result} "
              f"[{s['etf_name']}]")

    avg_return = total_return / len(stock_list) if stock_list else 0
    print(f"\n  수익: {win}개 / 손실: {lose}개 / "
          f"평균 등락: {avg_return:+.2f}%")

    # 텔레그램 발송
    send_telegram_result(stock_list, win, lose, avg_return)

    # 구글시트 저장
    save_performance_to_sheet(stock_list, avg_return)

def send_telegram_result(stocks, win, lose, avg_return):
    if not TELEGRAM_BOT_TOKEN or "여기에" in TELEGRAM_BOT_TOKEN:
        return

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%m/%d")
    if datetime.now().weekday() == 0:
        yesterday = (datetime.now() - timedelta(days=3)).strftime("%m/%d")

    lines = [f"📊 <b>D+1 성과 ({yesterday} 추천)</b>\n"]
    for s in stocks:
        emoji = "✅" if s["change_rate"] >= 3 else \
                "❌" if s["change_rate"] <= -3 else "➖"
        lines.append(
            f"{emoji} {s['corp_name']} "
            f"{s['change_rate']:+.2f}%"
        )
    lines.append(f"\n수익 {win}개 / 손실 {lose}개")
    lines.append(f"평균 등락: <b>{avg_return:+.2f}%</b>")

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID,
                  "text": "\n".join(lines),
                  "parse_mode": "HTML"},
            timeout=10)
        print("텔레그램 전송 완료")
    except Exception as e:
        print(f"텔레그램 실패: {e}")

def save_performance_to_sheet(stocks, avg_return):
    if not GOOGLE_SHEET_WEBAPP_URL or "여기에" in GOOGLE_SHEET_WEBAPP_URL:
        return
    try:
        res = requests.post(GOOGLE_SHEET_WEBAPP_URL, json={
            "type":       "performance",
            "date":       datetime.now().strftime("%Y-%m-%d"),
            "avg_return": avg_return,
            "data": [{
                "corp_name":   s["corp_name"],
                "stock_code":  s["stock_code"],
                "final_score": s["final_score"],
                "buy_price":   s["buy_price"],
                "close":       s["close"],
                "change_rate": s["change_rate"],
                "result":      s["result"],
                "etf_name":    s["etf_name"],
            } for s in stocks]
        }, timeout=15)
        print(f"구글시트 저장: {res.status_code}")
    except Exception as e:
        print(f"구글시트 실패: {e}")

kiwoom.OnEventConnect[int].connect(on_login)
kiwoom.OnReceiveTrData.connect(on_tr)
kiwoom.dynamicCall("CommConnect()")
loop.exec_()