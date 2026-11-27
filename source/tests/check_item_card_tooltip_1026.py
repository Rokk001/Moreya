"""Static check: the tooltips of the Dungeonbook inventory slots look like the item tooltip of the merchant mockup
W-1-merchant.png variant 3 (owner decision 1026, finding 5): dark box, item name large and the quality in the quality
colour, the price after a gold coin, the bonuses as a short left-aligned list. Plan INGAME-QS-11 K6: the border is a
thick frame in the colour of the item's quality (it was violet for every item), and every item tooltip of the game uses
the card, the merchant stock included. No game and no compiler needed.

Checked here:
1. gui/OD.looknfeel has the look OD/ItemTooltip with a dark background, a frame of the plain square Gui creates on all
   edges and corners in the colour of the property QualityFrameColour, left aligned top aligned text inside the frame
   and the named area TextArea, and the XML is well formed.
2. ItemInstance::describeTooltip writes name (large font) and quality in the quality colour, the price after the gold
   coin image, one line per bonus and effect with the values of describe(), and the level.
3. The default tooltip of Gui takes the look while the hovered window has the user string ItemTooltip = 1, and goes
   back to OD/Tooltip otherwise; the coin size follows the scaled by the display font, so it works at every resolution and UI scale.
4. The Dungeonbook slots (Creature::fillItemSlotWindows, boxes of SocialWindow::refreshInventory) use that tooltip; the
   merchant gives its stock cells the card text and marks the stock grid with the quality and the box of the hovered
   cell, so the card is never drawn over it.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

# OD.looknfeel and ODSkin.scheme are mixed files: as the game reads them only with their own rows from the content;
# without it they are None and their parts are named as not checked
CONTENT = content_packages.has_content(repo)
look = content_packages.read_text(repo, 'gui/OD.looknfeel') if CONTENT else None
if CONTENT:
    ET.fromstring(look)
else:
    content_packages.unchecked('check_item_card_tooltip_1026', ['the look OD/ItemTooltip of gui/OD.looknfeel',
                                                                'the fonts of gui/ODSkin.scheme'])
item = (repo / 'source/entities/ItemInstance.cpp').read_text()
header = (repo / 'source/entities/ItemInstance.h').read_text()
gui = (repo / 'source/render/Gui.cpp').read_text()
creature = (repo / 'source/entities/Creature.cpp').read_text()
social = (repo / 'source/render/SocialWindow.cpp').read_text()
# The icon and skin atlases lie whole in content packages (found through scripts/content_packages.py); without them
# they are None and their parts are named as not checked
ATLAS_FILES = ['gui/ODIcons.imageset', 'gui/ODSkin.imageset']
ATLAS_PRESENT = all(content_packages.data_file(repo, name) is not None for name in ATLAS_FILES)
if not ATLAS_PRESENT:
    content_packages.unchecked('check_item_card_tooltip_1026', ATLAS_FILES)
icons = content_packages.read_text(repo, 'gui/ODIcons.imageset') if ATLAS_PRESENT else None
fonts = content_packages.read_text(repo, 'gui/ODSkin.scheme') if CONTENT else None


def block(text, start, end='\n}\n'):
    body = text[text.index(start):]
    return body[:body.index(end)]


# 1. The look
frame_image = re.search(r'ITEM_TOOLTIP_FRAME_IMAGE = "([^"]+)";', gui)[1]
if CONTENT:
    widget = block(look, '<WidgetLook name="OD/ItemTooltip">', '</WidgetLook>')
    assert '<NamedArea name="TextArea">' in widget
    assert re.search(r'name="background".*?Colours[^>]*topLeft="F[0-9A-F]10', widget, re.S) or 'F2100C18' in widget, 'dark box'
    border = block(widget, '<ImagerySection name="border">', '</ImagerySection>')
    assert border.count('<Image ') == 8 and border.count('name="%s"' % frame_image) == 8, 'frame on all edges and corners'
    assert '<ColourRectProperty name="QualityFrameColour" />' in border and 'FFB070FF' not in border, 'quality colour'
    assert 'type="ColourRect" name="QualityFrameColour"' in widget
    assert widget.count('ImageDim dimension="Width" name="%s"' % frame_image) == 4, 'the text stays inside the frame'
    label = block(widget, '<ImagerySection name="label">', '</ImagerySection>')
    assert '<HorzFormat type="LeftAligned" />' in label and '<VertFormat type="TopAligned" />' in label, 'left aligned list'
    assert 'CentreAligned' not in widget
    assert widget.count('<StateImagery') == 2, 'Enabled and Disabled'
    # the look only uses images that exist: the skin images of the imageset and the frame square Gui creates before it loads
    if ATLAS_PRESENT:
        imageset = content_packages.read_text(repo, 'gui/ODSkin.imageset')
        for name in set(re.findall(r'name="OpenDungeonsSkin/(Tooltip[A-Za-z]+)"', widget)):
            assert 'name="%s"' % name in imageset, name
assert gui.index('createItemTooltipFrameImage();') < gui.index('createFromFile("ODSkin.scheme")')

# 2. The text
text = block(item, 'std::string ItemInstance::describeTooltip(')
assert "[font='MedievalSharp-13']" in text and "[font='MedievalSharp-10']" in text, 'large name, smaller lines'
for font in ('MedievalSharp-13', 'MedievalSharp-10') if CONTENT else ():
    assert 'name="%s"' % font in fonts, font
assert text.index('getDisplayName(map)') < text.index('qualityName(mQuality)') < text.index('GoldCoin') < text.index('itemNumber(getPrice(map))')
assert "OpenDungeonsIcons/GoldCoin" in text
assert icons is None or 'name="GoldCoin"' in icons
assert 'image-size' in text and 'coinSize' in text
assert 'QUALITY_COLOURS' in text, 'name and quality in the quality colour'
assert 'mBonuses' in text and 'mEffects' in text and 'bonusName(bonus.first)' in text and 'getLevelMin(map)' in text
assert text.count(r'<< "\n"') >= 2, 'one line per value'
assert 'describeTooltip(const GameMap* map, const Weapon* heldWeapon, int32_t coinSize) const' in header
# describe() keeps its values for the merchant stock cell tooltips and the context line
assert 'std::string ItemInstance::describe(' in item

# 3. The tooltip window
assert 'const char* const ITEM_TOOLTIP_LOOK = "OD/ItemTooltip";' in gui
assert 'const char* const PLAIN_TOOLTIP_LOOK = "OD/Tooltip";' in gui
moved = block(gui, 'context.setDefaultTooltipType("OD/Tooltip");', 'return true;')
assert 'getUserString(ITEM_TOOLTIP_USER_STRING) == "1"' in moved
assert 'tooltip->setLookNFeel(look);' in moved and 'tooltip->sizeSelf();' in moved
assert 'describeItemTooltip(item, map, heldWeapon)' in block(gui, 'void Gui::setItemTooltip(', '\n}\n')
assert 'getFontHeight()' in block(gui, 'std::string Gui::describeItemTooltip(', '\n}\n'), \
    'coin as high as the scaled by the display line'
assert 'setUserString(ITEM_TOOLTIP_USER_STRING, "1")' in gui
assert 'window->setUserString(ITEM_TOOLTIP_COLOUR_USER_STRING, qualityColour);' in gui
assert 'tooltip->setProperty("QualityFrameColour", frame);' in gui
assert 'static void setItemTooltip(' in (repo / 'source/render/Gui.h').read_text()

# 4. The slots
fill = block(creature, 'void Creature::fillItemSlotWindows(', '\n}\n')
assert 'Gui::setItemTooltip(image, *item, creature->getGameMap(), heldWeapon);' in fill
assert 'Gui::setPlainTooltip(image, ""' in fill
assert 'Gui::copyTooltip(slot, slot->getParent());' in block(social, 'void SocialWindow::refreshInventory(', '\n}\n')
merchant = (repo / 'source/modes/GameModeMerchant.cpp').read_text()
stock = block(merchant, 'void GameMode::receiveMerchantWindow(')
hover = block(merchant, 'bool GameMode::hoverMerchantItem(')
assert 'cell->setTooltipText(Gui::describeItemTooltip(items[index].second, mGameMap, nullptr));' in stock
assert 'list->setTooltipText(item->getTooltipText());' in hover and 'Gui::setPlainTooltip(list, "");' in hover
assert 'Gui::markItemTooltip(list, static_cast<const MerchantImageItem*>(item)->getQualityColour(), area.str());' in hover

print('item card tooltip 1026: look, text, tooltip switch and slots checked')
