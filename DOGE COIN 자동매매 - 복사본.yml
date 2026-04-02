import os
import csv
import time
import datetime
import ccxt
import pandas as pd

BYBIT_API_KEY = "여기에 API KEY를 입력해주세요."
BYBIT_SECRET  = "여기에 API KEY를 입력해주세요."

exchange = ccxt.bybit({
    'apiKey': BYBIT_API_KEY,
    'secret': BYBIT_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'linear'},
})

SYMBOL = 'DOGE/USDT:USDT'
LEVERAGE = 1

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "trade_log_bybit.csv")
STATUS_FILE = os.path.join(BASE_DIR, "position_status.txt")


# ── 저장 함수 ──────────────────────────────────────────────

def save_log(direction, result, entry_t, exit_t, entry_p, exit_p, signal_reason=''):
    if direction == 'long':
        pnl = round((exit_p - entry_p) / entry_p * 100, 2)
    else:
        pnl = round((entry_p - exit_p) / entry_p * 100, 2)
    kst_today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).date()
    is_new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(['날짜', '종목', '방향', '진입시간', '청산시간',
                             '결과', '진입가', '청산가', '수익(%)', '진입사유'])
        writer.writerow([
            kst_today, 'DOGE', direction,
            entry_t, exit_t, result, entry_p, exit_p, pnl, signal_reason
        ])


def save_status(position_type, entry_price, position_size, entry_time,
                peak_price, bottom_price, cooldown_until,
                latest_signal, latest_signal_reason):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(
            f"current_position={position_type or 'none'}\n"
            f"entry_price={entry_price or 0}\n"
            f"position_size={position_size}\n"
            f"entry_time={entry_time or '-'}\n"
            f"peak_price={peak_price or 0}\n"
            f"bottom_price={bottom_price or 0}\n"
            f"cooldown_until={cooldown_until.strftime('%Y-%m-%d %H:%M:%S') if cooldown_until else '-'}\n"
            f"latest_signal={latest_signal or 'none'}\n"
            f"latest_signal_reason={latest_signal_reason or '-'}\n"
            f"updated_at={datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )


# ── 거래소 연동 함수 ────────────────────────────────────────

def get_usdt_balance():
    try:
        balance = exchange.fetch_balance()
        if 'USDT' in balance.get('total', {}):
            val = balance['total']['USDT']
            if val and val > 0:
                return float(val)
        if 'USDT' in balance.get('free', {}):
            val = balance['free']['USDT']
            if val and val > 0:
                return float(val)
        result_list = balance.get('info', {}).get('result', {}).get('list', [])
        for item in result_list:
            for coin in item.get('coin', []):
                if coin.get('coin') == 'USDT':
                    val = coin.get('walletBalance', 0)
                    return float(val) if val else 0
        return 0
    except Exception as e:
        print(f"잔고 조회 오류: {e}")
        return 0


def get_position_size(current_price):
    try:
        usdt = get_usdt_balance()
        print(f"USDT 잔고: {usdt:.2f}")
        if usdt <= 0:
            return 0
        size = (usdt * 0.99) / current_price
        return round(size, 1)
    except Exception as e:
        print(f"수량 계산 오류: {e}")
        return 0


def set_leverage():
    try:
        exchange.set_leverage(LEVERAGE, SYMBOL)
        print(f"레버리지 {LEVERAGE}배 설정 완료")
    except Exception as e:
        if "leverage not modified" in str(e):
            print(f"레버리지 {LEVERAGE}배 이미 설정됨")
        else:
            print(f"레버리지 설정 오류: {e}")


def open_long(size):
    try:
        if size < 1:
            print("잔고 부족")
            return None
        order = exchange.create_order(SYMBOL, 'market', 'buy', size)
        print(f"✅ 롱 진입: {size} DOGE")
        return order
    except Exception as e:
        print(f"롱 진입 오류: {e}")
        return None


def close_long(size):
    try:
        order = exchange.create_order(SYMBOL, 'market', 'sell', size,
                                      params={'reduceOnly': True})
        print(f"✅ 롱 청산: {size} DOGE")
        return order
    except Exception as e:
        print(f"롱 청산 오류: {e}")
        return None


def open_short(size):
    try:
        if size < 1:
            print("잔고 부족")
            return None
        order = exchange.create_order(SYMBOL, 'market', 'sell', size)
        print(f"✅ 숏 진입: {size} DOGE")
        return order
    except Exception as e:
        print(f"숏 진입 오류: {e}")
        return None


def close_short(size):
    try:
        order = exchange.create_order(SYMBOL, 'market', 'buy', size,
                                      params={'reduceOnly': True})
        print(f"✅ 숏 청산: {size} DOGE")
        return order
    except Exception as e:
        print(f"숏 청산 오류: {e}")
        return None


def get_current_price():
    """실시간 현재가 조회 - 포지션 보유 중에만 사용"""
    try:
        ticker = exchange.fetch_ticker(SYMBOL)
        return float(ticker['last'])
    except Exception as e:
        print(f"현재가 조회 오류: {e}")
        return None


# ── 전략 분석 함수 ──────────────────────────────────────────

def fetch_5m_ohlcv():
    """5분봉 55개 조회 - 포지션 없을 때만 호출"""
    try:
        raw = exchange.fetch_ohlcv(SYMBOL, '5m', limit=55)
        df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.index = df.index.tz_localize('UTC').tz_convert('Asia/Seoul')
        return df
    except Exception as e:
        print(f"5분봉 OHLCV 조회 오류: {e}")
        return None


def calc_rsi(closes, period=14):
    """RSI(14) 계산 - 완성봉 종가 시리즈를 받아 최신 RSI 반환"""
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def calc_range(df):
    """
    [포지션 없을 때 1회만 호출]
    완성봉 50개 기준으로 range_high / range_low 계산 후 반환.
    반환값을 frozen_range_high / frozen_range_low 에 저장해 고정(freeze)한다.
    박스 폭이 1% 미만이면 None 반환 → 진입 금지.
    RSI(14) 도 함께 계산해 반환.
    """
    df_done = df.iloc[:-1].copy()
    df50 = df_done.iloc[-50:]

    range_high = float(df50['high'].max())
    range_low = float(df50['low'].min())
    last_close = float(df_done['close'].iloc[-1])

    # ── RSI(14) 계산 ──
    rsi = calc_rsi(df_done['close'])

    # ── 박스 폭 필터: 1% 미만이면 진입 금지 ──
    range_pct = (range_high - range_low) / range_low * 100
    if range_pct < 1.0:
        return None, None, last_close, range_pct, rsi

    return range_high, range_low, last_close, range_pct, rsi


def analyze_5m(last_close, frozen_range_high, frozen_range_low, rsi):
    """
    [매 루프 신호 판단 - range 재계산 없음]
    frozen_range_high / frozen_range_low 기준으로만 신호 판단.
    롱: 종가 >= frozen_range_high  AND  RSI(14) > 50
    숏: 종가 <= frozen_range_low   AND  RSI(14) < 50
    """
    if last_close >= frozen_range_high:
        if rsi > 50:
            signal = 'long'
            reason = (f"5분봉 종가 고점 돌파 | RSI={rsi} > 50 | "
                      f"last_close={last_close:.5f} >= frozen_high={frozen_range_high:.5f}")
        else:
            signal = None
            reason = (f"고점 돌파 but RSI={rsi} <= 50 → 롱 진입 금지 | "
                      f"last_close={last_close:.5f} frozen_high={frozen_range_high:.5f}")
    elif last_close <= frozen_range_low:
        if rsi < 50:
            signal = 'short'
            reason = (f"5분봉 종가 저점 이탈 | RSI={rsi} < 50 | "
                      f"last_close={last_close:.5f} <= frozen_low={frozen_range_low:.5f}")
        else:
            signal = None
            reason = (f"저점 이탈 but RSI={rsi} >= 50 → 숏 진입 금지 | "
                      f"last_close={last_close:.5f} frozen_low={frozen_range_low:.5f}")
    else:
        signal = None
        reason = (f"범위 내 | RSI={rsi} | last_close={last_close:.5f} | "
                  f"frozen_high={frozen_range_high:.5f} frozen_low={frozen_range_low:.5f}")

    return signal, reason


# ── 대기 함수 ───────────────────────────────────────────────

def wait_next_5m():
    """5분봉 마감 후 5초에 실행"""
    KST = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(KST)
    minutes = now.minute % 5
    seconds = minutes * 60 + now.second
    wait = (300 - seconds) + 5
    if wait < 10:
        wait = 305
    print(f"다음 5분봉까지 {wait}초 대기...")
    time.sleep(wait)


# ── 메인 루프 ───────────────────────────────────────────────

def run():
    print("=" * 55)
    print("DOGE 바이비트 롱/숏 자동매매 [5분봉 박스 돌파]")
    print("전략: 5분봉 완성봉 50개 기준 종가 박스 돌파 진입")
    print("range: 포지션 진입 전 1회 계산 후 고정(freeze)")
    print("필터: 박스 폭 1% 미만 진입 금지")
    print("롱: 종가 >= frozen_range_high  AND  RSI(14) > 50")
    print("숏: 종가 <= frozen_range_low   AND  RSI(14) < 50")
    print("손절: 실시간 -0.7% 즉시 청산 [우선순위 1]")
    print("부분익절: 수익 +0.5% 도달 시 50% 시장가 청산 (1회) [우선순위 2]")
    print("트레일링: 수익 +0.5% 이상 시 활성 / 고점(저점) 대비 -0.7% [우선순위 3]")
    print("연속 손절 2회 → 20분 휴식")
    print("동일 방향 청산 후 1봉 진입 금지")
    print(f"로그 저장: {LOG_FILE}")
    print(f"상태 저장: {STATUS_FILE}")
    print("=" * 55)

    set_leverage()

    in_position = False
    position_type = None
    entry_price = None
    entry_time = None
    position_size = 0
    peak_price = None
    bottom_price = None
    signal_reason = ''
    trailing_active = False
    last_exit_side = None
    last_exit_candle_time = None
    last_ohlcv_candle = None

    # ── 부분 익절 플래그 ──────────────────────────────────────
    partial_exit_done = False

    # ── frozen range 변수 ─────────────────────────────────────
    frozen_range_high = None
    frozen_range_low = None
    is_range_frozen = False
    rsi = 50.0  # 초기값

    consec_losses = 0
    cooldown_until = None
    current_date = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).date()

    latest_signal = None
    latest_signal_reason = ''

    save_status(None, None, 0, None, None, None, None, None, None)

    while True:
        try:
            KST = datetime.timezone(datetime.timedelta(hours=9))
            now = datetime.datetime.now(KST)
            today = now.date()

            if current_date != today:
                current_date = today
                print(f"\n📅 새로운 날: {today}")

            in_cooldown = cooldown_until and now < cooldown_until

            # ════════════════════════════════════════
            # ── 포지션 없을 때: range 계산(1회) + 종가 기준 진입 판단 ──
            # ════════════════════════════════════════
            if not in_position:
                if in_cooldown:
                    print(f"[{now.strftime('%H:%M:%S')}] 쿨다운 중 ({cooldown_until.strftime('%H:%M')}까지)")
                    is_range_frozen = False
                    wait_next_5m()
                    continue

                # ── range 미고정 시: 5분봉 조회 및 30봉 계산 ──
                if not is_range_frozen:
                    df = fetch_5m_ohlcv()
                    if df is None:
                        print("5분봉 OHLCV 조회 실패, 재시도...")
                        time.sleep(30)
                        continue

                    frozen_range_high, frozen_range_low, last_close, range_pct, rsi = calc_range(df)
                    current_candle_time = df.index[-2]

                    # 박스 폭 1% 미만이면 range 고정 않고 대기
                    if frozen_range_high is None:
                        print(f"[{now.strftime('%H:%M:%S')}] "
                              f"[RANGE SKIP] 박스 폭 {range_pct:.2f}% < 1.0% → 진입 금지 | "
                              f"RSI={rsi} | 완성봉 종가={last_close:.4f}")
                        wait_next_5m()
                        continue

                    is_range_frozen = True
                    print(f"[{now.strftime('%H:%M:%S')}] "
                          f"[RANGE FREEZE] high={frozen_range_high:.5f} low={frozen_range_low:.5f} | "
                          f"박스폭={range_pct:.2f}% | RSI={rsi} | 완성봉 종가={last_close:.4f} | 연속손절: {consec_losses}회")
                    # range 새로 계산 직후에는 바로 진입하지 않고 다음 봉 대기
                    # (현재 종가가 이미 박스 경계 밖에 있는 경우 즉시 진입 방지)
                    wait_next_5m()
                    continue

                else:
                    # ── range 고정 상태: 종가 및 RSI 재조회 ──
                    df = fetch_5m_ohlcv()
                    if df is None:
                        print("5분봉 OHLCV 조회 실패, 재시도...")
                        time.sleep(30)
                        continue

                    df_done = df.iloc[:-1].copy()
                    last_close = float(df_done['close'].iloc[-1])
                    rsi = calc_rsi(df_done['close'])
                    current_candle_time = df.index[-2]

                    print(f"[{now.strftime('%H:%M:%S')}] "
                          f"[RANGE FIXED] high={frozen_range_high:.5f} low={frozen_range_low:.5f} | "
                          f"완성봉 종가={last_close:.4f} | RSI={rsi} | 연속손절: {consec_losses}회")

                # ── 고정된 range 기준으로 신호 판단 (RSI 포함) ──
                signal, reason = analyze_5m(last_close, frozen_range_high, frozen_range_low, rsi)
                latest_signal = signal
                latest_signal_reason = reason

                print(f"   신호: {signal or '없음'} | {reason}")

                if signal in ('long', 'short'):
                    # 동일 방향 연속 진입 금지: 청산 후 1봉 대기
                    if signal == last_exit_side and last_exit_candle_time is not None:
                        candle_diff = (current_candle_time - last_exit_candle_time).total_seconds() / 300
                        if candle_diff <= 1:
                            print(f"   신호: {signal} | 동일 방향 청산 후 1봉 대기 중 → 스킵")
                            wait_next_5m()
                            continue

                    # 시장가 진입
                    rt_price = get_current_price()
                    if rt_price is None:
                        time.sleep(4)
                        continue

                    size = get_position_size(rt_price)
                    order = open_long(size) if signal == 'long' else open_short(size)
                    if order:
                        entry_price = (
                                float(order.get('average') or 0) or
                                float(order.get('price') or 0) or
                                rt_price
                        )
                        entry_time = now.strftime('%H:%M')
                        in_position = True
                        position_type = signal
                        position_size = size
                        peak_price = entry_price if signal == 'long' else None
                        bottom_price = entry_price if signal == 'short' else None
                        trailing_active = False
                        partial_exit_done = False
                        signal_reason = reason
                        last_ohlcv_candle = current_candle_time
                        print(f"   진입가(체결): {entry_price:.6f} | "
                              f"frozen_high={frozen_range_high:.5f} frozen_low={frozen_range_low:.5f}")
                        save_status(position_type, entry_price, position_size, entry_time,
                                    peak_price, bottom_price, cooldown_until,
                                    latest_signal, latest_signal_reason)
                else:
                    wait_next_5m()

            # ════════════════════════════════════════
            # ── 포지션 있을 때: 실시간 루프 ──
            # ════════════════════════════════════════
            else:
                current_price = get_current_price()
                if current_price is None:
                    time.sleep(6)
                    continue

                if position_type == 'long':
                    pnl_rt = round((current_price - entry_price) / entry_price * 100, 4)
                else:
                    pnl_rt = round((entry_price - current_price) / entry_price * 100, 4)

                # ── [우선순위 1] 손절: -0.7% 즉시 청산 ──
                sl_triggered = (
                        (position_type == 'long' and current_price <= entry_price * 0.993) or
                        (position_type == 'short' and current_price >= entry_price * 1.007)
                )

                if sl_triggered:
                    exit_time = now.strftime('%H:%M')
                    print(f"\n🛑 손절! {position_type} / {pnl_rt}% (현재가: {current_price:.6f})")
                    if position_type == 'long':
                        close_long(position_size)
                    else:
                        close_short(position_size)
                    save_log(position_type, '손절', entry_time, exit_time,
                             entry_price, current_price, signal_reason)
                    last_exit_side = position_type
                    last_exit_candle_time = last_ohlcv_candle
                    in_position = False
                    entry_price = None
                    entry_time = None
                    position_type = None
                    position_size = 0
                    peak_price = None
                    bottom_price = None
                    trailing_active = False
                    partial_exit_done = False
                    consec_losses += 1
                    if consec_losses >= 2:
                        cooldown_until = now + datetime.timedelta(minutes=20)
                        print(f"⛔ 연속 손절 2회 → 20분 휴식 ({cooldown_until.strftime('%H:%M')}까지)")
                    is_range_frozen = False
                    frozen_range_high = None
                    frozen_range_low = None
                    save_status(None, None, 0, None, None, None, cooldown_until,
                                latest_signal, latest_signal_reason)
                    continue

                # ── [우선순위 2] 부분 익절: +0.5% 도달 시 50% 청산 (1회) ──
                if pnl_rt >= 0.5 and not partial_exit_done:
                    half_size = round(position_size / 2, 1)
                    if half_size < 1:
                        half_size = 1

                    print(f"\n💰 부분 익절! {position_type} / {pnl_rt}% | "
                          f"청산 수량: {half_size} / 잔여 수량: {round(position_size - half_size, 1)}")

                    if position_type == 'long':
                        close_long(half_size)
                    else:
                        close_short(half_size)

                    save_log(position_type, '부분익절', entry_time, now.strftime('%H:%M'),
                             entry_price, current_price, signal_reason)

                    position_size = round(position_size - half_size, 1)
                    partial_exit_done = True

                    # 부분 익절과 동시에 트레일링 활성화
                    trailing_active = True
                    if position_type == 'long':
                        peak_price = current_price
                    else:
                        bottom_price = current_price

                    print(f"   잔여 포지션: {position_size} DOGE | 트레일링 활성화")
                    save_status(position_type, entry_price, position_size, entry_time,
                                peak_price, bottom_price, cooldown_until,
                                latest_signal, latest_signal_reason)

                # ── [우선순위 3] 트레일링: +0.5% 이상 시 활성 / 되돌림 0.7% ──
                if pnl_rt >= 0.5 and not trailing_active:
                    trailing_active = True
                    if position_type == 'long':
                        peak_price = current_price
                    else:
                        bottom_price = current_price

                if trailing_active:
                    if position_type == 'long':
                        peak_price = max(peak_price, current_price) if peak_price else current_price
                        trailing_stop = round(peak_price * 0.993, 6)  # 고점 대비 -0.7%
                        trail_hit = current_price <= trailing_stop
                        print(f"[{now.strftime('%H:%M:%S')}] "
                              f"롱 | 진입가: {entry_price:.6f} | 현재가: {current_price:.6f} | "
                              f"수익: {pnl_rt}% | 고점: {peak_price:.6f} | stop: {trailing_stop:.6f} | "
                              f"잔여수량: {position_size}")
                    else:
                        bottom_price = min(bottom_price, current_price) if bottom_price else current_price
                        trailing_stop = round(bottom_price * 1.007, 6)  # 저점 대비 +0.7%
                        trail_hit = current_price >= trailing_stop
                        print(f"[{now.strftime('%H:%M:%S')}] "
                              f"숏 | 진입가: {entry_price:.6f} | 현재가: {current_price:.6f} | "
                              f"수익: {pnl_rt}% | 저점: {bottom_price:.6f} | stop: {trailing_stop:.6f} | "
                              f"잔여수량: {position_size}")

                    if trail_hit:
                        exit_time = now.strftime('%H:%M')
                        print(f"\n🎯 트레일링 청산! {position_type} / {pnl_rt}% | 수량: {position_size}")
                        if position_type == 'long':
                            close_long(position_size)
                        else:
                            close_short(position_size)
                        save_log(position_type, '트레일링청산', entry_time, exit_time,
                                 entry_price, current_price, signal_reason)
                        last_exit_side = position_type
                        last_exit_candle_time = last_ohlcv_candle
                        in_position = False
                        entry_price = None
                        entry_time = None
                        position_type = None
                        position_size = 0
                        peak_price = None
                        bottom_price = None
                        trailing_active = False
                        partial_exit_done = False
                        consec_losses = 0
                        is_range_frozen = False
                        frozen_range_high = None
                        frozen_range_low = None
                        save_status(None, None, 0, None, None, None, cooldown_until,
                                    latest_signal, latest_signal_reason)
                        continue
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] "
                          f"{position_type} | 진입가: {entry_price:.6f} | 현재가: {current_price:.6f} | "
                          f"수익: {pnl_rt}% | 트레일링 대기 (0.5% 미만) | 잔여수량: {position_size}")

                # 상태 파일 갱신
                save_status(position_type, entry_price, position_size, entry_time,
                            peak_price, bottom_price, cooldown_until,
                            latest_signal, latest_signal_reason)

                time.sleep(6)

        except Exception as e:
            err_msg = str(e)
            print(f"⚠️ 오류: {err_msg}")
            if "Rate Limit" in err_msg or "Too many visits" in err_msg or "10006" in err_msg:
                print("   Rate Limit 감지 → 60초 대기")
                time.sleep(60)
            else:
                time.sleep(30)
            continue


try:
    run()
except KeyboardInterrupt:
    print("🚨 수동 종료!")