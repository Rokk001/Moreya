"""Check that nothing overlaps on the profile page of the Dungeonbook (owner decision 830, finding d).

Static check, no game needed. The profile page of the book (gui/WindowSocial.layout, book-variant-2 since plan
INGAME-QS-11 K1): portrait, name and handle line, the labels and values of the table, the skills, the quote, the rules,
the column rule and the posts column do not overlap (texts that replace each other aside); the portrait and the table
are left of the posts. The part about the bar row and the handle line of the shared creature profile page was removed
with that page (owner decision 2026-11-18); the book has no health or experience bar (book-variant-2).

The layout is content (core-gui package, found through scripts/content_packages.py); without it the removed shared page
is still checked absent and the profile page is named as not checked.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

# Absent from the public tree and from every content package
assert content_packages.data_file(repo, 'gui/WindowCreatureProfilePage.layout') is None, \
    'the shared profile page was deleted'
if content_packages.data_file(repo, 'gui/WindowSocial.layout') is None:
    content_packages.unchecked('check_dungeonbook_profile_overlap', ['gui/WindowSocial.layout'])
    sys.exit(0)


def overlap(a, b):
    return a[0] < b[2] - 1e-6 and b[0] < a[2] - 1e-6 and a[1] < b[3] - 1e-6 and b[1] < a[3] - 1e-6



# 1. The book's profile page (WindowSocial.layout), boxes as fractions of the frame client
social_layout = content_packages.read_text(repo, 'gui/WindowSocial.layout')
book = ET.fromstring(social_layout).find('Window')
size = re.search(r'name="Area" value="\{\{0\.5,(-?\d+)\},\{0\.5,(-?\d+)\},\{0\.5,(\d+)\},\{0\.5,(\d+)\}\}"', social_layout)
book_w, book_h = int(size[3]) - int(size[1]), int(size[4]) - int(size[2])
profile = book.find("Window[@name='ProfilePage']")


def fractions(element):
    value = element.find("Property[@name='Area']").get('value')
    dims = [(float(a), float(b)) for a, b in re.findall(r'\{(-?[0-9.]+),(-?[0-9.]+)\}', value)]
    assert all(offset == 0 for _, offset in dims), element.get('name') + ' scales with its parent'
    return tuple(d[0] for d in dims)


page_box = fractions(profile)
book_boxes = {w.get('name'): fractions(w) for w in profile.findall('Window')}
# Windows that are shown instead of each other: "Nothing posted yet." instead of the post pictures
alternatives = {frozenset(('PostsEmpty', 'PostThumb%d' % i)) for i in range(6)}
names = sorted(book_boxes)
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if frozenset((a, b)) not in alternatives:
            assert not overlap(book_boxes[a], book_boxes[b]), ('the profile page of the book overlaps', a, b)
assert 'SocialHolder' not in book_boxes and 'KeeperText' not in book_boxes, 'the book profile is book-variant-2'
assert book_boxes['NameText'][3] <= book_boxes['AgeLabel'][1], 'the name line is above the table'
assert book_boxes['Portrait'][2] <= book_boxes['NameText'][0] and book_boxes['Portrait'][2] <= book_boxes['AgeLabel'][0]
assert book_boxes['AgeValue'][2] <= book_boxes['ColumnRule'][0] <= book_boxes['PostThumb0'][0], 'the posts are right'

pairs = len(names) * (len(names) - 1) // 2
print('profile overlap ok: %d windows of the book profile, %d pairs free of overlap' % (len(names), pairs))
