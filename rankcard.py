import unicodedata
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from config import FONT_PATH


def generate_rank_card(
    username: str,
    avatar_bytes: bytes,
    xp: int,
    level: int,
    user_colour: tuple[int, int, int],
) -> BytesIO:
    # Generate a rank card image for the user.
    background = Image.new(
        "RGB", (800, 250), color=(43, 45, 49)
    )  # Standard Discord dark theme color
    draw = ImageDraw.Draw(background)

    # Load fonts, with a fallback to default if the specified font is not found
    try:
        font_large = ImageFont.truetype(FONT_PATH, 40)
        font_small = ImageFont.truetype(FONT_PATH, 25)
    except OSError as e:
        # Fallback just in case the file gets moved
        print(f"Font was unable to load: {e}")
        font_large = ImageFont.load_default(size=40)
        font_small = ImageFont.load_default(size=25)

    # Normalize the username to ensure consistent rendering
    clean_username = username.replace("\u0454", "e").replace("∂", "d")
    clean_username = unicodedata.normalize("NFKC", clean_username)

    # Calculate XP and level details for the progress bar
    current_level_xp = 100 * ((level - 1) ** 2) if level > 0 else 0
    needed_xp = 100 * (level**2)

    # Calculate how much XP the user has into the current level and the total XP needed for the next level
    xp_into_level = xp - current_level_xp
    xp_range = needed_xp - current_level_xp

    # Progress bar percentage (0.0 to 1.0)
    percentage = xp_into_level / xp_range if xp_range > 0 else 0
    percentage = max(0.0, min(percentage, 1.0))

    # Draw the avatar
    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((150, 150))

    # Create a circular mask for the avatar to make it round
    mask = Image.new("L", (150, 150), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 150, 150), fill=255)
    background.paste(avatar, (40, 50), mask)

    # Draw the username and XP/level text
    draw.text((230, 50), clean_username, font=font_large, fill=(255, 255, 255))
    xp_text = (
        f"Level {level}  |  {xp:,} Total XP  |  {xp_into_level:,} / {xp_range:,} XP"
    )
    draw.text((230, 115), xp_text, font=font_small, fill=(185, 187, 190))

    # Draw the progress bar
    bar_x, bar_y = 230, 165
    bar_width, bar_height = 500, 30
    fill_width = int(bar_width * percentage)
    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
        radius=15,
        fill=(30, 31, 34),
    )
    if fill_width > 15:
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + fill_width, bar_y + bar_height],
            radius=15,
            fill=user_colour,
        )

    # Save the image to a BytesIO buffer and return it
    buffer = BytesIO()
    background.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer
