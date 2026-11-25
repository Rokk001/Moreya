#!/usr/bin/env python3
"""Check that material textures and GUI images are in registered resource folders.

The material scripts, imagesets and textures are found in the public tree and in the content packages (the game adds
the same folder of every content package for each resources.cfg location). Without the content a texture that is not
in the public tree is named as not checked instead of failing; with the content present every reference must resolve.
"""

import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_packages  # noqa: E402
import room_packages  # noqa: E402


# Check every referenced texture against the non-recursive resource directories (the public folder and the same folder
# of every present content package, and the asset folders the game adds for every present room package; a texture of a
# room package that is not present is not checked, nor a texture outside the public tree while the content is missing).
def main():
    config = (ROOT / 'cmake/config/resources.cfg.in').read_text(encoding='utf-8')
    folders = []
    for value in re.findall(r'^\s*FileSystem\s*=\s*(.+?)\s*$', config, re.MULTILINE):
        if '@' not in value:
            folders += [ROOT / value.strip()] + [folder for folder in content_packages.data_folders(ROOT, value.strip())
                                              if folder != ROOT / value.strip()]
    for package in room_packages.package_roots(ROOT):
        textures = package / 'materials' / 'textures'
        folders += [textures] + [folder for folder in textures.rglob('*') if folder.is_dir()]
    references = []
    for material in content_packages.data_glob(ROOT, 'materials/scripts', '*.material'):
        for number, line in enumerate(material.read_text(encoding='utf-8').splitlines(), 1):
            match = re.match(r'^\s*texture\s+(\S+)', line)
            if match:
                references.append((material.name, number, match.group(1).strip('"')))
    unchecked_imagesets = []
    for imageset in content_packages.data_glob(ROOT, 'gui', '*.imageset'):
        # The own rows file of a mixed imageset (gui/ODIcons.own.imageset) is joined into its imageset, not read alone
        if imageset.name.endswith('.own.imageset'):
            continue
        relative = content_packages.relative_path(ROOT, imageset)
        text = content_packages.read_text(ROOT, relative)
        # Without the content a mixed imageset holds only its upstream rows and marker comments: not checked
        if '<!--#@own ' in text and not content_packages.has_content(ROOT):
            unchecked_imagesets.append(relative)
            continue
        root = ET.fromstring(text)
        for element in root.iter():
            if 'Imagefile' in element.attrib:
                references.append((relative, 0, element.attrib['Imagefile']))
    missing = [(source, line, name) for source, line, name in references
               if not any((folder / name).is_file() for folder in folders) and not packaged_elsewhere(name)]
    if not content_packages.has_content(ROOT):
        content_packages.unchecked('check_texture_resources', unchecked_imagesets +
                                   sorted(set(name for _, _, name in missing)))
        missing = []
    for source, line, name in missing:
        print(f'{source}:{line}: missing registered texture {name}')
    print(f'{len(references)} references checked; {len(missing)} missing')
    return 1 if missing else 0


def packaged_elsewhere(name):
    """True for a texture of a room package that is not present."""
    return any(room_packages.is_missing_packaged(ROOT, folder + name)
               for folder in ('materials/textures/', 'materials/textures/tavern/'))


if __name__ == '__main__':
    sys.exit(main())
