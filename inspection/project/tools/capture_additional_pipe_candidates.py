from pathlib import Path
import time
import win32com.client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "spatial_box_complex" / "catia_pipe_screenshots"
OUT.mkdir(parents=True, exist_ok=True)
SELECTED = [1, 738, 739, 740, 741, 817, 819, 821, 823, 825, 827, 828, 830, 833, 834, 835, 836, 837, 838, 839, 840, 841]


def apply(sel, show=None, color=None, opacity=None):
    vp = sel.VisProperties
    if show is not None:
        vp.SetShow(show)
    if color is not None:
        vp.SetRealColor(*color, 0)
    if opacity is not None:
        vp.SetRealOpacity(opacity, 0)


app = win32com.client.GetActiveObject("CATIA.Application")
doc = app.ActiveDocument
bodies = doc.Part.Bodies
sel = doc.Selection
viewer = app.ActiveWindow.ActiveViewer

def hide_all_bodies():
    sel.Clear(); sel.Add(doc.Part); apply(sel, show=0)
    sel.Clear()
    for i in range(1, bodies.Count + 1):
        sel.Add(bodies.Item(i))
    apply(sel, show=1)


# Build one batch selection, then perform one hide operation.
hide_all_bodies()

for idx in SELECTED:
    body = bodies.Item(idx)
    sel.Clear(); sel.Add(body); apply(sel, show=0)
    sel.Clear(); sel.Add(body.Shapes.Item(1)); apply(sel, color=(185, 190, 198), opacity=52)

for idx, rgb in ((741, (0, 190, 70)), (839, (220, 40, 40))):
    body = bodies.Item(idx)
    sel.Clear(); sel.Add(body); apply(sel, show=0)
    sel.Clear(); sel.Add(body.Shapes.Item(1)); apply(sel, color=rgb, opacity=255)

sel.Clear(); sel.Add(bodies.Item(741).Shapes.Item(1)); sel.Add(bodies.Item(839).Shapes.Item(1))
viewer.Reframe(); time.sleep(1)
viewer.CaptureToFile(5, str(OUT / "additional_pipe_candidates_context.jpg"))
time.sleep(2)

hide_all_bodies()
for idx, rgb in ((741, (0, 190, 70)), (839, (220, 40, 40))):
    body = bodies.Item(idx)
    sel.Clear(); sel.Add(body); apply(sel, show=0)
    sel.Clear(); sel.Add(body.Shapes.Item(1)); apply(sel, color=rgb, opacity=255)
sel.Clear(); sel.Add(bodies.Item(741).Shapes.Item(1)); sel.Add(bodies.Item(839).Shapes.Item(1))
viewer.Reframe(); time.sleep(1)
viewer.CaptureToFile(5, str(OUT / "additional_pipe_candidates_detail.jpg"))
time.sleep(2)

# Restore the established 22-Body review state.
hide_all_bodies()
for idx in SELECTED:
    body = bodies.Item(idx)
    sel.Clear(); sel.Add(body); apply(sel, show=0)
    sel.Clear(); sel.Add(body.Shapes.Item(1)); apply(sel, color=(255, 230, 0), opacity=255)
sel.Clear()
for idx in SELECTED:
    sel.Add(bodies.Item(idx))
viewer.Reframe()

print(OUT)

