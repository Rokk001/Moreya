"""Exercise editor tab geometry with CEGUI and the production look and layout.

The probe loads the scheme, imagesets and fonts of the gui folder of the public tree merged with the gui folders of the
content packages (scripts/content_packages.py; a public file wins, as in the game); a mixed interface file is given to
the probe joined with its own rows (content_packages.read_text), as the game reads it. Without the content the scheme
cannot be loaded, so the probe is not compiled and the check names it as not checked.
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

deps = Path(os.environ.get('BUILD_DEPS_ROOT', str(Path.home() / 'build-deps')))
null_source = deps / 'src/cegui/cegui/src/RendererModules/Null'
null_include = deps / 'src/cegui/cegui/include/CEGUI/RendererModules/Null'
gui_source = (repo / 'source/render/Gui.cpp').read_text(encoding='utf-8')
start = gui_source.index('std::string scaleFormattedImageSizes(')
end = gui_source.index('\n}\n', start) + 2
scaler = gui_source[start:end]
probe = r"""
#include <CEGUI/CEGUI.h>
#include "CEGUI/RendererModules/Null/Renderer.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
class StubImageCodec : public CEGUI::ImageCodec
{
public:
    StubImageCodec() : CEGUI::ImageCodec("Stub") {}
    CEGUI::Texture* load(const CEGUI::RawDataContainer&, CEGUI::Texture* result) { return result; }
};
@@SCALER@@
//! Checks real CEGUI header positions and the overflow control at one display size.
void checkSize(float width, float height, float user)
{
    CEGUI::System::getSingleton().notifyDisplaySizeChanged(CEGUI::Sizef(width, height));
    CEGUI::WindowManager& manager = CEGUI::WindowManager::getSingleton();
    CEGUI::Window* sheet = manager.loadLayoutFromFile("ModeEditor.layout");
    CEGUI::System::getSingleton().getDefaultGUIContext().setRootWindow(sheet);
    CEGUI::TabControl* tab = static_cast<CEGUI::TabControl*>(sheet->getChild("MainTabControl"));
    const float scale = std::min(width / 1024.0f, height / 768.0f) * user;
    tab->setArea(CEGUI::URect(CEGUI::UDim(0, 0), CEGUI::UDim(1, -133 * scale), CEGUI::UDim(1, -200 * scale), CEGUI::UDim(1, 0)));
    tab->setTabHeight(CEGUI::UDim(0, 35 * scale));
    tab->setTabTextPadding(CEGUI::UDim(0, 20 * scale));
    // The editor has no spells tab (it never cast anything there)
    const char* names[] = {"Tiles", "Rooms", "Traps", "Creatures", "Lights", "Boxes"};
    for(size_t i = 0; i < 6; ++i)
    {
        CEGUI::Window* page = tab->getChild(names[i]);
        page->setText(scaleFormattedImageSizes(page->getText(), scale));
    }
    CEGUI::Window* pane = tab->getChild("__auto_TabPane__Buttons");
    float previous = pane->getUnclippedOuterRect().get().left();
    const float iconWidths[] = {28, 40, 40, 40, 32, 28};
    for(size_t i = 0; i < 6; ++i)
    {
        CEGUI::Window* button = pane->getChildAtIdx(i);
        CEGUI::Rectf rect = button->getUnclippedOuterRect().get();
        CEGUI::TabButton* header = static_cast<CEGUI::TabButton*>(button);
        if(header->getTargetWindow()->getName() != names[i] ||
           std::fabs(rect.getWidth() - (std::floor(iconWidths[i] * scale + 0.5f) + 40 * scale)) > 2.0f ||
           rect.top() < 0 || rect.bottom() > height || rect.left() < 0 || rect.right() > width)
            throw std::runtime_error("header order, width or display fit invalid");
        if(std::fabs(rect.left() - previous) > 1.1f || rect.getWidth() <= 0 || rect.getHeight() <= 0)
            throw std::runtime_error("header positions or size invalid");
        previous = rect.right();
    }
    if(previous > pane->getUnclippedOuterRect().get().right() + 1)
        throw std::runtime_error("headers do not fit at required size");
    const float fittedWidth = pane->getPixelSize().d_width;
    // Force overflow to exercise the otherwise dormant CEGUI scroll control.
    tab->setWidth(CEGUI::UDim(0, 120 * scale));
    CEGUI::Window* first = pane->getChildAtIdx(0);
    float before = first->getUnclippedOuterRect().get().left();
    CEGUI::Window* right = tab->getChild("__auto_TabPane__ScrollRight");
    if(!right->isVisible() || right->getPixelSize().d_height < 1)
        throw std::runtime_error("overflow scroll control is unusable");
    CEGUI::Rectf scrollRect = right->getUnclippedOuterRect().get();
    CEGUI::GUIContext& context = CEGUI::System::getSingleton().getDefaultGUIContext();
    for(size_t i = 0; i < sheet->getChildCount(); ++i)
        if(sheet->getChildAtIdx(i) != tab)
            sheet->getChildAtIdx(i)->setVisible(false);
    context.injectMousePosition((scrollRect.left() + scrollRect.right()) / 2, (scrollRect.top() + scrollRect.bottom()) / 2);
    context.injectMouseButtonDown(CEGUI::LeftButton);
    context.injectMouseButtonUp(CEGUI::LeftButton);
    if(first->getUnclippedOuterRect().get().left() >= before)
        throw std::runtime_error("overflow scroll does not move headers");
    std::cout << width << "x" << height << " user=" << user << " pane=" << fittedWidth
              << " headers=" << previous - pane->getUnclippedOuterRect().get().left() << std::endl;
    CEGUI::System::getSingleton().getDefaultGUIContext().setRootWindow(nullptr);
    manager.destroyWindow(sheet);
    manager.cleanDeadPool();
}
int main()
{
    try
    {
        CEGUI::NullRenderer& renderer = CEGUI::NullRenderer::create();
        renderer.setDisplaySize(CEGUI::Sizef(640, 480));
        CEGUI::DefaultResourceProvider* provider = new CEGUI::DefaultResourceProvider();
        provider->setResourceGroupDirectory("gui", "@@GUI@@");
        provider->setResourceGroupDirectory("fonts", "@@FONTS@@");
        StubImageCodec codec;
        CEGUI::System::create(renderer, provider, static_cast<CEGUI::XMLParser*>(nullptr), &codec, nullptr, "", "cegui-check.log");
        CEGUI::Scheme::setDefaultResourceGroup("gui");
        CEGUI::ImageManager::setImagesetDefaultResourceGroup("gui");
        CEGUI::Font::setDefaultResourceGroup("fonts");
        CEGUI::WidgetLookManager::setDefaultResourceGroup("gui");
        CEGUI::WindowManager::setDefaultResourceGroup("gui");
        CEGUI::SchemeManager::getSingleton().createFromFile("ODSkin.scheme");
        const float sizes[][2] = {{640, 480}, {1920, 1200}, {7680, 4320}};
        const float users[] = {0.8f, 1.0f, 1.2f};
        for(size_t i = 0; i < 3; ++i)
            for(size_t j = 0; j < 3; ++j)
                checkSize(sizes[i][0], sizes[i][1], users[j]);
        return 0;
    }
    catch(const std::exception& error) { std::cerr << error.what() << std::endl; return 1; }
}
""".replace('@@SCALER@@', scaler)

if not content_packages.has_content(repo):
    content_packages.unchecked('check_editor_headers', ['CEGUI probe (content packages: %s)'
                                                        % ', '.join(content_packages.missing_packages(repo))])
    sys.exit(0)

if shutil.which('cl') is None:
    sys.exit('check_editor_headers.py needs the MSVC compiler cl on the PATH: run it from a shell prepared with vcvars64.bat (VS Build Tools, VC/Auxiliary/Build).')

with tempfile.TemporaryDirectory(prefix='odp-editor-headers-') as directory:
    work = Path(directory)
    gui_resources = work / 'gui'
    # The gui folders of the packages first, the public one last, so a public file wins as in the game
    for gui_folder in reversed(content_packages.data_folders(repo, 'gui')):
        shutil.copytree(gui_folder, gui_resources, dirs_exist_ok=True)
    # The mixed interface files as the game reads them: the public file joined with its own rows from the content
    for resource in sorted(gui_resources.rglob('*')):
        relative = 'gui/' + resource.relative_to(gui_resources).as_posix()
        if resource.is_file() and '.own.' not in resource.name and resource.suffix in ('.layout', '.looknfeel',
                                                                                         '.scheme', '.imageset', '.font'):
            if '#@own ' not in resource.read_text(encoding='utf-8'):
                continue
            resource.write_bytes(content_packages.read_text(repo, relative).encode('utf-8'))
    for resource_directory in ('gui/RoomCentreArtwork', 'gui/RoomCentreIcons'):
        for resource in content_packages.data_glob(repo, resource_directory):
            shutil.copy2(resource, gui_resources / resource.name)
    header_dir = work / 'CEGUI/RendererModules/Null'
    header_dir.mkdir(parents=True)
    for header in null_include.glob('*.h'):
        (header_dir / header.name).write_text(header.read_text().replace('"../../', '"CEGUI/'))
    sources = []
    for source in null_source.glob('*.cpp'):
        shutil.copy(source, work / source.name)
        sources.append(source.name)
    shutil.copy(null_source / 'RenderTarget.inl', work / 'RenderTarget.inl')
    probe = probe.replace('@@GUI@@', gui_resources.as_posix() + '/').replace('@@FONTS@@',
                                                                           (gui_resources / 'fonts').as_posix() + '/')
    (work / 'check.cpp').write_text(probe)
    subprocess.run(['cl', '/nologo', '/EHsc', '/MD', '/std:c++17', '/W1', '/D_SILENCE_CXX17_ITERATOR_BASE_CLASS_DEPRECATION_WARNING', '/DCEGUINULLRENDERER_EXPORTS',
                    '/I', str(work), '/I', str(deps / 'install/include/cegui-0'), 'check.cpp'] + sources +
                   ['/Fecheck.exe', '/link', '/LIBPATH:' + str(deps / 'install/lib'), 'CEGUIBase-0.lib'], cwd=work, check=True)
    env = dict(os.environ)
    env['PATH'] = str(deps / 'install/bin') + os.pathsep + env.get('PATH', '')
    subprocess.run([str(work / 'check.exe')], cwd=work, env=env, check=True)
