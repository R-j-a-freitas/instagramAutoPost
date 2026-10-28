# Seamless (horizontally tileable) warm cotton paper, 1600×2600, no vignette (the page adds it in screen space).
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
W, H = 1600, 2600; rng = np.random.default_rng(11)
base = np.array([241, 233, 218], np.float32)
def periodic_noise(cells_x, cells_y):
    """Smooth noise that wraps horizontally: bicubic upsampling of a grid tiled three times, centre third kept."""
    g = rng.standard_normal((cells_y + 3, cells_x)).astype(np.float32)
    g3 = np.concatenate([g, g, g], 1)
    im = Image.fromarray(((g3 - g3.min()) / (g3.max() - g3.min()) * 255).astype(np.uint8)).resize((W * 3, H + 3 * H // cells_y), Image.BICUBIC)
    a = np.asarray(im, np.float32)[H // cells_y: H // cells_y + H, W:2 * W] / 255 - .5
    return a
m = periodic_noise(7, 11) * .9 + periodic_noise(18, 29) * .5 + periodic_noise(64, 104) * .25
img = base[None, None, :] * (1 + m[..., None] * .035)
fib = Image.new('L', (W, H), 0); d = ImageDraw.Draw(fib)
for _ in range(5200):
    x, y = rng.uniform(0, W), rng.uniform(0, H); a = rng.uniform(0, np.pi); L = rng.uniform(8, 40); pts = [(x, y)]
    for k in range(4):
        a += rng.normal(0, .35); x += np.cos(a) * L / 4; y += np.sin(a) * L / 4; pts.append((x, y))
    for dx in (-W, 0, W):                                   # draw wrapped copies so fibres cross the seam
        d.line([(px + dx, py) for px, py in pts], fill=int(rng.uniform(40, 140)) if dx == 0 else 90, width=1)
fib = np.asarray(fib.filter(ImageFilter.GaussianBlur(.6)), np.float32) / 255
sign = np.where(periodic_noise(260, 430) > 0, 1, -1)
img = img * (1 - fib[..., None] * .035 * sign[..., None])
img += rng.normal(0, 1.6, (H, W, 1))
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save('paper_tile.jpg', quality=92)
