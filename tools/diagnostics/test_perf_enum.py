import time
from core.screenshot import get_all_visible_rects

t0 = time.time()
for _ in range(50):
    rects = get_all_visible_rects()
t1 = time.time()

print(f"50 iterations took {t1 - t0:.4f} seconds")
