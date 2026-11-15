"""Live startup/circular-map regression. Requires local servers, Playwright and Edge."""
import json
import math
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=browser.new_page(viewport={'width':1600,'height':1100})
        errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda request:requests.append(request.url))
        page.route('https://trek.nasa.gov/**',lambda route:route.abort())
        for lat,lon,name in [(12.3,45.6,'Equatorial circle'),(90,350,'North-pole circle'),(-88.2,170,'Polar circle'),(-12,-179.99,'Dateline circle')]:
            page.goto('http://127.0.0.1:5173',wait_until='domcontentloaded')
            expect(page.get_by_role('dialog')).to_be_visible()
            assert page.locator('iframe,canvas').count()==0
            page.get_by_role('button',name='Create circular map',exact=True).click()
            expect(page.get_by_role('alert')).to_contain_text('Enter both')
            page.get_by_label('Latitude',exact=False).fill(str(lat))
            page.get_by_label('Longitude',exact=False).fill(str(lon))
            page.get_by_label('Site name').fill(name)
            page.get_by_role('button',name='Create circular map',exact=True).click()
            canvas=page.locator('.circular-site-map canvas')
            expect(canvas).to_be_visible()
            expect(page.locator('.circular-map-caption')).to_contain_text('stereographic',timeout=30000)
            expect(page.locator('.map-header strong')).to_have_text(name)
            page.get_by_role('button',name='+ Add point',exact=True).click()
            box=canvas.bounding_box()
            # Outside the circular footprint must not place a point.
            page.mouse.click(box['x']+4,box['y']+4)
            page.mouse.click(box['x']+box['width']/2-16,box['y']+box['height']/2-16)
            with page.expect_download() as d:page.get_by_role('button',name='Export Custom points',exact=True).click()
            points=json.loads(Path(d.value.path()).read_text())['points']
            assert len(points)==2,points
            assert points[0]['latitude']==lat
            assert points[0]['longitude']==(lon-360 if lon>180 else lon)
            assert abs(points[1]['latitude']-lat)<2,points
            # Use angular distance: longitude differences grow near either pole.
            a,b=math.radians(lat),math.radians(points[1]['latitude'])
            dl=math.radians(points[1]['longitude']-points[0]['longitude'])
            distance=math.degrees(math.acos(max(-1,min(1,math.sin(a)*math.sin(b)+math.cos(a)*math.cos(b)*math.cos(dl)))))
            assert distance<2,points
            page.locator('input[type=date]').fill('2032-11-02')
            expect(page.locator('.map-header strong')).to_have_text(name)
            print(name+': startup gate, circular picks and persistent center OK',flush=True)
        page.goto('http://127.0.0.1:5173',wait_until='domcontentloaded')
        assert page.locator('iframe,canvas').count()==0
        page.get_by_role('button',name='Use default south pole',exact=True).click()
        expect(page.locator('.map-header strong')).to_have_text('Lunar South Pole')
        expect(page.locator('iframe.lunar-map-frame')).to_be_visible()
        assert page.locator('.circular-site-map').count()==0
        assert not errors,errors
        print('Explicit default south-pole choice OK; no browser errors',flush=True)
        browser.close()


if __name__=='__main__':main()
