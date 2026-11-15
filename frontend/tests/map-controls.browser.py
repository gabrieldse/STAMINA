"""Live checks for Help, Map area and custom-circle navigation; local app/API required."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def choose_coordinates(page, name):
    page.get_by_label('Latitude',exact=False).fill('12.3')
    page.get_by_label('Longitude',exact=False).fill('45.6')
    page.get_by_label('Site name').fill(name)
    page.get_by_role('button',name='Create circular map',exact=True).click()
    expect(page.locator('.circular-map-caption')).to_contain_text('stereographic',timeout=30000)
    page.wait_for_function("document.querySelector('.circular-site-map canvas')?.width > 500")


def exported_points(page):
    with page.expect_download() as download:
        page.get_by_role('button',name='Export Custom points',exact=True).click()
    return json.loads(Path(download.value.path()).read_text())['points']


def pick(page,x,y):
    count=len(exported_points(page))
    add=page.get_by_role('button',name='+ Add point',exact=True)
    if add.is_visible():add.click()
    expect(page.get_by_role('button',name='Cancel',exact=True)).to_be_visible()
    page.mouse.click(x,y)
    expect(add).to_be_visible()
    points=exported_points(page)
    assert len(points)==count+1,points
    return points[-1]


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1600,'height':1100})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('https://trek.nasa.gov/**',lambda route:route.abort())
        page.goto('http://127.0.0.1:5173',wait_until='domcontentloaded')
        choose_coordinates(page,'Control test')
        page.get_by_role('button',name='Help',exact=True).click()
        dialog=page.get_by_role('dialog')
        expect(dialog).to_contain_text('Ready to explore the Moon?')
        expect(dialog.get_by_role('button',name='Start Site Demo',exact=True)).to_be_visible()
        expect(dialog.get_by_role('button',name='Explore Freely',exact=True)).to_be_visible()
        assert not dialog.evaluate("node => /\\p{Extended_Pictographic}/u.test(node.innerText)")
        assert page.locator('.map-setup-form').count()==0
        dialog.get_by_role('button',name='Explore Freely',exact=True).click()
        expect(page.get_by_role('dialog')).to_have_count(0)
        page.get_by_role('button',name='Help',exact=True).click()
        page.get_by_role('button',name='Start Site Demo',exact=True).click()
        expect(page.locator('.site-demo-card')).to_be_visible()
        page.get_by_role('button',name='Close site demo',exact=True).click()

        area=page.get_by_role('button',name='Map area',exact=True)
        box=area.bounding_box();workspace=page.locator('.map-workspace').bounding_box()
        assert 0<=box['x']-workspace['x']<30
        assert 0<=box['y']-workspace['y']<30
        area.click();expect(page.get_by_role('dialog')).to_contain_text('Choose the center')
        page.get_by_role('button',name='Cancel',exact=True).click()
        expect(page.locator('.map-header strong')).to_have_text('Control test')
        area.click();page.get_by_role('button',name='Use default south pole',exact=True).click()
        expect(page.locator('.map-header strong')).to_have_text('Lunar South Pole')
        page.get_by_role('button',name='Map area',exact=True).click()
        choose_coordinates(page,'Gesture test')
        print('Help/demo/free exploration and left-side Map area menu: OK',flush=True)

        canvas=page.locator('.circular-site-map canvas');box=canvas.bounding_box()
        x=round(box['x']+box['width']*.61);y=round(box['y']+box['height']*.43)
        before=pick(page,x,y)
        page.get_by_role('button',name='Delete '+before['name'],exact=True).click()
        expect(page.get_by_role('button',name='Delete '+before['name'],exact=True)).to_have_count(0)
        page.mouse.move(x,y);page.mouse.wheel(0,-400);page.wait_for_timeout(400)
        after=pick(page,x,y)
        assert abs(before['latitude']-after['latitude'])<.03,(before,after)
        assert abs(before['longitude']-after['longitude'])<.03,(before,after)
        page.get_by_role('button',name='Delete '+after['name'],exact=True).click()
        expect(page.get_by_role('button',name='Delete '+after['name'],exact=True)).to_have_count(0)
        print('Wheel zoom stays anchored to the picked surface location: OK',flush=True)

        page.get_by_role('button',name='+ Add point',exact=True).click()
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+100,y+50,steps=12);page.mouse.up()
        assert len(exported_points(page))==1,'Dragging must not add a site'
        moved=pick(page,x,y)
        assert abs(moved['latitude']-after['latitude'])+abs(moved['longitude']-after['longitude'])>.1,(moved,after)
        page.get_by_role('button',name='Delete '+moved['name'],exact=True).click()
        page.get_by_role('button',name='Reset view',exact=True).click()
        origin=pick(page,round(box['x']+box['width']/2)-16,round(box['y']+box['height']/2)-16)
        assert abs(origin['latitude']-12.3)<2 and abs(origin['longitude']-45.6)<2
        print('Drag without accidental points and reset to original center: OK',flush=True)
        assert not errors,errors
        browser.close()


if __name__=='__main__':main()
