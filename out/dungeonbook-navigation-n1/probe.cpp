
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <map>
#include <sstream>
#include <string>
#include <vector>
namespace CEGUI {
//! Supplies event and widget state, retaining popup selection separately from edit text.
struct EventArgs {};
struct ListboxItem { unsigned id = 0; unsigned getID() const { return id; } };
struct Window {
    bool visible = false, enabled = true;
    std::string text;
    std::map<std::string, Window*> children;
    std::map<std::string, std::string> strings;
    //! Resolves the fixed widget paths used by production handlers.
    Window* getChild(const std::string& name) { assert(children.count(name)); return children[name]; }
    //! Reports the window visibility observed by production handlers.
    bool isVisible() const { return visible; }
    //! Records the requested window visibility.
    void setVisible(bool value) { visible = value; }
    //! Records whether a navigation button can be used.
    void setEnabled(bool value) { enabled = value; }
    //! Keeps the colours of the skills button outside this handler probe.
    void setProperty(const std::string&, const std::string&) {}
    //! Opens the fixture window.
    void show() { visible = true; }
    //! Closes the fixture window.
    void hide() { visible = false; }
    //! Leaves drawing order outside this handler probe.
    void moveToFront() {}
    //! Records edit text separately from popup selection.
    void setText(const std::string& value) { text = value; }
    //! Reports whether the event widget has a creature or row identifier.
    bool isUserStringDefined(const std::string& name) const { return strings.count(name) != 0; }
    //! Reads a production-handler event identifier.
    const std::string& getUserString(const std::string& name) const { return strings.at(name); }
};
//! Supplies a combobox whose selected item is independent of its displayed text.
struct Combobox : Window {
    ListboxItem item;
    //! Supplies the popup item independently of edit text.
    const ListboxItem* getSelectedItem() const { return &item; }
    //! Selects the popup item requested by a reset.
    void setItemSelectState(std::size_t index, bool selected) { assert(selected); item.id = unsigned(index); }
};
//! Supplies a deterministic list scroll position.
struct Scrollbar : Window { float getScrollPosition() const { return 0; } };
struct WindowEventArgs : EventArgs { Window* window = nullptr; };
}
namespace social {
struct DungeonbookEntry { std::string name; bool worker; bool unhappy; };
//! Supplies the asynchronous roster-ready flag used by the actual page guards.
struct PostLog {
    bool ready = true;
    //! Returns the isolated roster service.
    static PostLog& getSingleton() { static PostLog log; return log; }
    //! Reports whether a simulated roster has arrived.
    bool isDungeonbookRosterReady() const { return ready; }
    //! Simulates waiting for the next roster snapshot.
    void clearDungeonbookRoster() { ready = false; }
};
}
enum class ClientNotificationType { askDungeonbookRoster };
//! Records subscription service calls without opening a network connection.
struct ODClient {
    //! Returns the isolated client service.
    static ODClient& getSingleton() { static ODClient client; return client; }
    //! Accepts subscription messages without network activity.
    void queueClientNotification(ClientNotificationType, bool) {}
};
//! Uses the local roster fixture so opening does not discard its restored creatures.
bool useLocalCreatureRoster() { return true; }
const char* const FILTER_LABELS[] = {"All", "Zivs", "Fighters", "Unhappy"};
const char* const NAV_BUTTONS[] = {"NavFeed", "NavProfile", "NavValues", "NavInventory"};
const char* const NAV_SKILLS_BUTTON = "NavSkills";
const char* const NAV_ICON_ENABLED = "enabled";
const char* const NAV_ICON_DISABLED = "disabled";
const char* const TAB_COLOUR_INACTIVE = "inactive";
const char* const TAB_COLOUR_DISABLED = "disabled";
//! Replaces painting only; page and button visibility run through production showPage.
void setNavState(CEGUI::Window*, bool) {}
//! Hosts unchanged production handlers with explicit roster and painting service boundaries.
struct SocialWindow {
    enum class CreatureFilter { All, Workers, Fighters, Unhappy };
    enum class Page { Home, Feed, Profile, Values, Inventory };
    CEGUI::Window* mWindow;
    CreatureFilter mFilter = CreatureFilter::All;
    Page mPage = Page::Home;
    std::string mSelectedCreature;
    std::vector<std::string> mListedCreatures = {"worker", "fighter"};
    float mSinceRefreshCheck = 0;
    void show(); void showCreature(const std::string&); void hide();
    bool onFilterClicked(const CEGUI::EventArgs&); bool onListRowClicked(const CEGUI::EventArgs&);
    bool onLinkClicked(const CEGUI::EventArgs&); bool onBackClicked(const CEGUI::EventArgs&);
    bool onNavClicked(const CEGUI::EventArgs&);
    void selectCreature(const std::string&, Page); void showPage(Page);
    //! The worker of the fixture has a skill tree, the fighter has none (plan INGAME-QS-11 K4).
    bool selectedCreatureHasSkillTree() const { return mSelectedCreature == "worker"; }
    //! Applies the production filter predicates to a stable two-creature roster fixture.
    void rebuildCreatureList() {
        const social::DungeonbookEntry entries[] = {{"worker", true, false}, {"fighter", false, true}};
        mListedCreatures.clear();
        for(const social::DungeonbookEntry& creature : entries) {
        if((mFilter == CreatureFilter::Workers) && !creature.worker)
            continue;
        if((mFilter == CreatureFilter::Fighters) && creature.worker)
            continue;
        if((mFilter == CreatureFilter::Unhappy) && !creature.unhappy)
            continue;

            mListedCreatures.push_back(creature.name);
        }
    }
    //! Keeps painting outside this navigation-handler probe.
    void refreshListRows() {}
    //! Keeps creature-page painting outside this navigation-handler probe.
    void refreshPage() {}
    //! Keeps feed painting outside this navigation-handler probe; source contracts check its selection guard.
    void rebuildFeed() {}
    //! Resolves either fixture creature while rejecting missing selections.
    const social::DungeonbookEntry* findEntry(const std::string& name) const {
        static social::DungeonbookEntry entry;
        return name == "worker" || name == "fighter" ? &entry : nullptr;
    }
};
void SocialWindow::show()
{
    if(!mWindow->isVisible())
    {
        mFilter = CreatureFilter::All;
        CEGUI::Combobox* filter = static_cast<CEGUI::Combobox*>(mWindow->getChild("HomePage/Filter"));
        filter->setItemSelectState(static_cast<std::size_t>(0), true);
        filter->setText(FILTER_LABELS[0]);
    }
    if(!mWindow->isVisible() && !useLocalCreatureRoster())
    {
        social::PostLog::getSingleton().clearDungeonbookRoster();
        ODClient::getSingleton().queueClientNotification(ClientNotificationType::askDungeonbookRoster, true);
    }
    mWindow->show();
    mWindow->moveToFront();
    rebuildCreatureList();
    showPage(mSelectedCreature.empty() ? Page::Home : mPage);
    mSinceRefreshCheck = 0.0f;
}
void SocialWindow::showCreature(const std::string& creatureName)
{
    mFilter = CreatureFilter::All;
    CEGUI::Combobox* filter = static_cast<CEGUI::Combobox*>(mWindow->getChild("HomePage/Filter"));
    filter->setItemSelectState(static_cast<std::size_t>(0), true);
    filter->setText(FILTER_LABELS[0]);
    mSelectedCreature = creatureName;
    mPage = Page::Inventory;
    show();
}
void SocialWindow::hide()
{
    if(!mWindow->isVisible())
        return;
    if(!useLocalCreatureRoster())
    {
        ODClient::getSingleton().queueClientNotification(ClientNotificationType::askDungeonbookRoster, false);
        social::PostLog::getSingleton().clearDungeonbookRoster();
    }
    mWindow->hide();
}
bool SocialWindow::onFilterClicked(const CEGUI::EventArgs& /*e*/)
{
    CEGUI::Combobox* filter = static_cast<CEGUI::Combobox*>(mWindow->getChild("HomePage/Filter"));
    const CEGUI::ListboxItem* item = filter->getSelectedItem();
    if(item == nullptr || item->getID() >= 4)
        return true;
    const CreatureFilter filters[] = {CreatureFilter::All, CreatureFilter::Workers, CreatureFilter::Fighters,
        CreatureFilter::Unhappy};
    mFilter = filters[item->getID()];
    mSelectedCreature.clear();
    rebuildCreatureList();
    showPage(Page::Home);
    return true;
}
bool SocialWindow::onListRowClicked(const CEGUI::EventArgs& e)
{
    const CEGUI::WindowEventArgs& args = static_cast<const CEGUI::WindowEventArgs&>(e);
    std::istringstream parser(args.window->getUserString("Row").c_str());
    std::size_t row = 0;
    if(!(parser >> row))
        return true;

    CEGUI::Scrollbar* bar = static_cast<CEGUI::Scrollbar*>(mWindow->getChild("HomePage/ListScroll"));
    const std::size_t index = static_cast<std::size_t>(bar->getScrollPosition() + 0.5f) + row;
    // Selecting a creature shows its inventory right away
    if(index < mListedCreatures.size())
        selectCreature(mListedCreatures[index], Page::Inventory);
    return true;
}
bool SocialWindow::onLinkClicked(const CEGUI::EventArgs& e)
{
    const CEGUI::WindowEventArgs& args = static_cast<const CEGUI::WindowEventArgs&>(e);
    if(args.window->isUserStringDefined("Creature"))
        selectCreature(std::string(args.window->getUserString("Creature").c_str()), Page::Inventory);
    return true;
}
bool SocialWindow::onBackClicked(const CEGUI::EventArgs& /*e*/)
{
    mSelectedCreature.clear();
    showPage(Page::Home);
    return true;
}
bool SocialWindow::onNavClicked(const CEGUI::EventArgs& e)
{
    const CEGUI::WindowEventArgs& args = static_cast<const CEGUI::WindowEventArgs&>(e);
    const std::string index = args.window->getUserString("Page").c_str();
    const Page pages[] = {Page::Feed, Page::Profile, Page::Values, Page::Inventory};
    Page page = Page::Home;
    for(std::size_t i = 0; i < 4; ++i)
    {
        if(index == std::to_string(i + 1))
            page = pages[i];
    }
    // The feed button of the start page is the start page itself; the other buttons need a creature, the selected
    // one or else the first of the list
    if(mPage == Page::Home && page == Page::Feed)
        return true;
    if(mSelectedCreature.empty() && !mListedCreatures.empty())
        mSelectedCreature = mListedCreatures[0];
    if(mSelectedCreature.empty())
        return true;

    showPage(page);
    return true;
}
void SocialWindow::selectCreature(const std::string& creatureName, Page page)
{
    if((mFilter != CreatureFilter::All) &&
       (std::find(mListedCreatures.begin(), mListedCreatures.end(), creatureName) == mListedCreatures.end()))
    {
        mFilter = CreatureFilter::All;
        CEGUI::Combobox* filter = static_cast<CEGUI::Combobox*>(mWindow->getChild("HomePage/Filter"));
        filter->setItemSelectState(static_cast<std::size_t>(0), true);
        filter->setText(FILTER_LABELS[0]);
    }
    mSelectedCreature = creatureName;
    rebuildCreatureList();
    if(!mSelectedCreature.empty())
        showPage(page);
}
void SocialWindow::showPage(Page page)
{
    // Right after opening, the server roster is still on its way; the page of the creature is filled when it arrives
    const bool waitingForRoster = !mSelectedCreature.empty() && !useLocalCreatureRoster() &&
        !social::PostLog::getSingleton().isDungeonbookRosterReady();
    if(page != Page::Home && findEntry(mSelectedCreature) == nullptr && !waitingForRoster)
        page = Page::Home;
    mPage = page;
    const char* const pageNames[] = {"HomePage", "FeedPage", "ProfilePage", "ValuesPage", "InventoryPage"};
    const Page pages[] = {Page::Home, Page::Feed, Page::Profile, Page::Values, Page::Inventory};
    // One creature's pages replace the start page: the creature list is not shown beside them (book-switch-variant-1)
    mWindow->getChild("HomePage")->setVisible(page == Page::Home);
    for(std::size_t i = 1; i < 5; ++i)
    {
        mWindow->getChild(pageNames[i])->setVisible(pages[i] == page);
        if(pages[i] == page)
            mWindow->getChild(pageNames[i])->moveToFront();
    }
    const char* const overviewFeed[] = {"FeedPanel", "FeedTitle", "FeedTitleRule", "FeedRows", "FeedScroll", "FeedEmpty"};
    for(const char* child : overviewFeed)
        mWindow->getChild(std::string("HomePage/") + child)->setVisible(page == Page::Home);
    mWindow->getChild("NavBar")->setVisible(page != Page::Home);
    mWindow->getChild("Header")->setVisible(page != Page::Home);
    mWindow->getChild("BackButton")->setVisible(page != Page::Home);
    // The skills button is shown greyed out for a creature without a skill tree
    CEGUI::Window* skills = mWindow->getChild(std::string("NavBar/") + NAV_SKILLS_BUTTON);
    const bool hasSkillTree = selectedCreatureHasSkillTree();
    skills->setEnabled(hasSkillTree);
    skills->getChild("Icon")->setProperty("ImageColours", hasSkillTree ? NAV_ICON_ENABLED : NAV_ICON_DISABLED);
    skills->getChild("Label")->setProperty("TextColours", hasSkillTree ? TAB_COLOUR_INACTIVE : TAB_COLOUR_DISABLED);
    // The start page is the feed of all creatures, so its feed button is the active one there
    const Page navPages[] = {Page::Feed, Page::Profile, Page::Values, Page::Inventory};
    for(std::size_t i = 0; i < 4; ++i)
    {
        const bool active = (navPages[i] == page) || (page == Page::Home && i == 0);
        setNavState(mWindow->getChild(std::string("NavBar/") + NAV_BUTTONS[i]), active);
        mWindow->getChild(std::string("NavBar/") + NAV_BUTTONS[i])->setEnabled(
            i == 0 || !mSelectedCreature.empty() || !mListedCreatures.empty());
    }
    if(page == Page::Home)
        refreshListRows();
    if(page == Page::Home || page == Page::Feed)
        rebuildFeed();
    refreshPage();
}
//! Runs selection, all filter choices, every tab, reopen and restored-world UI lifecycle scenarios.
int main() {
    CEGUI::Window root;
    CEGUI::Combobox filter;
    CEGUI::Scrollbar scroll;
    const char* names[] = {"HomePage", "FeedPage", "ProfilePage", "ValuesPage", "InventoryPage", "NavBar", "Header",
        "HomePage/FeedPanel", "HomePage/FeedTitle", "HomePage/FeedTitleRule", "HomePage/FeedRows",
        "HomePage/FeedScroll", "HomePage/FeedEmpty", "NavBar/NavFeed", "NavBar/NavProfile", "NavBar/NavValues", "NavBar/NavInventory",
        "NavBar/NavSkills", "BackButton"};
    CEGUI::Window windows[19];
    for(std::size_t i = 0; i < 19; ++i) root.children[names[i]] = &windows[i];
    CEGUI::Window skillsIcon, skillsLabel;
    windows[17].children["Icon"] = &skillsIcon;
    windows[17].children["Label"] = &skillsLabel;
    root.children["HomePage/Filter"] = &filter;
    root.children["HomePage/ListScroll"] = &scroll;
    SocialWindow book;
    book.mWindow = &root;
    book.show();
    assert(book.mPage == SocialWindow::Page::Home && root.getChild("HomePage")->visible);
    assert(root.getChild("HomePage/FeedRows")->visible && !root.getChild("NavBar")->visible);
    assert(!root.getChild("BackButton")->visible);
    CEGUI::Window row;
    row.strings["Row"] = "0";
    CEGUI::WindowEventArgs event;
    event.window = &row;
    for(unsigned choice = 0; choice < 4; ++choice) {
        book.onListRowClicked(event);
        assert(book.mPage == SocialWindow::Page::Inventory && book.mSelectedCreature == "worker");
        assert(!root.getChild("HomePage")->visible && root.getChild("NavBar")->visible);
        assert(root.getChild("BackButton")->visible && root.getChild("NavBar/NavSkills")->enabled);
        assert(!root.getChild("HomePage/FeedRows")->visible);
        filter.item.id = choice;
        book.onFilterClicked(event);
        const std::vector<std::string> expected[] = {{"worker", "fighter"}, {"worker"}, {"fighter"}, {"fighter"}};
        assert(book.mListedCreatures == expected[choice]);
        assert(book.mSelectedCreature.empty() && book.mPage == SocialWindow::Page::Home);
        assert(root.getChild("HomePage")->visible && root.getChild("HomePage/FeedRows")->visible);
        assert(!root.getChild("NavBar")->visible && !root.getChild("Header")->visible);
        assert(!root.getChild("BackButton")->visible);
        book.hide(); book.show();
        assert(book.mFilter == SocialWindow::CreatureFilter::All && filter.item.id == 0 && filter.text == "All");
    }
    book.showCreature("fighter");
    assert(book.mPage == SocialWindow::Page::Inventory && book.mSelectedCreature == "fighter");
    // A creature without a skill tree shows the skills button disabled
    assert(!root.getChild("NavBar/NavSkills")->enabled && !root.getChild("HomePage")->visible);
    row.strings["Creature"] = "worker";
    book.onLinkClicked(event);
    assert(book.mPage == SocialWindow::Page::Inventory && book.mSelectedCreature == "worker");
    book.mFilter = SocialWindow::CreatureFilter::Fighters;
    book.rebuildCreatureList();
    filter.item.id = 2;
    book.onLinkClicked(event);
    assert(book.mFilter == SocialWindow::CreatureFilter::All && filter.item.id == 0);
    assert(book.mPage == SocialWindow::Page::Inventory && book.mSelectedCreature == "worker");
    for(unsigned tab = 1; tab <= 4; ++tab) {
        row.strings["Page"] = std::to_string(tab);
        book.onNavClicked(event);
        assert(static_cast<unsigned>(book.mPage) == tab && !root.getChild("HomePage")->visible);
        assert(root.getChild("NavBar")->visible);
    }
    book.onBackClicked(event);
    assert(book.mSelectedCreature.empty() && book.mPage == SocialWindow::Page::Home);
    // Saving keeps the live UI unchanged; loading creates a fresh book over restored creatures.
    filter.item.id = 3;
    book.onFilterClicked(event);
    const std::vector<std::string> savedCreatures = {"worker", "fighter"};
    assert(book.mFilter == SocialWindow::CreatureFilter::Unhappy);
    book.hide();
    SocialWindow loaded;
    loaded.mWindow = &root;
    loaded.mListedCreatures = savedCreatures;
    loaded.show();
    assert(loaded.mListedCreatures == savedCreatures && loaded.mFilter == SocialWindow::CreatureFilter::All);
    assert(filter.item.id == 0 && filter.text == "All" && loaded.mSelectedCreature.empty());
    assert(root.getChild("HomePage/FeedRows")->visible && !root.getChild("NavBar")->visible);
}
