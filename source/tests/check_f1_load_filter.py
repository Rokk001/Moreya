"""Check the unified load screen wiring and exercise real save classification."""
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import content_packages  # noqa: E402

load = (ROOT / "source/modes/MenuModeLoad.cpp").read_text(encoding="utf-8")
assert '"Campaign", "Skirmish", "Sandbox", "Replays"' in load
assert 'visibleLoadEntries(collectLoadEntries()' in load
assert 'openingLoadKind(collectLoadEntries())' in load
# The layout is a mixed file: as the game reads it only with its own rows from the content
if content_packages.has_content(ROOT):
    layout_text = content_packages.read_text(ROOT, "gui/MenuLoad.layout")
    layout = ET.ElementTree(ET.fromstring(layout_text))
    assert len(layout.findall('.//Window[@name="KindFilter"]')) == 1
    assert 'name="Sort" value="False"' in layout_text
    # The filter is the row of four template buttons of the chosen load screen sheet, one radio group (INGAME-QS-10 K14).
    filters = layout.findall('.//Window[@name="KindFilter"]/Window')
    assert [w.get('type') for w in filters] == ['OD/MenuFilterButton'] * 4
    assert [w.get('name') for w in filters] == ['FilterCampaign', 'FilterSkirmish', 'FilterSandbox', 'FilterReplays']
    for w in filters:
        props = {p.get('name'): p.get('value') for p in w.findall('Property')}
        assert props['Text'] == w.get('name')[len('Filter'):] and props['GroupID'] == '1', w.get('name')
else:
    content_packages.unchecked("check_f1_load_filter", ["the kind filter of gui/MenuLoad.layout"])
assert 'getFilterButton(sheet, newestKind)->setSelected(true)' in load
assert '"LevelWindowFrame/KindFilter/Filter") + LOAD_FILTER_NAMES[kind]' in load
assert 'if(levelSelectList->getSelectedCount() == 0)' in load
assert 'loadConfirmAction(' in load and 'ODClient::getSingleton().replay(level)' in load
delete_body = load[load.index('bool MenuModeLoad::deleteSelectedButtonPressed'):load.index('bool MenuModeLoad::updateDescription')]
assert 'updateFilesList();' in delete_body and 'activate();' not in delete_body

PROBE = r'''
#include "modes/LoadGameFilter.h"
#include "utils/Translation.h"
//! \brief Stand-in of the language texts: the probe does not look at texts, so a text is its key.
std::string Translation::tr(const std::string& key) { return key; }
#include <sstream>
#include <iostream>
//! \brief Checks save categories with a locked second campaign level.
int main()
{
    Campaign& campaign = Campaign::getSingleton();
    std::istringstream levels("[Level]\nFile=campaign/One.level\n[Level]\nFile=campaign/Two.level\n");
    std::istringstream progress("Difficulty 1\n");
    if(!campaign.importDefinition(levels) || !campaign.importProgress(progress)) return 1;
    LevelInfo info;
    if(classifyLoadSave("2026-SK-One.level", true, info, campaign) != 0) return 2;
    if(classifyLoadSave("2026-SK-Two.level", true, info, campaign) != 1) return 3;
    info.mCampaignSave.importInfoLine("Campaign\t1 campaign/One.level 1 0 - 0");
    if(classifyLoadSave("renamed.level", true, info, campaign) != 0) return 4;
    info.mCampaignSave.importInfoLine("Campaign\t1 campaign/Two.level 1 0 - 0");
    if(classifyLoadSave("renamed.level", true, info, campaign) != 1) return 5;
    info = LevelInfo();
    info.mIsSandbox = true;
    if(classifyLoadSave("2026-SK-Sandbox.level", true, info, campaign) != 2) return 6;
    if(classifyLoadSave("2026-MP-One.level", true, info, campaign) != -1) return 7;
    info.mIsSandbox = false;
    if(classifyLoadSave("2026-SK-Arena.level", true, info, campaign) != 1) return 8;
    // Multiplayer anywhere before SK-, and an unreadable save counts as skirmish.
    info = LevelInfo();
    if(classifyLoadSave("2026-MP-Two.level", true, info, campaign) != -1) return 9;
    if(classifyLoadSave("broken.level", false, info, campaign) != 1) return 10;
    // Opening kind, order, empty list, confirm action.
    std::vector<LoadEntry> none;
    if(openingLoadKind(none) != 0) return 11;
    if(!visibleLoadEntries(none, 0).empty()) return 12;
    if(loadConfirmAction(0, false) != 0 || loadConfirmAction(3, false) != 0) return 13;
    std::vector<LoadEntry> files = {{"a", 100, 0}, {"b", 300, 2}, {"c", 200, 1}, {"d", 250, 3}, {"e", 150, 1}, {"f", 150, 1}};
    if(openingLoadKind(files) != 2) return 14;
    files.push_back({"g", 400, 3});
    if(openingLoadKind(files) != 3) return 15;
    std::vector<LoadEntry> sk = visibleLoadEntries(files, 1);
    if(sk.size() != 3 || sk[0].mPath != "c" || sk[1].mPath != "e" || sk[2].mPath != "f") return 16;
    std::vector<LoadEntry> rp = visibleLoadEntries(files, 3);
    if(rp.size() != 2 || rp[0].mPath != "g" || rp[1].mPath != "d") return 17;
    if(visibleLoadEntries(files, 0).size() != 1 || visibleLoadEntries(files, 2).size() != 1) return 18;
    // Deleting rebuilds the list for the same kind.
    files.erase(files.begin() + 2);
    sk = visibleLoadEntries(files, 1);
    if(sk.size() != 2 || sk[0].mPath != "e") return 19;
    std::vector<LoadEntry> emptied;
    if(!visibleLoadEntries(emptied, 2).empty() || openingLoadKind(emptied) != 0) return 20;
    // Replays start replay playback, saves load as saved games.
    if(loadConfirmAction(3, true) != 2 || loadConfirmAction(0, true) != 1
        || loadConfirmAction(1, true) != 1 || loadConfirmAction(2, true) != 1) return 21;
    std::cout << "F1 behaviour: 21 cases passed\n";
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="odp-f1-") as directory:
    work = Path(directory)
    (work / "probe.cpp").write_text(PROBE, encoding="utf-8")
    subprocess.run(["cl", "/nologo", "/EHsc", "/MD", "/std:c++14", f"/I{ROOT / 'source'}",
                    "probe.cpp", str(ROOT / "source/game/Campaign.cpp"), "/Feprobe.exe"], cwd=work, check=True)
    subprocess.run([str(work / "probe.exe")], cwd=work, check=True)
print("F1 menu wiring: PASS")
