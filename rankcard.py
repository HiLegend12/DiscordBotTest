import unicodedata
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from config import FONT_PATH, MINING_XP_BASE

MINING_COLOUR = (230, 160, 40)


def _progress(xp: int, level: int, base: int) -> tuple[int, int, float]:
    """Return (xp_into_level, xp_range, percentage 0.0-1.0) for a level curve."""
    current_level_xp = base * ((level - 1) ** 2) if level > 0 else 0
    needed_xp = base * (level**2)
    xp_into_level = xp - current_level_xp
    xp_range = needed_xp - current_level_xp
    percentage = xp_into_level / xp_range if xp_range > 0 else 0
    return xp_into_level, xp_range, max(0.0, min(percentage, 1.0))


def _draw_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    percentage: float,
    colour: tuple[int, int, int],
    width: int = 500,
    height: int = 30,
) -> None:
    """Draw a rounded progress bar: dark track plus a coloured fill."""
    draw.rounded_rectangle([x, y, x + width, y + height], radius=15, fill=(30, 31, 34))
    fill_width = int(width * percentage)
    if fill_width > 15:
        draw.rounded_rectangle(
            [x, y, x + fill_width, y + height], radius=15, fill=colour
        )


def generate_rank_card(
    username: str,
    avatar_bytes: bytes,
    xp: int,
    level: int,
    user_colour: tuple[int, int, int],
    streak: int,
    mining_xp: int,
    mining_level: int,
) -> BytesIO:
    background = Image.new("RGB", (800, 360), color=(43, 45, 49))  # was 800x250
    draw = ImageDraw.Draw(background)

    try:
        font_large = ImageFont.truetype(FONT_PATH, 40)
        font_small = ImageFont.truetype(FONT_PATH, 25)
    except OSError as e:
        print(f"Font was unable to load: {e}")
        font_large = ImageFont.load_default(size=40)
        font_small = ImageFont.load_default(size=25)

    clean_username = username.replace("\u0454", "e").replace("∂", "d")
    clean_username = unicodedata.normalize("NFKC", clean_username)

    # Avatar
    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((150, 150))
    mask = Image.new("L", (150, 150), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 150, 150), fill=255)
    background.paste(avatar, (40, 50), mask)

    grey = (185, 187, 190)

    # --- Chat level section ---
    xp_into_level, xp_range, percentage = _progress(xp, level, 100)
    draw.text((230, 50), clean_username, font=font_large, fill=(255, 255, 255))
    draw.text(
        (230, 115),
        f"Level {level}  |  {xp:,} Total XP  |  {xp_into_level:,} / {xp_range:,} XP",
        font=font_small,
        fill=grey,
    )
    _draw_bar(draw, 230, 165, percentage, user_colour)
    draw.text((230, 205), f"Daily streak: {streak}", font=font_small, fill=grey)

    # --- Divider ---
    draw.line([(40, 255), (760, 255)], fill=(63, 65, 70), width=2)

    # --- Mining section ---
    m_into, m_range, m_pct = _progress(mining_xp, mining_level, MINING_XP_BASE)
    draw.text(
        (40, 270),
        f"Mining Level {mining_level}  |  {mining_xp:,} Total XP  |  {m_into:,} / {m_range:,} XP",
        font=font_small,
        fill=grey,
    )
    _draw_bar(draw, 40, 315, m_pct, MINING_COLOUR, width=720)

    buffer = BytesIO()
    background.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
