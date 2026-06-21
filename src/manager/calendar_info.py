from datetime import date, timedelta

from PySide6.QtCore import QObject, Slot


# 1900-2100 农历数据,通用 bit 表:闰月、大小月、闰月天数。
_LUNAR_INFO = [
    0x04BD8, 0x04AE0, 0x0A570, 0x054D5, 0x0D260, 0x0D950, 0x16554, 0x056A0,
    0x09AD0, 0x055D2, 0x04AE0, 0x0A5B6, 0x0A4D0, 0x0D250, 0x1D255, 0x0B540,
    0x0D6A0, 0x0ADA2, 0x095B0, 0x14977, 0x04970, 0x0A4B0, 0x0B4B5, 0x06A50,
    0x06D40, 0x1AB54, 0x02B60, 0x09570, 0x052F2, 0x04970, 0x06566, 0x0D4A0,
    0x0EA50, 0x06E95, 0x05AD0, 0x02B60, 0x186E3, 0x092E0, 0x1C8D7, 0x0C950,
    0x0D4A0, 0x1D8A6, 0x0B550, 0x056A0, 0x1A5B4, 0x025D0, 0x092D0, 0x0D2B2,
    0x0A950, 0x0B557, 0x06CA0, 0x0B550, 0x15355, 0x04DA0, 0x0A5D0, 0x14573,
    0x052D0, 0x0A9A8, 0x0E950, 0x06AA0, 0x0AEA6, 0x0AB50, 0x04B60, 0x0AAE4,
    0x0A570, 0x05260, 0x0F263, 0x0D950, 0x05B57, 0x056A0, 0x096D0, 0x04DD5,
    0x04AD0, 0x0A4D0, 0x0D4D4, 0x0D250, 0x0D558, 0x0B540, 0x0B6A0, 0x195A6,
    0x095B0, 0x049B0, 0x0A974, 0x0A4B0, 0x0B27A, 0x06A50, 0x06D40, 0x0AF46,
    0x0AB60, 0x09570, 0x04AF5, 0x04970, 0x064B0, 0x074A3, 0x0EA50, 0x06B58,
    0x05AC0, 0x0AB60, 0x096D5, 0x092E0, 0x0C960, 0x0D954, 0x0D4A0, 0x0DA50,
    0x07552, 0x056A0, 0x0ABB7, 0x025D0, 0x092D0, 0x0CAB5, 0x0A950, 0x0B4A0,
    0x0BAA4, 0x0AD50, 0x055D9, 0x04BA0, 0x0A5B0, 0x15176, 0x052B0, 0x0A930,
    0x07954, 0x06AA0, 0x0AD50, 0x05B52, 0x04B60, 0x0A6E6, 0x0A4E0, 0x0D260,
    0x0EA65, 0x0D530, 0x05AA0, 0x076A3, 0x096D0, 0x04BD7, 0x04AD0, 0x0A4D0,
    0x1D0B6, 0x0D250, 0x0D520, 0x0DD45, 0x0B5A0, 0x056D0, 0x055B2, 0x049B0,
    0x0A577, 0x0A4B0, 0x0AA50, 0x1B255, 0x06D20, 0x0ADA0, 0x14B63, 0x09370,
    0x049F8, 0x04970, 0x064B0, 0x168A6, 0x0EA50, 0x06B20, 0x1A6C4, 0x0AAE0,
    0x092E0, 0x0D2E3, 0x0C960, 0x0D557, 0x0D4A0, 0x0DA50, 0x05D55, 0x056A0,
    0x0A6D0, 0x055D4, 0x052D0, 0x0A9B8, 0x0A950, 0x0B4A0, 0x0B6A6, 0x0AD50,
    0x055A0, 0x0ABA4, 0x0A5B0, 0x052B0, 0x0B273, 0x06930, 0x07337, 0x06AA0,
    0x0AD50, 0x14B55, 0x04B60, 0x0A570, 0x054E4, 0x0D160, 0x0E968, 0x0D520,
    0x0DAA0, 0x16AA6, 0x056D0, 0x04AE0, 0x0A9D4, 0x0A2D0, 0x0D150, 0x0F252,
    0x0D520,
]

_MONTHS = ["正月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "冬月", "腊月"]
_DAYS = ["初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
         "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
         "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]
_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
_ANIMALS = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

_LUNAR_FESTIVALS = {
    (1, 1): "春节",
    (1, 15): "元宵节",
    (5, 5): "端午节",
    (7, 7): "七夕",
    (8, 15): "中秋节",
    (9, 9): "重阳节",
    (12, 8): "腊八节",
}
_SOLAR_FESTIVALS = {
    (1, 1): "元旦",
    (2, 14): "情人节",
    (3, 8): "妇女节",
    (3, 12): "植树节",
    (5, 1): "劳动节",
    (6, 1): "儿童节",
    (10, 1): "国庆节",
}


def _dates(start, end):
    d = date.fromisoformat(start)
    e = date.fromisoformat(end)
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=1)


_LEGAL_2026 = {}
for _name, _start, _end in [
    ("元旦", "2026-01-01", "2026-01-03"),
    ("春节", "2026-02-15", "2026-02-23"),
    ("清明节", "2026-04-04", "2026-04-06"),
    ("劳动节", "2026-05-01", "2026-05-05"),
    ("端午节", "2026-06-19", "2026-06-21"),
    ("中秋节", "2026-09-25", "2026-09-27"),
    ("国庆节", "2026-10-01", "2026-10-07"),
]:
    for _d in _dates(_start, _end):
        _LEGAL_2026[_d] = ("holiday", _name)
for _d in ["2026-01-04", "2026-02-14", "2026-02-28", "2026-05-09", "2026-09-20", "2026-10-10"]:
    _LEGAL_2026[_d] = ("workday", "调休上班")


def _info(year):
    if not 1900 <= year <= 2100:
        raise ValueError("lunar year out of range")
    return _LUNAR_INFO[year - 1900]


def _leap_month(year):
    return _info(year) & 0xF


def _leap_days(year):
    if _leap_month(year):
        return 30 if (_info(year) & 0x10000) else 29
    return 0


def _month_days(year, month):
    return 30 if (_info(year) & (0x10000 >> month)) else 29


def _year_days(year):
    total = 348
    mask = 0x8000
    while mask > 0x8:
        if _info(year) & mask:
            total += 1
        mask >>= 1
    return total + _leap_days(year)


def _lunar_from_solar(y, m, d):
    offset = (date(y, m, d) - date(1900, 1, 31)).days
    year = 1900
    while year < 2101:
        days = _year_days(year)
        if offset < days:
            break
        offset -= days
        year += 1
    leap = _leap_month(year)
    is_leap = False
    month = 1
    while month <= 12:
        days = _leap_days(year) if is_leap else _month_days(year, month)
        if offset < days:
            return year, month, offset + 1, is_leap
        offset -= days
        if leap == month and not is_leap:
            is_leap = True
        else:
            if is_leap:
                is_leap = False
            month += 1
    return year, 12, 30, False


class CalendarInfoProvider:
    """农历、节日、2026 中国法定节假日信息。month 为 0-11。"""

    def info(self, year, month, day):
        solar = date(int(year), int(month) + 1, int(day))
        ly, lm, ld, leap = _lunar_from_solar(solar.year, solar.month, solar.day)
        legal_type, legal_name = _LEGAL_2026.get(solar.isoformat(), ("", ""))
        lunar_festival = "" if leap else _LUNAR_FESTIVALS.get((lm, ld), "")
        solar_festival = _SOLAR_FESTIVALS.get((solar.month, solar.day), "")
        if solar.month == 4 and solar.day in (4, 5):
            solar_festival = "清明节"
        festival = legal_name if legal_type == "holiday" else (lunar_festival or solar_festival)
        if not festival and lm == 12 and ld == _month_days(ly, 12):
            festival = "除夕"
        stem_branch = _STEMS[(ly - 4) % 10] + _BRANCHES[(ly - 4) % 12]
        lunar_month = ("闰" if leap else "") + _MONTHS[lm - 1]
        lunar_day = _DAYS[ld - 1]
        cell_label = legal_name if legal_type == "holiday" else (festival or lunar_day)
        return {
            "date": solar.isoformat(),
            "lunarYear": stem_branch + "年",
            "zodiac": _ANIMALS[(ly - 4) % 12],
            "lunarMonth": lunar_month,
            "lunarDay": lunar_day,
            "festival": festival,
            "holidayName": legal_name,
            "dayType": legal_type,
            "cellLabel": cell_label,
        }


class CalendarInfoBridge(QObject):
    def __init__(self, provider=None):
        super().__init__()
        self._provider = provider or CalendarInfoProvider()

    @Slot(int, int, int, result="QVariantMap")
    def info(self, year, month, day):
        return self._provider.info(year, month, day)

    @Slot(int, int, int, result=str)
    def cellLabel(self, year, month, day):
        return self._provider.info(year, month, day)["cellLabel"]

    @Slot(int, int, int, result=str)
    def dayType(self, year, month, day):
        return self._provider.info(year, month, day)["dayType"]
