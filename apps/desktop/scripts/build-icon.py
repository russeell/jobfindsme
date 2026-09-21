"""Rasterize the code-native brand.svg geometry into macOS icon sizes (Pillow)."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
scale = 16
im = Image.new('RGBA', (1024, 1024))
draw = ImageDraw.Draw(im)
draw.rounded_rectangle((0, 0, 1023, 1023), radius=15*scale, fill='#30302e')
def point(x,y): return ((x+2)*scale,(y-5)*scale)
draw.rectangle((point(32,14),point(41,23)),fill='white')
points=[(32,28),(41,28),(41,45)]
def curve(a,b,c):
    x,y=points[-1]
    for i in range(1,33):
        t=i/32;u=1-t
        points.append((u**3*x+3*u*u*t*a[0]+3*u*t*t*b[0]+t**3*c[0],u**3*y+3*u*u*t*a[1]+3*u*t*t*b[1]+t**3*c[1]))
curve((41,55),(36,60),(27,60))
curve((23,60),(20,59),(18,57))
points.append((22,50))
curve((23,51),(25,52),(27,52))
curve((30,52),(32,50),(32,46))
draw.polygon([point(x,y) for x,y in points],fill='white')
(root/'public').mkdir(exist_ok=True)
im.save(root/'public/brand.png')
im.save(root/'public/brand.icns', format='ICNS')
