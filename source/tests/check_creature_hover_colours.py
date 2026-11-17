"""Check that a creature under the cursor keeps its normal colours and only its thin seat-colour contour marks it.

Every creature material of materials/scripts/Creatures is read with its passes, their fragment programs and their
ambient factors. A probe compiles the production RenderManager::getBrighterMaterial (the hover copy) with stand-ins
for the Ogre material classes, gives each creature material the contour pass of getOutlinerMaterial (Custom_color,
ambient = seat colour) and makes its hover copy for every seat colour. For every creature material and seat it
evaluates the colour terms of the production shaders on the hover copy:
- body passes (Creature.frag): the term ambientLightColour * ambient is the same as on the normal material, so the
  body keeps its normal colours and is never filled white;
- contour pass (Custom_color.frag, cc = 0.01 * ambient + 0.99 * color): stays within 0.1 of the seat colour in every
  channel, so the marker remains a contour in seat colour.

Fixed values of this branch: 33 creature material files, 49 creature materials, 4 seat colours. The probe compiles
with cl, so this check runs in the compile phase of the integration only.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    """Returns the text of a repository file."""
    return (ROOT / path).read_text(encoding='utf-8')


def block_from(text, start):
    """Returns the text from start to the end of the first braces block after it."""
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def strip_comments(text):
    """Removes // comments of material scripts."""
    return re.sub(r'//[^\n]*', '', text)


# The production shader formulas the probe evaluates.
creature_frag = read('shaders/Creature.frag')
assert 'uniform vec3 ambient;' in creature_frag
assert '+ ambientLightColour.rgb * ambient;' in creature_frag
custom_frag = re.sub(r'\s+', ' ', read('shaders/Custom_color.frag'))
assert 'cc = 0.01* ambient + 0.99*color;' in custom_frag

render = read('source/render/RenderManager.cpp')
production = block_from(render, render.index('Ogre::MaterialPtr RenderManager::getBrighterMaterial('))
outliner = block_from(render, render.index('Ogre::MaterialPtr RenderManager::getOutlinerMaterial('))
# The contour pass of the outliner copy uses Custom_color with the seat colour as ambient.
assert 'myPass1->setFragmentProgram("Custom_color","Graphics");' in outliner
assert 'setNamedConstant("ambient",cc);' in outliner and 'setNamedConstant("color",cc);' in outliner

files = sorted((ROOT / 'materials/scripts/Creatures').glob('*.material'))
assert len(files) == 33, len(files)
materials = []
for path in files:
    text = strip_comments(path.read_text(encoding='utf-8'))
    programs = dict(re.findall(r'fragment_program\s+(\w+)\s+glsl\s*\{\s*source\s+(\S+)', text))
    for match in re.finditer(r'^material\s+([\w/]+)', text, re.M):
        material = block_from(text, match.start())
        techniques = [m.start() for m in re.finditer(r'\btechnique\b', material)]
        assert techniques, match.group(1)
        last = block_from(material, techniques[-1])
        passes = []
        for pass_match in re.finditer(r'\bpass\b[^{]*\{', last):
            body = block_from(last, pass_match.start())
            ref = re.search(r'fragment_program_ref\s+(\w+)', body)
            if ref is None:
                passes.append(('', None))
                continue
            assert programs.get(ref.group(1)) == 'Creature.frag', (path.name, ref.group(1))
            ambient = re.search(r'param_named\s+ambient\s+float3\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', body)
            assert ambient, (path.name, match.group(1))
            passes.append((ref.group(1), tuple(float(v) for v in ambient.groups())))
        assert any(p[1] is not None for p in passes), match.group(1)
        materials.append((match.group(1), passes))
assert len(materials) == 49, len(materials)

PREAMBLE = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#define OD_LOG_INF(message) ((void)(message))

namespace FrameStallTrace
{
enum Kind { MaterialPreparation };
//! Stand-in for the frame stall timer scope.
struct Scope { Scope(Kind, const char*) {} };
}

namespace Helper
{
//! Stand-in for the number formatting used in log lines.
inline std::string toString(size_t value) { std::stringstream ss; ss << value; return ss.str(); }
}

namespace Ogre
{
//! Stand-in for the Ogre colour.
struct ColourValue
{
    float r, g, b, a;
    ColourValue(float red = 0.0f, float green = 0.0f, float blue = 0.0f, float alpha = 1.0f) :
        r(red), g(green), b(blue), a(alpha)
    {}
};

//! Stand-in for program parameters: named colour constants.
struct GpuProgramParameters
{
    std::map<std::string, ColourValue> mValues;
    int mDefinition = 0;
    const int* _findNamedConstantDefinition(const std::string& name, bool) const
    {
        return mValues.count(name) != 0 ? &mDefinition : nullptr;
    }
    void setNamedConstant(const std::string& name, const ColourValue& value) { mValues[name] = value; }
};
typedef std::shared_ptr<GpuProgramParameters> GpuProgramParametersSharedPtr;

//! Stand-in pass with an optional fragment program and its parameters.
struct Pass
{
    std::string mFragmentProgram;
    GpuProgramParametersSharedPtr mParameters = std::make_shared<GpuProgramParameters>();
    bool hasFragmentProgram() const { return !mFragmentProgram.empty(); }
    const std::string& getFragmentProgramName() const { return mFragmentProgram; }
    GpuProgramParametersSharedPtr getFragmentProgramParameters() { return mParameters; }
};

//! Stand-in technique owning its passes.
struct Technique
{
    std::vector<std::shared_ptr<Pass>> mPasses;
    size_t getNumPasses() const { return mPasses.size(); }
    std::vector<Pass*> getPasses() const
    {
        std::vector<Pass*> passes;
        for(const std::shared_ptr<Pass>& pass : mPasses)
            passes.push_back(pass.get());
        return passes;
    }
};

class Material;
typedef std::shared_ptr<Material> MaterialPtr;

//! Stand-in material manager keyed by name.
class MaterialManager
{
public:
    std::map<std::string, MaterialPtr> mMaterials;
    static MaterialManager* getSingletonPtr() { static MaterialManager manager; return &manager; }
    MaterialPtr getByName(const std::string& name, const std::string&)
    {
        std::map<std::string, MaterialPtr>::iterator it = mMaterials.find(name);
        return it == mMaterials.end() ? MaterialPtr() : it->second;
    }
};

//! Stand-in material whose clone copies every pass and its parameters.
class Material
{
public:
    std::string mName;
    std::vector<Technique> mTechniques;
    const std::string& getName() const { return mName; }
    size_t getNumTechniques() const { return mTechniques.size(); }
    Technique* getTechnique(size_t index) { return &mTechniques[index]; }
    MaterialPtr clone(const std::string& name, const std::string&) const
    {
        MaterialPtr copy = std::make_shared<Material>();
        copy->mName = name;
        for(const Technique& technique : mTechniques)
        {
            Technique copied;
            for(const std::shared_ptr<Pass>& pass : technique.mPasses)
            {
                std::shared_ptr<Pass> p = std::make_shared<Pass>();
                p->mFragmentProgram = pass->mFragmentProgram;
                *p->mParameters = *pass->mParameters;
                copied.mPasses.push_back(p);
            }
            copy->mTechniques.push_back(copied);
        }
        MaterialManager::getSingletonPtr()->mMaterials[name] = copy;
        return copy;
    }
};
}

//! The production render manager reduced to the hover material function.
class RenderManager
{
public:
    Ogre::MaterialPtr getBrighterMaterial(const std::string& materialName);
};

'''

MAIN_HEAD = r'''
//! One creature pass as written in its material script; an empty program is a pass without fragment program.
struct ScriptPass
{
    const char* program;
    float ambient[3];
};

//! One creature material with its passes.
struct ScriptMaterial
{
    const char* name;
    std::vector<ScriptPass> passes;
};

//! Checks the hover copy of every creature material for every seat colour.
int main()
{
    const Ogre::ColourValue seats[] = {
        Ogre::ColourValue(0.8f, 0.0f, 0.0f), Ogre::ColourValue(0.0f, 0.6f, 0.1f),
        Ogre::ColourValue(0.1f, 0.2f, 0.9f), Ogre::ColourValue(0.9f, 0.8f, 0.0f)};
    std::vector<ScriptMaterial> scripts;
'''

MAIN_TAIL = r'''
    RenderManager renderer;
    Ogre::MaterialManager* manager = Ogre::MaterialManager::getSingletonPtr();
    int checked = 0;
    for(const ScriptMaterial& script : scripts)
    {
        for(int s = 0; s < 4; ++s)
        {
            // The contour copy as getOutlinerMaterial() makes it: the creature passes plus the Custom_color pass.
            Ogre::MaterialPtr contour = std::make_shared<Ogre::Material>();
            std::stringstream name;
            name << script.name << "##_Outliner" << s;
            contour->mName = name.str();
            Ogre::Technique technique;
            for(const ScriptPass& scriptPass : script.passes)
            {
                std::shared_ptr<Ogre::Pass> pass = std::make_shared<Ogre::Pass>();
                pass->mFragmentProgram = scriptPass.program;
                if(pass->hasFragmentProgram())
                    pass->mParameters->setNamedConstant("ambient", Ogre::ColourValue(
                        scriptPass.ambient[0], scriptPass.ambient[1], scriptPass.ambient[2]));
                technique.mPasses.push_back(pass);
            }
            std::shared_ptr<Ogre::Pass> contourPass = std::make_shared<Ogre::Pass>();
            contourPass->mFragmentProgram = "Custom_color";
            contourPass->mParameters->setNamedConstant("color", seats[s]);
            contourPass->mParameters->setNamedConstant("ambient", seats[s]);
            technique.mPasses.push_back(contourPass);
            contour->mTechniques.push_back(technique);
            manager->mMaterials[contour->mName] = contour;

            Ogre::MaterialPtr hover = renderer.getBrighterMaterial(contour->mName);
            assert(hover && hover != contour);
            const std::vector<Ogre::Pass*> passes = hover->getTechnique(hover->getNumTechniques() - 1)->getPasses();
            assert(passes.size() == script.passes.size() + 1);
            for(size_t p = 0; p < script.passes.size(); ++p)
            {
                if(!passes[p]->hasFragmentProgram())
                    continue;
                // Creature.frag: lightingTerm = local light + ambientLightColour.rgb * ambient
                const Ogre::ColourValue& ambient = passes[p]->mParameters->mValues["ambient"];
                assert(ambient.r == script.passes[p].ambient[0]);
                assert(ambient.g == script.passes[p].ambient[1]);
                assert(ambient.b == script.passes[p].ambient[2]);
            }
            // Custom_color.frag: cc = 0.01 * ambient + 0.99 * color
            const Ogre::ColourValue& colour = passes.back()->mParameters->mValues["color"];
            const Ogre::ColourValue& ambient = passes.back()->mParameters->mValues["ambient"];
            const float cc[3] = {0.01f * ambient.r + 0.99f * colour.r, 0.01f * ambient.g + 0.99f * colour.g,
                0.01f * ambient.b + 0.99f * colour.b};
            assert(std::fabs(cc[0] - seats[s].r) <= 0.1f);
            assert(std::fabs(cc[1] - seats[s].g) <= 0.1f);
            assert(std::fabs(cc[2] - seats[s].b) <= 0.1f);
            ++checked;
        }
    }
    assert(checked == 49 * 4);
    std::printf("creature hover colours probe passed (%d material and seat cases)\n", checked);
    return 0;
}
'''


def cpp_float(value):
    """Formats a float literal for the probe."""
    return repr(float(value)) + 'f'


def main():
    """Compiles and runs the probe of the production hover material function."""
    lines = []
    for name, passes in materials:
        items = []
        for program, ambient in passes:
            ambient = ambient or (0.0, 0.0, 0.0)
            items.append('{"%s", {%s}}' % (program, ', '.join(cpp_float(v) for v in ambient)))
        lines.append('    scripts.push_back(ScriptMaterial{"%s", {%s}});' % (name, ', '.join(items)))
    source = PREAMBLE + production + '\n' + MAIN_HEAD + '\n'.join(lines) + '\n' + MAIN_TAIL
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        cpp = directory / 'probe.cpp'
        cpp.write_text(source, encoding='utf-8')
        batch = directory / 'run.cmd'
        batch.write_text(
            f'@echo off\ncall "{vcvars}" >nul\n'
            f'cl /nologo /EHsc /std:c++14 "{cpp}" /Fe:"{directory / "probe.exe"}" '
            f'/Fo:"{directory / "probe.obj"}"\n'
            'if errorlevel 1 exit /b 1\n'
            f'"{directory / "probe.exe"}"\nexit /b %errorlevel%\n',
            encoding='utf-8',
        )
        subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=directory, check=True)
    print('creature hover colours pass the checks')


if __name__ == '__main__':
    main()
