# -*- coding: utf-8 -*-
import os
import uuid
import math
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Flowable,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

try:
    import swisseph as swe
    SWISS_AVAILABLE = True
except Exception:
    swe = None
    SWISS_AVAILABLE = False


pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

API_KEY = os.getenv("ASTRO_API_KEY", "CHANGE_ME_TO_A_SECRET_KEY")

BASE_URL = os.getenv(
    "BASE_URL",
    "https://astrology-api-l5tr.onrender.com"
)

PAYMENT_PAGE_URL = os.getenv(
    "PAYMENT_PAGE_URL",
    "https://astrology-api-l5tr.onrender.com/success"
)

OUTPUT_DIR = "generated_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="AI Astrology Report API")
app.mount("/reports", StaticFiles(directory=OUTPUT_DIR), name="reports")


class BirthInput(BaseModel):
    token: Optional[str] = None
    name: Optional[str] = None
    birth_date: str
    birth_time: str
    birth_place: str
    gender: Optional[str] = None
    timezone: Optional[str] = "Asia/Taipei"
    plan: Optional[str] = "free"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


ZODIAC_SIGNS = [
    ("牡羊座", "Aries", "♈"),
    ("金牛座", "Taurus", "♉"),
    ("雙子座", "Gemini", "♊"),
    ("巨蟹座", "Cancer", "♋"),
    ("獅子座", "Leo", "♌"),
    ("處女座", "Virgo", "♍"),
    ("天秤座", "Libra", "♎"),
    ("天蠍座", "Scorpio", "♏"),
    ("射手座", "Sagittarius", "♐"),
    ("摩羯座", "Capricorn", "♑"),
    ("水瓶座", "Aquarius", "♒"),
    ("雙魚座", "Pisces", "♓"),
]

PLANET_DEFS = [
    ("太陽", "Sun", "☉", "SUN"),
    ("月亮", "Moon", "☽", "MOON"),
    ("水星", "Mercury", "☿", "MERCURY"),
    ("金星", "Venus", "♀", "VENUS"),
    ("火星", "Mars", "♂", "MARS"),
    ("木星", "Jupiter", "♃", "JUPITER"),
    ("土星", "Saturn", "♄", "SATURN"),
    ("天王星", "Uranus", "♅", "URANUS"),
    ("海王星", "Neptune", "♆", "NEPTUNE"),
    ("冥王星", "Pluto", "♇", "PLUTO"),
]

CITY_FALLBACK = {
    "台北": (25.0330, 121.5654, "Asia/Taipei"),
    "台北市": (25.0330, 121.5654, "Asia/Taipei"),
    "台北，台灣": (25.0330, 121.5654, "Asia/Taipei"),
    "台北市，台灣": (25.0330, 121.5654, "Asia/Taipei"),
    "台中": (24.1477, 120.6736, "Asia/Taipei"),
    "台中市": (24.1477, 120.6736, "Asia/Taipei"),
    "台中，台灣": (24.1477, 120.6736, "Asia/Taipei"),
    "台中市，台灣": (24.1477, 120.6736, "Asia/Taipei"),
    "台南": (22.9999, 120.2270, "Asia/Taipei"),
    "高雄": (22.6273, 120.3014, "Asia/Taipei"),
    "東京": (35.6895, 139.6917, "Asia/Tokyo"),
    "東京，日本": (35.6895, 139.6917, "Asia/Tokyo"),
    "大阪": (34.6937, 135.5023, "Asia/Tokyo"),
    "大阪，日本": (34.6937, 135.5023, "Asia/Tokyo"),
    "紐約": (40.7128, -74.0060, "America/New_York"),
    "紐約，美國": (40.7128, -74.0060, "America/New_York"),
    "倫敦": (51.5072, -0.1276, "Europe/London"),
    "倫敦，英國": (51.5072, -0.1276, "Europe/London"),
    "香港": (22.3193, 114.1694, "Asia/Hong_Kong"),
    "新加坡": (1.3521, 103.8198, "Asia/Singapore"),
    "首爾": (37.5665, 126.9780, "Asia/Seoul"),
    "首爾，韓國": (37.5665, 126.9780, "Asia/Seoul"),
    "上海": (31.2304, 121.4737, "Asia/Shanghai"),
    "北京": (39.9042, 116.4074, "Asia/Shanghai"),
}


def symbol_for_point(name: str) -> str:
    symbol_map = {
        "太陽": "☉",
        "月亮": "☽",
        "水星": "☿",
        "金星": "♀",
        "火星": "♂",
        "木星": "♃",
        "土星": "♄",
        "天王星": "♅",
        "海王星": "♆",
        "冥王星": "♇",
        "北交點": "☊",
        "南交點": "☋",
        "凱龍星": "Ch",
        "莉莉絲": "Lil",
        "福點": "⊗",
    }
    return symbol_map.get(name, "")


def check_api_key(x_api_key: Optional[str]):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


def normalize_plan(plan: Optional[str]) -> str:
    if not plan:
        return "free"

    plan = plan.lower().strip()

    if plan not in ["free", "starter", "standard", "deep"]:
        return "free"

    return plan


def normalize_degree(value: float) -> float:
    return value % 360.0


def zodiac_position(deg: float) -> Dict[str, str]:
    deg = normalize_degree(deg)
    sign_index = int(deg // 30)
    degree_in_sign = deg % 30

    d = int(degree_in_sign)
    m = int(round((degree_in_sign - d) * 60))

    if m >= 60:
        d += 1
        m -= 60

    if d >= 30:
        d -= 30
        sign_index = (sign_index + 1) % 12

    sign_tw, sign_en, glyph = ZODIAC_SIGNS[sign_index]

    return {
        "sign_tw": sign_tw,
        "sign_en": sign_en,
        "glyph": glyph,
        "degree_text": f"{d:02d}°{m:02d}′",
        "full_text": f"{sign_tw} {d:02d}°{m:02d}′",
    }


def degree_to_dms_text(deg: float) -> str:
    return zodiac_position(deg)["full_text"]


def parse_birth_datetime_utc(data: BirthInput) -> datetime:
    try:
        naive = datetime.strptime(f"{data.birth_date} {data.birth_time}", "%Y-%m-%d %H:%M")
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="出生日期或出生時間格式錯誤，請使用 YYYY-MM-DD 與 HH:MM。"
        )

    tz_name = data.timezone or "Asia/Taipei"

    if ZoneInfo is None:
        return naive

    try:
        local_dt = naive.replace(tzinfo=ZoneInfo(tz_name))
        return local_dt.astimezone(ZoneInfo("UTC"))
    except Exception:
        local_dt = naive.replace(tzinfo=ZoneInfo("Asia/Taipei"))
        return local_dt.astimezone(ZoneInfo("UTC"))


def get_location(data: BirthInput) -> Tuple[float, float, str]:
    if data.latitude is not None and data.longitude is not None:
        return float(data.latitude), float(data.longitude), data.timezone or "Asia/Taipei"

    place = data.birth_place or ""

    if place in CITY_FALLBACK:
        lat, lon, tz = CITY_FALLBACK[place]
        return lat, lon, data.timezone or tz

    return 25.0330, 121.5654, data.timezone or "Asia/Taipei"


def swiss_planet_id(name: str):
    mapping = {
        "SUN": swe.SUN,
        "MOON": swe.MOON,
        "MERCURY": swe.MERCURY,
        "VENUS": swe.VENUS,
        "MARS": swe.MARS,
        "JUPITER": swe.JUPITER,
        "SATURN": swe.SATURN,
        "URANUS": swe.URANUS,
        "NEPTUNE": swe.NEPTUNE,
        "PLUTO": swe.PLUTO,
    }
    return mapping[name]


def calc_ut_safe(jd_ut: float, body_id: int) -> float:
    try:
        result = swe.calc_ut(jd_ut, body_id, swe.FLG_SWIEPH)
        return normalize_degree(float(result[0][0]))
    except Exception:
        result = swe.calc_ut(jd_ut, body_id, swe.FLG_MOSEPH)
        return normalize_degree(float(result[0][0]))


def is_retrograde(jd_ut: float, body_id: int) -> bool:
    try:
        result = swe.calc_ut(jd_ut, body_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
        speed = float(result[0][3])
        return speed < 0
    except Exception:
        try:
            result = swe.calc_ut(jd_ut, body_id, swe.FLG_MOSEPH | swe.FLG_SPEED)
            speed = float(result[0][3])
            return speed < 0
        except Exception:
            return False


def angular_distance(a: float, b: float) -> float:
    diff = abs(normalize_degree(a) - normalize_degree(b))
    return min(diff, 360.0 - diff)


def orb_to_text(orb: float) -> str:
    d = int(orb)
    m = int(round((orb - d) * 60))

    if m >= 60:
        d += 1
        m -= 60

    return f"{d}°{m:02d}′"


def is_between_circular(value: float, start: float, end: float) -> bool:
    value = normalize_degree(value)
    start = normalize_degree(start)
    end = normalize_degree(end)

    if start <= end:
        return start <= value < end

    return value >= start or value < end


def find_house(degree: float, house_cusps: List[float]) -> int:
    for i in range(12):
        start = house_cusps[i]
        end = house_cusps[(i + 1) % 12]

        if is_between_circular(degree, start, end):
            return i + 1

    return 1


def calculate_part_of_fortune(asc: float, sun: float, moon: float) -> float:
    return normalize_degree(asc + moon - sun)


def calculate_aspects(points: List[Dict]) -> List[Dict]:
    aspect_defs = [
        ("合相", 0, 8),
        ("六分相", 60, 5),
        ("四分相", 90, 6),
        ("三分相", 120, 6),
        ("對分相", 180, 8),
    ]

    aspects = []

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            a = points[i]
            b = points[j]

            if a["name"] == "福點" or b["name"] == "福點":
                continue

            dist = angular_distance(a["degree"], b["degree"])

            for aspect_name, aspect_deg, orb_limit in aspect_defs:
                orb = abs(dist - aspect_deg)

                if orb <= orb_limit:
                    aspects.append({
                        "p1": a["name"],
                        "p2": b["name"],
                        "aspect": aspect_name,
                        "aspect_deg": aspect_deg,
                        "orb": orb,
                        "orb_text": orb_to_text(orb),
                    })
                    break

    aspects.sort(key=lambda x: x["orb"])
    return aspects[:16]


def calculate_chart(data: BirthInput) -> Dict:
    if not SWISS_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Render 尚未安裝 Swiss Ephemeris。請在 requirements.txt 加入 pyswisseph 後重新部署。"
        )

    lat, lon, tz_name = get_location(data)
    utc_dt = parse_birth_datetime_utc(data)

    jd_ut = swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )

    try:
        houses_result = swe.houses_ex(jd_ut, lat, lon, b"P")
    except TypeError:
        houses_result = swe.houses_ex(jd_ut, lat, lon, hsys=b"P")

    house_cusps = [normalize_degree(float(x)) for x in houses_result[0][:12]]
    ascmc = houses_result[1]

    asc = normalize_degree(float(ascmc[0]))
    mc = normalize_degree(float(ascmc[1]))
    desc = normalize_degree(asc + 180.0)
    ic = normalize_degree(mc + 180.0)

    planets = []

    for tw_name, en_name, glyph, swiss_name in PLANET_DEFS:
        planet_id = swiss_planet_id(swiss_name)
        deg = calc_ut_safe(jd_ut, planet_id)
        retro = is_retrograde(jd_ut, planet_id)

        planets.append({
            "name": tw_name,
            "en_name": en_name,
            "glyph": glyph,
            "degree": deg,
            "position": degree_to_dms_text(deg),
            "house": find_house(deg, house_cusps),
            "status": "逆行" if retro else "",
        })

    extra_points = []

    try:
        node_deg = calc_ut_safe(jd_ut, swe.TRUE_NODE)
        extra_points.append({
            "name": "北交點",
            "en_name": "North Node",
            "glyph": "☊",
            "degree": node_deg,
            "position": degree_to_dms_text(node_deg),
            "house": find_house(node_deg, house_cusps),
            "status": "",
        })

        south_deg = normalize_degree(node_deg + 180.0)
        extra_points.append({
            "name": "南交點",
            "en_name": "South Node",
            "glyph": "☋",
            "degree": south_deg,
            "position": degree_to_dms_text(south_deg),
            "house": find_house(south_deg, house_cusps),
            "status": "",
        })
    except Exception:
        pass

    try:
        lilith_deg = calc_ut_safe(jd_ut, swe.MEAN_APOG)
        extra_points.append({
            "name": "莉莉絲",
            "en_name": "Lilith",
            "glyph": "Lil",
            "degree": lilith_deg,
            "position": degree_to_dms_text(lilith_deg),
            "house": find_house(lilith_deg, house_cusps),
            "status": "",
        })
    except Exception:
        pass

    try:
        chiron_deg = calc_ut_safe(jd_ut, swe.CHIRON)
        extra_points.append({
            "name": "凱龍星",
            "en_name": "Chiron",
            "glyph": "Ch",
            "degree": chiron_deg,
            "position": degree_to_dms_text(chiron_deg),
            "house": find_house(chiron_deg, house_cusps),
            "status": "",
        })
    except Exception:
        pass

    sun_deg = next(p["degree"] for p in planets if p["name"] == "太陽")
    moon_deg = next(p["degree"] for p in planets if p["name"] == "月亮")
    fortune_deg = calculate_part_of_fortune(asc, sun_deg, moon_deg)

    extra_points.append({
        "name": "福點",
        "en_name": "Part of Fortune",
        "glyph": "⊗",
        "degree": fortune_deg,
        "position": degree_to_dms_text(fortune_deg),
        "house": find_house(fortune_deg, house_cusps),
        "status": "",
    })

    all_points = planets + extra_points

    angles = {
        "ASC 上升": asc,
        "DSC 下降": desc,
        "MC 天頂": mc,
        "IC 天底": ic,
    }

    aspects = calculate_aspects(all_points)

    return {
        "jd_ut": jd_ut,
        "utc_datetime": utc_dt,
        "latitude": lat,
        "longitude": lon,
        "timezone": tz_name,
        "planets": planets,
        "extra_points": extra_points,
        "all_points": all_points,
        "house_cusps": house_cusps,
        "angles": angles,
        "asc": asc,
        "mc": mc,
        "aspects": aspects,
    }


class NatalChartFlowable(Flowable):
    def __init__(self, chart: Dict, size: float = 13.8 * cm):
        Flowable.__init__(self)
        self.chart = chart
        self.width = size
        self.height = size
        self.size = size

    def angle_to_xy(self, deg: float, radius: float):
        asc = self.chart["asc"]
        display_deg = 180.0 - normalize_degree(deg - asc)
        rad = math.radians(display_deg)
        x = self.size / 2 + math.cos(rad) * radius
        y = self.size / 2 + math.sin(rad) * radius
        return x, y

    def draw_centered_text(self, text, x, y, font_size=7, color=colors.black):
        c = self.canv
        c.setFont("STSong-Light", font_size)
        c.setFillColor(color)
        c.drawCentredString(x, y - font_size / 3, text)

    def draw(self):
        c = self.canv
        size = self.size
        cx = size / 2
        cy = size / 2

        outer_r = size * 0.47
        zodiac_r = size * 0.42
        house_r = size * 0.32
        aspect_r = size * 0.24
        planet_r = size * 0.365

        c.setStrokeColor(colors.HexColor("#222222"))
        c.setLineWidth(1.2)
        c.circle(cx, cy, outer_r)
        c.circle(cx, cy, zodiac_r)
        c.circle(cx, cy, house_r)
        c.circle(cx, cy, aspect_r)

        for i in range(12):
            deg = i * 30
            x1, y1 = self.angle_to_xy(deg, zodiac_r)
            x2, y2 = self.angle_to_xy(deg, outer_r)

            c.setStrokeColor(colors.HexColor("#B8B8B8"))
            c.setLineWidth(0.6)
            c.line(x1, y1, x2, y2)

            label_deg = deg + 15
            lx, ly = self.angle_to_xy(label_deg, outer_r - 13)

            sign_tw = ZODIAC_SIGNS[i][0]
            sign_symbol = ZODIAC_SIGNS[i][2]

            self.draw_centered_text(sign_symbol, lx, ly + 4, 10, colors.HexColor("#8A6B28"))
            self.draw_centered_text(sign_tw[:2], lx, ly - 8, 6.5, colors.HexColor("#8A6B28"))

        for i, cusp in enumerate(self.chart["house_cusps"]):
            x1, y1 = self.angle_to_xy(cusp, aspect_r)
            x2, y2 = self.angle_to_xy(cusp, zodiac_r)

            c.setStrokeColor(colors.HexColor("#888888"))
            c.setLineWidth(0.6)
            c.line(x1, y1, x2, y2)

            label_deg = cusp + 12
            lx, ly = self.angle_to_xy(label_deg, house_r - 12)
            self.draw_centered_text(str(i + 1), lx, ly, 7, colors.HexColor("#333333"))

        for angle_name, deg in self.chart["angles"].items():
            x1, y1 = self.angle_to_xy(deg, aspect_r)
            x2, y2 = self.angle_to_xy(deg, outer_r + 10)

            c.setStrokeColor(colors.black)
            c.setLineWidth(1.5)
            c.line(x1, y1, x2, y2)

            lx, ly = self.angle_to_xy(deg, outer_r + 23)
            self.draw_centered_text(angle_name.split()[0], lx, ly, 8, colors.black)

        placed_count = {}

        for p in self.chart["all_points"]:
            key = int(round(p["degree"] / 3.0))
            placed_count[key] = placed_count.get(key, 0) + 1
            offset = (placed_count[key] - 1) * 10

            px, py = self.angle_to_xy(p["degree"], planet_r - offset)

            symbol = p.get("glyph", "") or symbol_for_point(p["name"])

            if not symbol:
                symbol = p["name"][:2]

            self.draw_centered_text(symbol, px, py + 2, 10, colors.HexColor("#7A1E1E"))

        aspect_colors = {
            0: colors.HexColor("#444444"),
            60: colors.HexColor("#4C9A65"),
            90: colors.HexColor("#D34A4A"),
            120: colors.HexColor("#3E64C8"),
            180: colors.HexColor("#D34A4A"),
        }

        for asp in self.chart["aspects"][:14]:
            p1 = next((p for p in self.chart["all_points"] if p["name"] == asp["p1"]), None)
            p2 = next((p for p in self.chart["all_points"] if p["name"] == asp["p2"]), None)

            if not p1 or not p2:
                continue

            x1, y1 = self.angle_to_xy(p1["degree"], aspect_r)
            x2, y2 = self.angle_to_xy(p2["degree"], aspect_r)

            c.setStrokeColor(aspect_colors.get(asp["aspect_deg"], colors.grey))
            c.setLineWidth(0.45)
            c.line(x1, y1, x2, y2)

        c.setFont("STSong-Light", 8)
        c.setFillColor(colors.HexColor("#2B2414"))
        c.drawCentredString(cx, cy - 3, "本命星盤")


def build_small_table(data, col_widths):
    table = Table(data, colWidths=col_widths)

    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFE6C8")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8B77A")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    return table


def get_core_summary(chart: Dict) -> str:
    sun = next((p for p in chart["planets"] if p["name"] == "太陽"), None)
    moon = next((p for p in chart["planets"] if p["name"] == "月亮"), None)

    asc = chart["angles"]["ASC 上升"]

    sun_sign = zodiac_position(sun["degree"])["sign_tw"] if sun else ""
    moon_sign = zodiac_position(moon["degree"])["sign_tw"] if moon else ""
    asc_sign = zodiac_position(asc)["sign_tw"]

    return (
        f"這張命盤以 {sun_sign} 太陽、{moon_sign} 月亮、{asc_sign} 上升為核心。"
        "免費版先提供本命星盤圖、星體位置、四軸與主要相位。"
        "完整付費版可進一步解讀財富模式、事業方向、感情合作、流年與年度策略。"
    )


def generate_ai_advice(chart: Dict) -> List[Tuple[str, str]]:
    def get_plan_label(plan: str) -> str:
    labels = {
        "free": "免費排出星盤｜NT$0｜引流體驗",
        "starter": "入門星盤報告｜NT$199｜低門檻付費",
        "standard": "AI 財富命盤標準報告｜NT$499｜主力商品",
        "deep": "年度深度命盤全書｜NT$999｜高單價完整報告",
    }
    return labels.get(plan, labels["free"])


def get_paid_sections(plan: str, chart: Dict) -> List[Tuple[str, str]]:
    sun = next((p for p in chart["planets"] if p["name"] == "太陽"), None)
    moon = next((p for p in chart["planets"] if p["name"] == "月亮"), None)
    mercury = next((p for p in chart["planets"] if p["name"] == "水星"), None)
    venus = next((p for p in chart["planets"] if p["name"] == "金星"), None)
    mars = next((p for p in chart["planets"] if p["name"] == "火星"), None)
    jupiter = next((p for p in chart["planets"] if p["name"] == "木星"), None)
    saturn = next((p for p in chart["planets"] if p["name"] == "土星"), None)

    asc_text = degree_to_dms_text(chart["angles"]["ASC 上升"])
    mc_text = degree_to_dms_text(chart["angles"]["MC 天頂"])

    sun_text = f"{sun['position']} 第{sun['house']}宮" if sun else "資料不足"
    moon_text = f"{moon['position']} 第{moon['house']}宮" if moon else "資料不足"
    mercury_text = f"{mercury['position']} 第{mercury['house']}宮" if mercury else "資料不足"
    venus_text = f"{venus['position']} 第{venus['house']}宮" if venus else "資料不足"
    mars_text = f"{mars['position']} 第{mars['house']}宮" if mars else "資料不足"
    jupiter_text = f"{jupiter['position']} 第{jupiter['house']}宮" if jupiter else "資料不足"
    saturn_text = f"{saturn['position']} 第{saturn['house']}宮" if saturn else "資料不足"

    top_aspects = chart.get("aspects", [])[:5]
    aspect_text = "、".join([
        f"{a['p1']} {a['aspect']} {a['p2']}（容許度 {a['orb_text']}）"
        for a in top_aspects
    ]) or "主要相位資料不足"

    if plan == "starter":
        return [
            (
                "命盤三大核心主題",
                f"你的命盤可以先從三個核心來看：第一，太陽位於 {sun_text}，代表人生目標與自我認同；第二，月亮位於 {moon_text}，代表情緒需求與安全感來源；第三，上升位於 {asc_text}，代表你面對世界的外在方式。入門版的重點，是先讓你掌握自己的基本人格、優勢與需要調整的方向。"
            ),
            (
                "核心人格：太陽 / 月亮 / 上升",
                f"太陽顯示你想成為什麼樣的人，月亮顯示你真正需要什麼，上升顯示別人第一眼如何感受到你。當太陽 {sun_text}、月亮 {moon_text}、上升 {asc_text} 同時運作時，你的人生會在自我要求、情緒需求與外在表達之間找到平衡。"
            ),
            (
                "星體位置快速解讀",
                f"水星位於 {mercury_text}，影響你的思考與表達；金星位於 {venus_text}，影響感情、審美與價值交換；火星位於 {mars_text}，代表行動力、慾望與界線。這些星體組合顯示，你需要找到適合自己的節奏，而不是照別人的期待生活。"
            ),
            (
                "性格優勢與盲點",
                f"你的優勢來自於能把不同經驗整合成自己的判斷，但盲點是容易在壓力、關係或金錢議題中忽略真正需求。主要相位可參考：{aspect_text}。這些相位提醒你，人生不是只有單一方向，而是需要學會調整內在拉扯。"
            ),
            (
                "入門行動建議",
                "建議先做三件事：第一，確認自己真正重視的價值；第二，建立穩定的工作與生活節奏；第三，避免在情緒波動時做重大金錢或關係決定。這份入門報告適合當作自我認識的第一步。"
            ),
        ]

    if plan == "standard":
        return [
            (
                "命盤三大核心結論",
                f"第一，你的內在運作由太陽 {sun_text}、月亮 {moon_text} 與上升 {asc_text} 共同構成，代表你需要在自我要求、情緒安全與外在表達之間建立穩定整合。第二，財富與事業不能只看短期機會，還要看金星 {venus_text}、木星 {jupiter_text}、土星 {saturn_text} 與 MC {mc_text} 的長期結構。第三，關係與成熟方向會受到主要相位與交點課題影響，這些會決定你如何從重複模式中長大。"
            ),
            (
                "核心性格的立體透視：太陽、月亮、上升",
                f"這一章回答的是：你真正是如何運作的人。太陽 {sun_text} 代表你想建立的人生方向，月亮 {moon_text} 代表你內在真正需要的安全感，上升 {asc_text} 代表你如何進入世界。當這三者互相拉扯時，你可能會一邊想追求秩序與成果，一邊又需要自由、理解與被看見。實際建議是：不要只靠意志硬撐，也要建立能照顧情緒的生活結構。"
            ),
            (
                "思維與表達：水星的運作模式",
                f"水星位於 {mercury_text}，顯示你的思考方式、學習能力與表達習慣。這代表你適合把複雜資訊整理成系統，也適合做分析、寫作、研究、顧問或需要精準表達的工作。盲點是容易想太多，或在情緒壓力下反覆檢查。建議把腦中的資訊外化成筆記、流程、表格或產品。"
            ),
            (
                "感情與吸引力：金星與月亮",
                f"金星位於 {venus_text}，月亮位於 {moon_text}。金星代表你喜歡什麼、如何吸引他人，也代表價值交換；月亮代表你真正的情緒需求。這組合顯示你在關係中不能只追求表面和諧，也要能被理解、被尊重。感情上的成熟關鍵，是學會清楚說出需求，而不是用退讓或控制來維持關係。"
            ),
            (
                "行動力與慾望：火星",
                f"火星位於 {mars_text}，代表你的行動方式、競爭心與界線。這顯示你需要有可以主動表現的舞台，也需要被允許用自己的方式做決定。若火星能量被壓抑，容易變成急躁、拖延或突然爆發。實際建議是：把行動力導向可累積的專案，而不是短期情緒反應。"
            ),
            (
                "財富模式：第2宮、第8宮、金星、木星",
                f"財富模式要同時看收入能力、資源交換與長期機會。金星 {venus_text} 顯示你的價值交換方式，木星 {jupiter_text} 顯示機會來源，土星 {saturn_text} 顯示需要負責與累積的地方。你的金錢策略不適合只靠運氣，而適合透過專業能力、內容、服務、顧問、系統化流程或長期資源管理來累積。"
            ),
            (
                "事業方向：MC、第10宮、土星與木星",
                f"MC 位於 {mc_text}，代表社會角色與事業定位。搭配木星 {jupiter_text} 與土星 {saturn_text}，你的事業發展需要兼顧創新、專業、制度與長期累積。適合的方向包括知識服務、資料分析、科技工具、顧問型服務、內容產品、身心靈與策略整合。避免只做沒有累積性的短期工作。"
            ),
            (
                "主要相位與內在動力",
                f"主要相位顯示內在推力與拉扯，目前重要相位包括：{aspect_text}。相位不是好壞，而是能量如何互相影響。緊張相位會帶來壓力，但也會逼你成長；和諧相位會帶來天賦，但若不用也會浪費。建議把相位視為人生的操作說明書。"
            ),
            (
                "南北交點、莉莉絲與凱龍星",
                "南北交點代表舊模式與新方向，莉莉絲代表被壓抑的慾望與界線，凱龍星代表傷口與可轉化的天賦。這一組不是單純的神秘點，而是你人生中容易反覆出現的深層課題。真正的成長，是不再被舊模式牽著走，而是把傷口轉成洞察力，把陰影轉成界線。"
            ),
            (
                "風險提醒與實際行動建議",
                "你的風險不是沒有能力，而是容易在壓力、關係或金錢選擇中同時想要太多方向。建議建立三層策略：第一，穩定現金流；第二，把能力產品化；第三，建立長期資產與可複製流程。避免保證式投資、情緒消費與沒有邊界的合作。"
            ),
            (
                "總結：如何用這張命盤做人生決策",
                "這張命盤不是要限制你，而是幫你看見自己的運作模式。當你知道自己的核心需求、行動方式、財富模式與關係課題，就能少走一些重複的路。真正好的命盤使用方式，是把它變成決策工具：知道何時累積、何時表達、何時合作、何時止損。"
            ),
        ]

    if plan == "deep":
        return [
            (
                "命盤三大核心主題",
                f"第一主題是人格結構：太陽 {sun_text}、月亮 {moon_text}、上升 {asc_text} 形成你的基本人生運作。第二主題是現實成就：MC {mc_text}、木星 {jupiter_text}、土星 {saturn_text} 顯示你如何建立事業、責任與長期成果。第三主題是深層轉化：主要相位、南北交點、莉莉絲與凱龍星會反覆推動你面對關係、資源與自我價值的成熟課題。"
            ),
            (
                "第一部分：命盤深度解剖與靈魂結構分析",
                "深度版不是只看單一星體，而是看整張命盤如何互相牽動。太陽代表人生方向，月亮代表情緒底層，上升代表你如何進入世界；宮位代表人生場景，相位代表內在動力，交點與特殊點則代表長期課題。這些合起來，才是完整的命盤故事。"
            ),
            (
                "核心性格的立體透視：日月升的三角張力",
                f"太陽 {sun_text}、月亮 {moon_text}、上升 {asc_text} 是這張命盤的三角骨架。你可能一方面想把生活整理得有秩序，一方面又需要精神自由與情緒空間。外在表達可能比內在更靈活，但內心其實需要穩定、安全與可掌握感。"
            ),
            (
                "行星落點與人格功能",
                f"水星 {mercury_text} 影響你的學習與表達；金星 {venus_text} 影響關係與價值交換；火星 {mars_text} 影響行動力；木星 {jupiter_text} 帶來擴張機會；土星 {saturn_text} 要求你成熟與負責。這些功能若能整合，你會更適合發展可長期累積的專業系統。"
            ),
            (
                "宮位重心與人生主場景",
                "宮位顯示人生能量集中在哪些領域。若多顆星集中在某些宮位，代表這些領域會成為人生反覆學習的主場景。你需要觀察哪些議題總是重複出現：家庭、關係、工作、財富、精神探索或社會定位，這些就是命盤要你整理的核心功課。"
            ),
            (
                "主要相位與內在動力",
                f"目前主要相位包括：{aspect_text}。深度版會把相位視為內在角色之間的對話。某些相位帶來天賦，某些相位帶來壓力，但真正的重點不是好壞，而是你能否把矛盾變成推動力。"
            ),
            (
                "四個交點與人生十字軸",
                f"ASC {asc_text}、DSC {degree_to_dms_text(chart['angles']['DSC 下降'])}、MC {mc_text}、IC {degree_to_dms_text(chart['angles']['IC 天底'])} 形成你的人生十字軸。它同時描述自我、關係、家庭根基與社會成就。當這四軸清楚，你會更知道什麼是自己的路，什麼只是外界期待。"
            ),
            (
                "南北交點、黑月莉莉絲與凱龍星",
                "南交點代表熟悉但容易卡住的模式，北交點代表今生要發展的新能力。莉莉絲顯示你不願被控制或被壓抑的地方，凱龍星顯示傷口如何轉化成天賦。深度版的重點，是把這些點看成一條成熟主線，而不是零散名詞。"
            ),
            (
                "感情模式與互動方式",
                f"感情模式需要看月亮 {moon_text}、金星 {venus_text} 與第七宮軸線。你在關係中需要的不只是吸引力，也需要理解、尊重與可對話的空間。成熟關係不是完全沒有衝突，而是能把需求說清楚，並建立雙方都能承擔的界線。"
            ),
            (
                "事業發展與社會定位",
                f"事業定位以 MC {mc_text} 為核心，並參考木星 {jupiter_text} 與土星 {saturn_text}。你適合建立自己的專業識別，而不是一直追逐別人的模式。長期來看，可發展顧問、內容、分析、科技、身心靈策略或系統整合型服務。"
            ),
            (
                "財富運作與資源整合策略",
                f"財富不是單純賺多少，而是資源如何流動。金星 {venus_text} 顯示價值交換，木星 {jupiter_text} 顯示機會擴張，土星 {saturn_text} 顯示限制與責任。建議把收入分成穩定現金流、專業產品化、長期資產三層。"
            ),
            (
                "健康節律與日常修復模式",
                "健康在占星報告中只作生活節律參考，不作醫療判斷。你的修復關鍵在於規律、睡眠、情緒排放與工作節奏。當壓力累積時，身體會提醒你需要放慢、整理與重新分配能量。"
            ),
            (
                "長周期運勢與年度轉折框架",
                "年度策略不是預言事件，而是安排節奏。你可以把一年分成整理期、推進期、檢討期與擴張期。當命盤中的土星、木星或食相觸動重要位置時，適合重新檢查責任、機會與方向。"
            ),
            (
                "逐月行動曆與季度策略",
                "第一季適合整理資料、修正定位與建立基本流程；第二季適合測試產品、增加曝光與建立合作；第三季適合檢查成效、調整價格與優化服務；第四季適合整合成果、沉澱品牌與規劃下一年度。這是策略地圖，不是保證事件。"
            ),
            (
                "深層課題與成熟方向",
                "你的深層課題是學會把敏感、壓力、慾望與責任整合成自己的力量。成熟不是壓抑自己，而是知道什麼時候表達、什麼時候等待、什麼時候切割不適合的人事物。"
            ),
            (
                "整體閱讀總結與後續建議",
                "深度命盤的價值在於讓你看見長期模式。建議每三個月回來重讀一次：第一次看人格，第二次看財富，第三次看關係，第四次看年度策略。命盤不是一次看完就結束，而是可以反覆使用的人生地圖。"
            ),
        ]

    return []
    mc_sign = zodiac_position(chart["angles"]["MC 天頂"])["full_text"]

    return [
        (
            "財運模式",
            "財富模式不適合只靠短線衝動，而適合把個人專長、知識、服務能力與長期規劃轉成穩定收入。"
        ),
        (
            "事業方向",
            f"事業方向可參考天頂 {mc_sign}。適合發展專業服務、內容分析、顧問、創意或需要判斷力與系統能力並用的領域。"
        ),
        (
            "風險提醒",
            "主要風險在於情緒壓力、過度理想化，或在關係與資源合作中缺乏界線。建議所有財務與合作都要建立清楚規則。"
        ),
        (
            "感情模式",
            "感情模式重視安全感與理解，需要能溝通、能互相支持的關係。若壓抑需求，容易在關係中累積不滿。"
        ),
    ]


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <meta charset="utf-8">
    <h1>AI 財富命盤 API 已上線</h1>
    <p><a href="/form">前往測試表單頁</a></p>
    <p><a href="/success">付款成功測試頁</a></p>
    <p><a href="/docs">API Docs</a></p>
    """


@app.get("/form", response_class=HTMLResponse)
def form_page():
    return f"""
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>AI 財富命盤報告生成器</title>
</head>
<body>
  <h1>AI 財富命盤報告生成器</h1>
  <p>正式網站表單請使用 WordPress 頁面。</p>
  <p><a href="{PAYMENT_PAGE_URL}">付款成功測試頁</a></p>
</body>
</html>
    """


@app.get("/success", response_class=HTMLResponse)
def success_page():
    return """
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>付款成功</title>
</head>
<body>
  <h1>付款成功測試頁</h1>
  <p>正式綠界或其他金流串接完成後，這裡會接收付款成功 token 並產生付費報告。</p>
</body>
</html>
    """


@app.post("/api/generate-report")
def generate_report(data: BirthInput, x_api_key: Optional[str] = Header(None)):
    check_api_key(x_api_key)

    plan = normalize_plan(data.plan)

    if plan != "free":
        if not data.token or data.token != "PAID_OK":
            raise HTTPException(status_code=403, detail="請先完成付款")

    chart = calculate_chart(data)

    filename = f"wealth_report_{str(uuid.uuid4())[:8]}.pdf"
    path = os.path.join(OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=1.45 * cm,
        leftMargin=1.45 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.35 * cm,
    )

    title = ParagraphStyle(
        "Title",
        fontName="STSong-Light",
        fontSize=22,
        leading=30,
        alignment=1,
        textColor=colors.HexColor("#2B2414"),
        spaceAfter=8,
    )

    subtitle = ParagraphStyle(
        "Subtitle",
        fontName="STSong-Light",
        fontSize=10.5,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#5F5437"),
        spaceAfter=16,
    )

    header = ParagraphStyle(
        "Header",
        fontName="STSong-Light",
        fontSize=14,
        leading=21,
        spaceBefore=12,
        spaceAfter=7,
        textColor=colors.HexColor("#2B2414"),
    )

    body = ParagraphStyle(
        "Body",
        fontName="STSong-Light",
        fontSize=10.5,
        leading=17,
        spaceAfter=7,
        textColor=colors.black,
    )

    small = ParagraphStyle(
        "Small",
        fontName="STSong-Light",
        fontSize=8.5,
        leading=13,
        spaceAfter=5,
        textColor=colors.HexColor("#5F5437"),
    )

    content = []

    utc_text = chart["utc_datetime"].isoformat()

   content.append(Paragraph("專業本命星盤 × AI占星顧問報告", title))
content.append(Paragraph(get_plan_label(plan), subtitle))
    content.append(Paragraph(
        f"姓名：{data.name or '未填'}　出生：{data.birth_date} {data.birth_time}　地點：{data.birth_place}　性別：{data.gender or '未填'}<br/>"
        f"系統：熱帶黃道 / Placidus　時區：{chart['timezone']}　UTC：{utc_text}",
        subtitle,
    ))

    left_rows = [
        ["出生資料", ""],
        ["姓名", data.name or "未填"],
        ["生日", data.birth_date],
        ["時間", data.birth_time],
        ["地點", data.birth_place],
        ["性別", data.gender or "未填"],
        ["系統", "熱帶黃道 / Placidus"],
    ]

    planet_rows = [["星體", "位置", "宮位"]]

    for p in chart["all_points"]:
        symbol = p.get("glyph", "") or symbol_for_point(p["name"])
        display_name = f"{symbol} {p['name']}".strip()

        planet_rows.append([
            display_name,
            p["position"],
            f"第{p['house']}宮",
        ])

    angle_rows = [["四軸", "位置"]]

    for name, deg in chart["angles"].items():
        angle_rows.append([name, degree_to_dms_text(deg)])

    left_table = build_small_table(left_rows, [2.2 * cm, 5.6 * cm])
    planet_table = build_small_table(planet_rows, [2.0 * cm, 3.7 * cm, 2.1 * cm])
    angle_table = build_small_table(angle_rows, [2.6 * cm, 5.2 * cm])

    left_block = Table(
        [
            [left_table],
            [Spacer(1, 8)],
            [planet_table],
            [Spacer(1, 8)],
            [angle_table],
        ],
        colWidths=[8.1 * cm],
    )

    chart_block = NatalChartFlowable(chart, size=11.5 * cm)

    cover_table = Table(
        [[left_block, chart_block]],
        colWidths=[8.2 * cm, 11.2 * cm],
    )

    cover_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C8B77A")),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#E0D4AA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    content.append(cover_table)
    content.append(PageBreak())

    content.append(Paragraph("一、核心命盤定位", header))
    content.append(Paragraph(get_core_summary(chart), body))

    content.append(Paragraph("二、星體位置表", header))

    full_planet_rows = [["星體", "星座位置", "宮位", "狀態"]]

    for p in chart["all_points"]:
        symbol = p.get("glyph", "") or symbol_for_point(p["name"])
        display_name = f"{symbol} {p['name']}".strip()

        full_planet_rows.append([
            display_name,
            p["position"],
            f"第{p['house']}宮",
            p.get("status", ""),
        ])

    full_planet_table = build_small_table(
        full_planet_rows,
        [3.0 * cm, 6.2 * cm, 3.0 * cm, 3.0 * cm],
    )

    content.append(full_planet_table)

    content.append(Paragraph("三、四軸位置", header))

    full_angle_rows = [["四軸", "星座位置"]]

    for name, deg in chart["angles"].items():
        full_angle_rows.append([name, degree_to_dms_text(deg)])

    full_angle_table = build_small_table(
        full_angle_rows,
        [4.5 * cm, 8.0 * cm],
    )

    content.append(full_angle_table)
    content.append(PageBreak())

    content.append(Paragraph("四、主要相位", header))

    aspect_rows = [["相位", "容許度"]]

    if chart["aspects"]:
        for asp in chart["aspects"]:
            aspect_rows.append([
                f"{asp['p1']} {asp['aspect_deg']}° {asp['p2']}｜{asp['aspect']}",
                asp["orb_text"],
            ])
    else:
        aspect_rows.append(["主要相位資料不足", "-"])

    aspect_table = build_small_table(
        aspect_rows,
        [11.5 * cm, 4.0 * cm],
    )

    content.append(aspect_table)

    if plan == "free":
    content.append(Paragraph("五、AI占星顧問式解讀", header))

    for h, t in generate_ai_advice(chart):
        content.append(Paragraph(f"{h}：{t}", body))

    content.append(Spacer(1, 12))
    content.append(Paragraph("免費版升級提示", header))
    content.append(Paragraph(
        "此免費版提供完整排盤資料、星體位置、四軸與主要相位。完整付費版將加入財富宮位、職涯策略、感情合作、流年重點與更完整的 AI 深度解盤。",
        body,
    ))
else:
    content.append(Paragraph("五、付費版深度解讀", header))

    paid_sections = get_paid_sections(plan, chart)

    for section_title, section_text in paid_sections:
        content.append(Paragraph(section_title, header))
        content.append(Paragraph(section_text, body))
        content.append(Spacer(1, 12))
        content.append(Paragraph("免費版升級提示", header))
        content.append(Paragraph(
            "此免費版提供完整排盤資料、星體位置、四軸與主要相位。完整付費版將加入財富宮位、職涯策略、感情合作、流年重點與更完整的 AI 深度解盤。",
            body,
        ))

    content.append(Spacer(1, 16))
    content.append(Paragraph(
        "免責聲明：本報告為占星與個人策略分析用途，不構成投資建議、法律建議、醫療建議或任何保證性承諾。",
        small,
    ))

    doc.build(content)

    download_url = f"{BASE_URL}/reports/{filename}"

    return {
        "status": "success",
        "plan": plan,
        "download_url": download_url,
        "filename": filename,
    }
