from manager.calendar_info import CalendarInfoProvider


def test_lunar_dates_for_2026_major_festivals():
    p = CalendarInfoProvider()

    spring = p.info(2026, 1, 17)  # 2026-02-17
    assert spring["lunarDay"] == "初一"
    assert spring["lunarMonth"] == "正月"
    assert spring["festival"] == "春节"

    dragon_boat = p.info(2026, 5, 19)  # 2026-06-19
    assert dragon_boat["lunarDay"] == "初五"
    assert dragon_boat["lunarMonth"] == "五月"
    assert dragon_boat["festival"] == "端午节"

    mid_autumn = p.info(2026, 8, 25)  # 2026-09-25
    assert mid_autumn["lunarDay"] == "十五"
    assert mid_autumn["lunarMonth"] == "八月"
    assert mid_autumn["festival"] == "中秋节"


def test_2026_legal_holiday_and_adjusted_workday():
    p = CalendarInfoProvider()

    assert p.info(2026, 0, 1)["dayType"] == "holiday"
    assert p.info(2026, 0, 1)["holidayName"] == "元旦"
    assert p.info(2026, 0, 4)["dayType"] == "workday"
    assert p.info(2026, 0, 4)["holidayName"] == "调休上班"
    assert p.info(2026, 8, 20)["dayType"] == "workday"
    assert p.info(2026, 8, 20)["holidayName"] == "调休上班"
    assert p.info(2026, 9, 1)["dayType"] == "holiday"
    assert p.info(2026, 9, 1)["holidayName"] == "国庆节"


def test_cell_label_prefers_legal_holiday_then_festival_then_lunar_day():
    p = CalendarInfoProvider()

    assert p.info(2026, 9, 1)["cellLabel"] == "国庆节"
    assert p.info(2026, 1, 17)["cellLabel"] == "春节"
    assert p.info(2026, 5, 22)["cellLabel"] == "初八"
