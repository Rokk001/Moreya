#!/usr/bin/env python3
"""Text check of the skill rank stars in the Dungeonbook and the hover of a research field (owner decision of
2026-11-23). No game start, no compiler.

- A skill of the Dungeonbook skill tree shows its rank as stars, one per rank it can reach: learned ranks gold, the
  others greyed. The thin rank bar under the icon is hidden; the text "x/y" moves into the tooltip of the stars.
- The star image SkillRankStar/Star is loaded by the scheme and credited.
- Hovering a research field (research window and Dungeonbook) keeps the whole field and lays the focus frame over it,
  so the icon no longer disappears.
- Research levels: level 1 the plain tile, level 2 a silver frame, level 3 a gold frame.

The star imageset and its picture are game data of the content packages (scripts/content_packages.py): they are read
from the public tree or from the content packages, their CREDITS row from the CREDITS of the public tree and of the
content repository. The scheme and the looks are read with their own rows of the content package core-gui. Without the
content the star files, their CREDITS row, the scheme entry and the hover look are named as not checked; the code is
checked.
"""
import re
import sys
import time
from pathlib import Path

START = time.monotonic()
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402

FAILURES = []
STAR_FILES = ('gui/SkillRankStar.imageset', 'gui/SkillRankStar.png')


def read(relative):
    """Returns the text of a file of the repository; a mixed interface file comes with its own rows of the content."""
    return content_packages.read_text(ROOT, relative)


def check(condition, message):
    """Records a failed item."""
    if not condition:
        FAILURES.append(message)


social = read('source/render/SocialWindow.cpp')
node = social[social.index('void showSkillTreeNode('):]
node = node[:node.index('\n}\n')]
check('bar->setVisible(false);' in node, 'the rank bar is hidden')
check('rank->setText(Gui::toCeguiText(skillRankStars(node.mRank, node.mMaxRank, rank->getPixelSize().d_height)));' in node,
      'the rank label shows the stars')
check('rank->setTooltipText(Gui::toCeguiText(escapeMarkup(node.mBarText)));' in node, 'the rank text stays in the tooltip')
check('setProgress(' not in node, 'no rank progress is drawn')
stars = social[social.index('std::string skillRankStars('):]
stars = stars[:stars.index('\n}\n')]
check('for(uint32_t i = 0; i < maxRank; ++i)' in stars, 'one star per reachable rank')
check('(i < rank ? SKILL_RANK_STAR_FULL_COLOUR : SKILL_RANK_STAR_EMPTY_COLOUR)' in stars,
      'learned ranks gold, the others greyed')
check('const char* const SKILL_RANK_STAR_IMAGE = "SkillRankStar/Star";' in social, 'star image name')
check('const char* const SKILL_RANK_STAR_EMPTY_COLOUR = "FF4A4A4A";' in social, 'grey of an unlearned rank')

# The star files are checked when they are found or the content is present (then a missing one fails as before)
if content_packages.has_content(ROOT) or all(content_packages.data_file(ROOT, path) is not None for path in STAR_FILES):
    imageset = content_packages.read_text(ROOT, 'gui/SkillRankStar.imageset')
    check('imagefile="SkillRankStar.png" name="SkillRankStar"' in imageset and 'name="Star"' in imageset,
          'imageset of the star')
    check(content_packages.data_file(ROOT, 'gui/SkillRankStar.png') is not None, 'star image file')
    check(re.search(r'^gui/SkillRankStar\.png, gui/SkillRankStar\.imageset .*AI-generated \(Codex\)',
                    room_packages.credits_text(ROOT), re.MULTILINE) is not None, 'CREDITS entry of the star, marked AI-generated')
else:
    content_packages.unchecked('check_skill_rank_stars', STAR_FILES + ('the CREDITS entry of the star',))
if content_packages.has_content(ROOT):
    check(read('gui/ODSkin.scheme').count('<Imageset filename="SkillRankStar.imageset" name="SkillRankStar" />') == 1,
          'the scheme loads the star once')

    look = read('gui/OD.looknfeel')
    research = look[look.index('<WidgetLook name="OD/ResearchButton"'):]
    research = research[:research.index('</WidgetLook>')]
    check('<StateImagery name="Hover"><Layer><Section section="research" /><Section section="research_hover" /></Layer>'
          '</StateImagery>' in research, 'hover keeps the field and lays the focus over it')
else:
    content_packages.unchecked('check_skill_rank_stars', ['scheme entry and hover look (own rows of gui/ODSkin.scheme '
                                                          'and gui/OD.looknfeel)'])

game = read('source/modes/GameMode.cpp')
check('static const std::string RESEARCH_FRAME_COLOUR_SILVER = "FFCDD3DC";' in game and
      'static const std::string RESEARCH_FRAME_COLOUR_GOLD = "FFFFC947";' in game, 'silver and gold frame colours')
check('static const uint32_t RESEARCH_LEVEL_SILVER = 2;' in game and 'static const uint32_t RESEARCH_LEVEL_GOLD = 3;'
      in game, 'silver at level 2, gold at level 3')
check('BRONZE' not in game, 'no bronze frame any more')

print('ODP_TEST_PHASE {"name":"check","seconds":%.3f}' % (time.monotonic() - START))
for failure in FAILURES:
    print('FAIL ' + failure)
if FAILURES:
    sys.exit(1)
print('skill rank stars ok')
