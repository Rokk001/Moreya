"""Ghost and merchant page look, shared frame and all nested text at every required scale.

The merchant empty state is eighteen empty slots. R6 replaces the old explanation
panels and history row with pictures, short labels and item confirmation.

The four layouts are content (core-gui package, found through scripts/content_packages.py); without them the code of
the merchant page and the shared close handler are checked and the layouts are named as not checked.
"""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from check_room_manager_pages import props, windows, fit_page

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402

merchant=(ROOT/'source/modes/GameModeMerchant.cpp').read_text()
assert 'std::max<std::size_t>(18, ((items.size() + 5) / 6) * 6)' in merchant,'eighteen empty slots, six columns'
assert 'cell->setDisabled(true)' in merchant,'empty slots are not goods'
assert 'cell->setTooltipText(Gui::toCeguiText(Gui::describeItemTooltip(items[index].second, mGameMap, nullptr)))' in merchant,'full item card tooltip'
assert 'positionSelf()' in merchant,'tooltip at the pointer'
assert 'refreshMerchantSelection();' in merchant,'treasury enabled state refreshed'
shared=(ROOT/'source/modes/GameModeRoomManager.cpp').read_text()
assert 'CEGUI::FrameWindow::EventCloseClicked' in shared and '&GameMode::closeRoomManager' in shared
#: The layouts of the page look (core-gui package)
LAYOUTS=('gui/WindowRoomManager.layout','gui/WindowSocial.layout','gui/RoomManagerGhostPage.layout',
         'gui/RoomManagerMerchantPage.layout')
missing_content=[name for name in LAYOUTS if content_packages.data_file(ROOT,name) is None]
if missing_content:
    content_packages.unchecked('check_ghost_merchant_window_look',missing_content)
    print('PASS ghost and merchant code: empty slots, item card tooltip, shared close handler')
    sys.exit(0)
manager=ET.ElementTree(ET.fromstring(content_packages.read_layout_text(ROOT, 'gui/WindowRoomManager.layout'))).getroot().find('Window')
book=ET.ElementTree(ET.fromstring(content_packages.read_layout_text(ROOT, 'gui/WindowSocial.layout'))).getroot().find('Window')
# The Room Manager and the Dungeonbook share their frame: the window frame of the menu sheet that every in-game window
# uses (it was the ornate book frame copied into both layouts), with no frame or title band property of their own.
assert manager.get('type')==book.get('type')=='OD/SheetWindow','shared frame of the menu sheet'
for window in (manager,book):
    for key in props(window):
        assert not ((key.startswith('Frame') and key.endswith('Image')) or key=='TitlebarFont'),'own frame '+key
    assert window.find('AutoWindow') is None,'own title band'
for name in ('Ghost','Merchant'):
    root=ET.ElementTree(ET.fromstring(content_packages.read_layout_text(ROOT, 'gui/RoomManager'+name+'Page.layout'))).getroot().find('Window')
    assert root.get('type')=='DefaultWindow' and root.find('AutoWindow') is None
    page=windows(root)
    assert 'CloseButton' not in page,'common close control'
    for path,node in page.items():
        q=props(node)
        if node.get('type') in ('OD/Button','OD/Checkbox','OD/StaticText','OD/MultiColumnList'):
            assert q.get('Font','').startswith('MedievalSharp-'),(name,path,'game font')
        if node.get('type')=='OD/StaticText':
            assert q.get('TextColours')=='FFF2C860',(name,path,'gold labels')
        assert node.get('type')!='OD/GameTabButton',(name,path,'no HUD tab in room page')
        assert len(q.get('TooltipText',''))<=100,(name,path,'tooltip bounds')
    assert not {'HistoryText','HistoryPanel','EmptyText','GhostExplainText'} & set(page)
    fit_page(name,page,windows(manager))
print('PASS ghost and merchant shared frame, fonts, gold labels, empty slots and 100 screen/scale cases')
