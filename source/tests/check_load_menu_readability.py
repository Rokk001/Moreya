"""Exercise the browser's production look switch with installed CEGUI.

The probe reads the GUI folders of a temporary copy: the files of the public tree and of the content packages (a public
file wins, as in the game), the mixed interface files joined with their own rows (scripts/content_packages.py). Without
the content the scheme cannot be loaded, so the probe is named as not checked.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
import content_packages  # noqa: E402

source = (repo / 'source/modes/MenuModeLoad.cpp').read_text()
start = source.index('    sheet->getChild("LevelWindowFrame")->setLookNFeel(')
block = source[start:source.index('    if(mInGame)', start)]
# The probe registers exactly the GUI folders the game reads from resources.cfg.in, non-recursively like ResourceManager.
gui_section = (repo / 'cmake/config/resources.cfg.in').read_text().split('[GUI]', 1)[1].split('[', 1)[0]
gui_folders = ','.join('"%s"' % line.split('=', 1)[1].strip() for line in gui_section.splitlines() if line.startswith('FileSystem='))
probe = r'''
#include <CEGUI/CEGUI.h>
#include <CEGUI/RendererModules/Null/Renderer.h>
#include <CEGUI/RendererModules/Ogre/ResourceProvider.h>
#include <CEGUI/RendererModules/Ogre/ImageCodec.h>
#include <OgreRoot.h>
#include <OgreResourceGroupManager.h>
#include <iostream>
void apply(CEGUI::Window* sheet,bool mInGame){BLOCK}
int checks=0,failures=0;
void check(bool ok){++checks;if(!ok)++failures;}
int main(int argc,char** argv){try{
 Ogre::Root ogre("","","load-menu-Ogre.log");ogre.loadPlugin(std::string(argv[2])+"/bin/Codec_STBI");
 Ogre::ResourceGroupManager& resources=Ogre::ResourceGroupManager::getSingleton();
 for(const char* path:{GUI_FOLDERS})resources.addResourceLocation(std::string(argv[1])+"/"+path,"FileSystem","GUI");
 CEGUI::OgreResourceProvider provider;provider.setDefaultResourceGroup("GUI");CEGUI::OgreImageCodec codec;codec.setImageFileDataType("png");
 CEGUI::NullRenderer& renderer=CEGUI::NullRenderer::create();renderer.setDisplaySize(CEGUI::Sizef(1920,1200));
 CEGUI::System& system=CEGUI::System::create(renderer,&provider,nullptr,&codec,nullptr,"","load-menu-CEGUI.log");
 CEGUI::SchemeManager::getSingleton().createFromFile("ODSkin.scheme");
 CEGUI::WindowManager& windows=CEGUI::WindowManager::getSingleton();CEGUI::Window* sheet=windows.loadLayoutFromFile("MenuLoad.layout");
 system.getDefaultGUIContext().setRootWindow(sheet);
 CEGUI::Window* frame=sheet->getChild("LevelWindowFrame");CEGUI::Window* loading=sheet->getChild("LoadingText");
 CEGUI::Listbox* list=static_cast<CEGUI::Listbox*>(frame->getChild("SaveGameSelect"));
 list->addItem(new CEGUI::ListboxTextItem("Saved dungeon"));
 for(bool game:{true,false,true,false}){
  apply(sheet,game);check(frame->getLookNFeel()==(game?"OD/GameSettingsWindow":"OD/MenuPageWindow"));
  check(loading->isInFront(*frame));check(list->getItemCount()==1);
  check(frame->getChild("BackButton")->isVisible());
  check(frame->getPixelSize().d_width==1920&&frame->getPixelSize().d_height==1200);
  system.getDefaultGUIContext().draw();
 }
 windows.destroyWindow(sheet);CEGUI::System::destroy();CEGUI::NullRenderer::destroy(renderer);
 std::cout<<"CHECKS="<<checks<<" FAILURES="<<failures<<'\n';return failures?1:0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
'''.replace('BLOCK', block)
probe = probe.replace('GUI_FOLDERS', gui_folders)


def copy_gui_folders(target):
    """Copies the files of every GUI folder (not recursive) as the game finds them below target: package files first,
    the public file last so it wins, and every mixed interface file joined with its own rows."""
    for line in gui_section.splitlines():
        if not line.startswith('FileSystem='):
            continue
        folder = line.split('=', 1)[1].strip()
        (target / folder).mkdir(parents=True, exist_ok=True)
        for source_folder in reversed(content_packages.data_folders(repo, folder)):
            for path in source_folder.iterdir():
                if path.is_file() and '.own.' not in path.name:
                    shutil.copy2(path, target / folder / path.name)
        for path in (target / folder).iterdir():
            if path.suffix in ('.layout', '.looknfeel', '.scheme', '.imageset', '.font'):
                if '#@own ' in path.read_text(encoding='utf-8'):
                    path.write_bytes(content_packages.read_text(repo, folder + '/' + path.name).encode('utf-8'))


if not content_packages.has_content(repo):
    content_packages.unchecked('check_load_menu_readability', ['CEGUI probe (content packages: %s)'
                                                               % ', '.join(content_packages.missing_packages(repo))])
    sys.exit(0)
prefix = Path(os.environ['CMAKE_PREFIX_PATH'])
with tempfile.TemporaryDirectory(prefix='odp-load-menu-') as directory:
    work = Path(directory)
    data = work / 'data'
    copy_gui_folders(data)
    (work / 'check.cpp').write_text(probe)
    cegui = prefix.parent / 'src/cegui/cegui'
    subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/std:c++17', '/DCEGUINULLRENDERER_EXPORTS',
        f'/I{prefix / "include/cegui-0"}', f'/I{cegui / "include"}', f'/I{prefix / "include/OGRE"}',
        'check.cpp', *[str(cegui / 'src/RendererModules/Null' / (name+'.cpp')) for name in ('Renderer','GeometryBuffer','Texture','TextureTarget')],
        '/Fecheck.exe', '/link', f'/LIBPATH:{prefix / "lib"}', 'CEGUIBase-0.lib', 'CEGUIOgreRenderer-0.lib', 'OgreMain.lib'], cwd=work, check=True)
    subprocess.run([str(work / 'check.exe'), str(data), str(prefix)], cwd=work, check=True)
