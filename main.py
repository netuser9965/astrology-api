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

app = FastAPI(title="Secure Astrology Report API")
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
CITY_FALLBACK = {
    "台北": (25.0330, 121.5654, "Asia/Taipei"),
    "台北市，台灣": (25.0330, 121.5654, "Asia/Taipei"),
    "台中": (24.1477, 120.6736, "Asia/Taipei"),
    "台中市，台灣": (24.1477, 120.6736, "Asia/Taipei"),
    "東京": (35.6895, 139.6917, "Asia/Tokyo"),
    "東京，日本": (35.6895, 139.6917, "Asia/Tokyo"),
    "紐約": (40.7128, -74.0060, "America/New_York"),
    "紐約，美國": (40.7128, -74.0060, "America/New_York"),
    "倫敦": (51.5072, -0.1276, "Europe/London"),
    "倫敦，英國": (51.5072, -0.1276, "Europe/London"),
    "香港": (22.3193, 114.1694, "Asia/Hong_Kong"),
    "新加坡": (1.3521, 103.8198, "Asia/Singapore"),
    "首爾，韓國": (37.5665, 126.9780, "Asia/Seoul"),
}


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
        raise HTTPException(status_code=422, detail="出生日期或出生時間格式錯誤，請使用 YYYY-MM-DD 與 HH:MM。")

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


def angular_distance(a: float, b: float) -> float:
    diff = abs(normalize_degree(a) - normalize_degree(b))
    return min(diff, 360.0 - diff)


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

            if a["name"] in ["福點"] or b["name"] in ["福點"]:
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


def orb_to_text(orb: float) -> str:
    d = int(orb)
    m = int(round((orb - d) * 60))
    if m >= 60:
        d += 1
        m -= 60
    return f"{d}°{m:02d}′"


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
            "glyph": "Lilith",
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
        "glyph": "福",
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
            lx, ly = self.angle_to_xy(label_deg, outer_r - 12)
            sign_tw = ZODIAC_SIGNS[i][0]
            self.draw_centered_text(sign_tw[:2], lx, ly, 8, colors.HexColor("#8A6B28"))

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
            short_name = p["name"][:2]
            self.draw_centered_text(short_name, px, py, 7, colors.HexColor("#7A1E1E"))

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
            c.setLineWidth(0.4)
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
        "整體人格結構同時包含內在需求、外在表達與現實行動模式。免費版先呈現完整排盤資料，"
        "付費版會進一步加入財運、事業、感情、相位與年度策略。"
    )


def generate_ai_advice(chart: Dict) -> List[Tuple[str, str]]:
    mc_sign = zodiac_position(chart["angles"]["MC 天頂"])["full_text"]

    return [
        (
            "財運模式",
            "財富模式不適合只靠短線衝動，而適合把個人專長、知識、服務能力與長期規劃轉成穩定收入。若能建立系統化方法，財務累積會比單次機會更重要。"
        ),
        (
            "事業方向",
            f"事業方向可參考天頂 {mc_sign}。適合發展專業服務、內容分析、顧問、創意、資料整合或需要判斷力與系統能力並用的領域。"
        ),
        (
            "風險提醒",
            "主要風險在於情緒壓力、過度理想化、或在關係與資源合作中缺乏邊界。建議所有財務與合作都要建立清楚規則。"
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
    <p><a href="/form">前往正式表單頁</a></p>
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
    return f"""
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>付款成功</title>
</head>
<body>
  <h1>付款成功測試頁</h1>
  <p>正式綠界串接完成後，這裡會接收付款成功 token 並產生付費報告。</p>
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
        planet_rows.append([
            p["name"],
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
        full_planet_rows.append([
            p["name"],
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

    content.append(Paragraph("五、AI占星顧問式解讀", header))
    for h, t in generate_ai_advice(chart):
        content.append(Paragraph(f"{h}：{t}", body))

    if plan == "free":
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
