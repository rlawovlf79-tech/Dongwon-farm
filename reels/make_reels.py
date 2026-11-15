"""동원농원 수확 릴스 생성기 (1080x1920, 30fps).

사용법: python3 make_reels.py <사진폴더> <폰트폴더> <출력.mp4>
"""
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

PHOTO_DIR, FONT_DIR, OUT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
W, H, FPS = 1080, 1920, 30
XFADE = 0.45  # 장면 전환 시간(초)

RED = (214, 36, 44)
CREAM = (255, 248, 236)
DARK = (28, 18, 14)

F_TITLE = str(FONT_DIR / "bh.ttf")          # Black Han Sans
F_BODY = str(FONT_DIR / "nanum-xb.ttf")     # 나눔고딕 ExtraBold
F_PEN = str(FONT_DIR / "pen.ttf")           # 나눔손글씨 펜


def font(path, size):
    return ImageFont.truetype(path, size)


# (파일, 길이초, 초점x, 초점y, 줌 시작, 줌 끝, 작은글씨, 큰글씨 줄들, 강조색 줄 인덱스)
SCENES = [
    ("5d2790bf-image.jpg", 3.0, 0.45, 0.55, 1.18, 1.02,
     "2026 가을, 예산", ["지금 동원농원은", "수확 중"], {1}),
    ("8b398bfe-image.jpg", 2.6, 0.45, 0.55, 1.02, 1.14,
     "햇살 가득 머금은", ["나무에서 바로 딴", "꿀사과"], {1}),
    ("4e37819f-image.jpg", 2.6, 0.45, 0.45, 1.12, 1.02,
     "사다리 위에서", ["한 알 한 알", "직접 손으로"], {1}),
    ("1c25a338-image.jpg", 2.6, 0.47, 0.5, 1.02, 1.10,
     "농부의 일 년이 담긴", ["정성 그대로"], {0}),
    ("ac1a0a3f-image.jpg", 2.8, 0.5, 0.5, 1.12, 1.02,
     "선별 또 선별", ["A급 사과는", "빨간 박스에"], {1}),
    ("7f6cf039-image.jpg", 2.6, 0.5, 0.5, 1.02, 1.12,
     "명절 선물용으로 딱", ["예산 사과", "선물세트"], {0}),
    ("00a8e791-image.jpg", 2.6, 0.42, 0.5, 1.10, 1.02,
     "실속 있게 드시고 싶다면", ["가정용 사과", "판매 예정"], {1}),
    ("16c8f6b1-image.jpg", 3.0, 0.5, 0.35, 1.02, 1.10,
     "팔로우만 해도", ["팔로워 전용", "특별 혜택"], {1}),
]
END_SEC = 3.6


def load_cover(name, fx, fy, zoom_max):
    """사진을 9:16 커버 크기(+줌 여유분)로 미리 잘라둔다."""
    im = ImageOps.exif_transpose(Image.open(PHOTO_DIR / name)).convert("RGB")
    tw, th = int(W * zoom_max) + 4, int(H * zoom_max) + 4
    s = max(tw / im.width, th / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    cx = min(max(fx * im.width, tw / 2), im.width - tw / 2)
    cy = min(max(fy * im.height, th / 2), im.height - th / 2)
    return im.crop((int(cx - tw / 2), int(cy - th / 2), int(cx - tw / 2) + tw, int(cy - th / 2) + th))


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def kenburns(base, z):
    cw, ch = W * z, H * z
    x0, y0 = (base.width - cw) / 2, (base.height - ch) / 2
    return base.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def gradient_overlay():
    g = Image.new("L", (1, H))
    for y in range(H):
        top = max(0, 1 - y / 420) * 120
        bot = max(0, (y - H * 0.45) / (H * 0.55)) ** 1.6 * 225
        g.putpixel((0, y), int(min(255, top + bot)))
    alpha = g.resize((W, H))
    ov = Image.new("RGBA", (W, H), (10, 4, 2, 0))
    ov.putalpha(alpha)
    return ov


GRAD = gradient_overlay()


def text_layer(draw_fn):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer


def shadowed(layer, radius=10, opacity=170):
    a = layer.split()[3]
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: v * opacity // 255))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 6))
    out.alpha_composite(layer)
    return out


def fade(layer, a):
    if a >= 1:
        return layer
    r, g, b, al = layer.split()
    return Image.merge("RGBA", (r, g, b, al.point(lambda v: int(v * a))))


def brand_chip():
    def d(dr):
        f = font(F_BODY, 34)
        label = "동원농원  |  예산 사과"
        tw = dr.textlength(label, font=f)
        dr.rounded_rectangle((60, 90, 60 + tw + 64, 160), radius=35, fill=(255, 255, 255, 235))
        dr.ellipse((84, 113, 108, 137), fill=RED)
        dr.text((60 + 32 + 28, 125), label, font=f, fill=DARK, anchor="lm")
    return d


CHIP = text_layer(brand_chip())


def caption_frame(small, lines, accent, t, dur):
    """작은글씨 + 큰글씨 줄들. 줄마다 시차를 두고 아래에서 올라온다."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    big = font(F_TITLE, 138 if max(len(s) for s in lines) <= 6 else 118)
    sm = font(F_PEN, 84)
    base_y = H - 520 - (len(lines) - 1) * 160
    out_a = 1 - ease((t - (dur - 0.35)) / 0.35) if t > dur - 0.35 else 1

    items = [("small", small, base_y - 165, 0.05)] + [
        ("big", s, base_y + i * 160, 0.18 + i * 0.12) for i, s in enumerate(lines)
    ]
    for kind, s, y, delay in items:
        p = ease((t - delay) / 0.5)
        if p <= 0:
            continue
        sub = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(sub)
        dy = int((1 - p) * 60)
        if kind == "small":
            dr.text((70, y + dy), s, font=sm, fill=CREAM, anchor="ls")
        else:
            idx = lines.index(s)
            if idx in accent:
                tw = dr.textlength(s, font=big)
                pad = 22
                dr.rounded_rectangle((70 - pad, y + dy - 126, 70 + tw * min(1, p * 1.2) + pad, y + dy + 24),
                                     radius=18, fill=RED + (245,))
                dr.text((70, y + dy), s, font=big, fill=(255, 255, 255), anchor="ls")
            else:
                dr.text((70, y + dy), s, font=big, fill=(255, 255, 255), anchor="ls",
                        stroke_width=2, stroke_fill=(0, 0, 0, 90))
        layer.alpha_composite(fade(sub, p * out_a))
    return shadowed(layer, 12, 150)


def end_card(t):
    bg = Image.new("RGBA", (W, H), RED + (255,))
    dr = ImageDraw.Draw(bg)
    # 은은한 원 패턴
    for i, (cx, cy, r) in enumerate([(900, 300, 320), (120, 1650, 380), (980, 1500, 160)]):
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(232, 58, 64, 255))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    def show(delay):
        return ease((t - delay) / 0.5)

    rows = [
        (0.0, lambda dy: d.text((W / 2, 560 + dy), "나무에서 따자마자", font=font(F_PEN, 92), fill=CREAM, anchor="mm")),
        (0.12, lambda dy: d.text((W / 2, 690 + dy), "바로 포장! 바로 발송!", font=font(F_TITLE, 100), fill=(255, 255, 255), anchor="mm")),
        (0.35, lambda dy: d.text((W / 2, 930 + dy), "동원농원", font=font(F_TITLE, 190), fill=(255, 255, 255), anchor="mm")),
        (0.5, lambda dy: d.text((W / 2, 1060 + dy), "충남 예산 · 산지직송 사과", font=font(F_BODY, 46), fill=CREAM, anchor="mm")),
    ]
    for delay, fn in rows:
        p = show(delay)
        if p > 0:
            sub = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(sub)
            fn(int((1 - p) * 50))
            layer.alpha_composite(fade(sub, p))
    p = show(0.7)
    if p > 0:
        sub = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(sub)
        dy = int((1 - p) * 50)
        d.rounded_rectangle((150, 1230 + dy, W - 150, 1390 + dy), radius=80, fill=(255, 255, 255, 255))
        d.text((W / 2, 1312 + dy), "010-3473-9110", font=font(F_TITLE, 92), fill=RED, anchor="mm")
        d.text((W / 2, 1480 + dy), "주문 · 문의는 DM 또는 전화로", font=font(F_BODY, 48), fill=(255, 255, 255), anchor="mm")
        layer.alpha_composite(fade(sub, p))
    p = show(1.1)
    if p > 0:
        sub = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(sub)
        pulse = 1 + 0.04 * math.sin(t * 6)
        f = font(F_BODY, int(46 * pulse))
        d.rounded_rectangle((300, 1600, W - 300, 1700), radius=50, outline=(255, 255, 255, 255), width=5)
        d.text((W / 2, 1650), "팔로우하고 혜택 받기", font=f, fill=(255, 255, 255), anchor="mm")
        layer.alpha_composite(fade(sub, p))
    bg.alpha_composite(shadowed(layer, 10, 90))
    return bg


def progress(img, frac):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 8), fill=(255, 255, 255, 70))
    d.rectangle((0, 0, int(W * frac), 8), fill=(255, 255, 255, 230))


def main():
    covers = [load_cover(s[0], s[2], s[3], max(s[4], s[5])) for s in SCENES]
    starts, t = [], 0.0
    for s in SCENES:
        starts.append(t)
        t += s[1] - XFADE
    end_start = t
    total = end_start + END_SEC
    nframes = int(total * FPS)

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-shortest", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k", OUT],
        stdin=subprocess.PIPE)

    def scene_img(i, lt):
        s = SCENES[i]
        dur = s[1]
        z = s[4] + (s[5] - s[4]) * (lt / dur)
        img = kenburns(covers[i], z).convert("RGBA")
        img.alpha_composite(GRAD)
        img.alpha_composite(CHIP)
        img.alpha_composite(caption_frame(s[6], s[7], s[8], lt, dur))
        return img

    for f in range(nframes):
        tt = f / FPS
        active = [i for i in range(len(SCENES)) if starts[i] <= tt < starts[i] + SCENES[i][1]]
        frame = None
        for i in active:
            img = scene_img(i, tt - starts[i])
            if frame is None:
                frame = img
            else:
                a = ease((tt - starts[i]) / XFADE)
                frame = Image.blend(frame, img, a)
        if tt >= end_start:
            lt = tt - end_start
            ec = end_card(lt)
            a = ease(lt / XFADE)
            frame = ec if frame is None else Image.blend(frame, ec, a)
        progress(frame, tt / total)
        ff.stdin.write(frame.convert("RGB").tobytes())
        if f % 60 == 0:
            print(f"{f}/{nframes}", flush=True)

    ff.stdin.close()
    ff.wait()
    print("done", OUT, f"{total:.1f}s")


if __name__ == "__main__":
    main()
