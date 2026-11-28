#include "modes/GameMode.h"
#include "modes/RoomManagerListItem.h"
#include "render/CreaturePortrait.h"
#include "entities/Creature.h"
#include "entities/CreatureDefinition.h"
#include "social/SocialProfileCache.h"
#include "game/SkillManager.h"
#include "game/SkillType.h"
#include "entities/PotionDefinition.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "network/ClientNotification.h"
#include "network/ODClient.h"
#include "render/Gui.h"
#include "rooms/RoomType.h"
#include "render/Gui.h"
#include "utils/Helper.h"
#include "utils/Translation.h"
#include <CEGUI/Window.h>
#include <CEGUI/widgets/ListboxTextItem.h>
#include <CEGUI/widgets/MultiColumnList.h>
#include <cmath>
#include <sstream>

//! \brief Requests owner-seat data and opens the laboratory overview when a lab exists.
void GameMode::showAlchemyLabWindow()
{
    Player* player = mGameMap->getLocalPlayer();
    if(!isConnected() || player == nullptr || player->getSeat() == nullptr ||
       player->getSeat()->getNbRooms(RoomType::alchemyLab) == 0)
        return;
    mRootWindow->getChild("RoomManagerWindow/Pages/AlchemyPage")->show();
    setLabModeShown(player->getSeat()->getLabMode());
    ClientNotification* request = new ClientNotification(ClientNotificationType::askLabWindow);
    request->mPacket << true;
    ODClient::getSingleton().queueClientNotification(request);
}

//! \brief Toggles the laboratory window from the minimap control and the L key.
bool GameMode::toggleAlchemyLabWindow(const CEGUI::EventArgs& event)
{
    return selectRoomManagerType(RoomType::alchemyLab);
}

//! \brief Closes the overview and stops server snapshots for this player.
bool GameMode::hideAlchemyLabWindow(const CEGUI::EventArgs&)
{
    mRootWindow->getChild("RoomManagerWindow/Pages/AlchemyPage")->hide();
    if(isConnected())
    {
        ClientNotification* request = new ClientNotification(ClientNotificationType::askLabWindow);
        request->mPacket << false;
        ODClient::getSingleton().queueClientNotification(request);
    }
    return true;
}

//! \brief Requests the next of the three approved brewing modes.
bool GameMode::cycleLabMode(const CEGUI::EventArgs&)
{
    Player* player = mGameMap->getLocalPlayer();
    if(!isConnected() || player == nullptr || player->getSeat() == nullptr)
        return true;
    ClientNotification* request = new ClientNotification(ClientNotificationType::askLabSetting);
    request->mPacket << static_cast<int32_t>((player->getSeat()->getLabMode()+1)%3);
    ODClient::getSingleton().queueClientNotification(request);
    return true;
}

//! \brief Adopts the validated server setting and displays its label with the potions the mode brews, as the "Auto"
//! button of the chosen alchemy lab mockup.
void GameMode::setLabModeShown(int32_t mode)
{
    if(mode < 0 || mode > 2)
        return;
    Player* player = mGameMap->getLocalPlayer();
    if(player != nullptr && player->getSeat() != nullptr)
        player->getSeat()->setLabMode(mode);
    static const char* const labels[] = {"mode.game.alchemy.auto", "mode.game.alchemy.healing", "mode.game.alchemy.combat"};
    // Healing, mana and combat potion pictures: automatic brews all three kinds.
    static const bool potions[3][3] = {{true, true, true}, {true, true, false}, {false, false, true}};
    CEGUI::Window* button = mRootWindow->getChild("RoomManagerWindow/Pages/AlchemyPage/ModeButton");
    button->getChild("Label")->setText(Gui::trCegui(labels[mode]));
    for(int32_t index = 0; index < 3; ++index)
        button->getChild("Potion" + Helper::toString(index))->setVisible(potions[mode][index]);
}

//! \brief Sets the item and potion names of the merchant stock and laboratory tooltips again after the language
//! changed. Called every frame; it does nothing while the language is the one the texts were set for.
void GameMode::refreshItemNameTexts()
{
    const std::string language = Translation::getLanguage();
    if(mItemNameLanguage.empty())
    {
        mItemNameLanguage = language;
        return;
    }
    if(mItemNameLanguage == language)
        return;
    mItemNameLanguage = language;

    // The merchant stock: the item card of every cell is made again from its item
    CEGUI::MultiColumnList* stock = static_cast<CEGUI::MultiColumnList*>(
        mRootWindow->getChild("RoomManagerWindow/Pages/MerchantPage/StockList"));
    for(CEGUI::uint row = 0; row < stock->getRowCount(); ++row)
        for(CEGUI::uint column = 0; column < stock->getColumnCount(); ++column)
        {
            CEGUI::ListboxItem* cell = stock->getItemAtGridReference(CEGUI::MCLGridRef(row, column));
            if(cell == nullptr || cell->isDisabled())
                continue;
            for(const std::pair<uint32_t, ItemInstance>& entry : mMerchantItems)
                if(entry.first == cell->getID())
                    cell->setTooltipText(Gui::toCeguiText(Gui::describeItemTooltip(entry.second, mGameMap, nullptr)));
        }

    // The laboratory: the cauldron rows are made again from the latest snapshot
    if(mLabWindowDataReceived)
        setLabWindowData(mLabWindowData);
}

//! \brief Replaces cauldron rows and herb totals with one coherent owner-seat snapshot; the potion names of the
//! tooltips are in the chosen language.
void GameMode::setLabWindowData(const LabWindowData& data)
{
    // Kept so that the tooltips can be set again when the language changes
    mLabWindowData = data;
    mLabWindowDataReceived = true;
    CEGUI::MultiColumnList* list = static_cast<CEGUI::MultiColumnList*>(
        mRootWindow->getChild("RoomManagerWindow/Pages/AlchemyPage/CauldronList"));
    if(list->getColumnCount() == 0)
    {
        list->addColumn("", 0, CEGUI::UDim(0.95f, 0));
        list->setUserSortControlEnabled(false);
    }
    list->resetList();
    for(std::size_t index = 0; index < data.mCauldrons.size(); ++index)
    {
        const LabCauldronRow& cauldron = data.mCauldrons[index];
        const uint32_t row = list->addRow();
        std::vector<const CEGUI::Image*> pictures;
        pictures.push_back(roomManagerImage("OpenDungeonsIcons/AlchemyLabButton"));
        const PotionDefinition* recipe = nullptr;
        for(const PotionDefinition& potion : ConfigManager::getSingleton().getPotions())
            if(potion.getDisplay() == cauldron.mPotion) recipe = &potion;
        pictures.push_back(recipe == nullptr ? nullptr : roomManagerImage("ItemImages/" + recipe->getImage()));
        Creature* brewer = mGameMap->getCreature(cauldron.mBrewer);
        if(brewer != nullptr)
            pictures.push_back(&getCreatureProfilePortraitImage(cauldron.mBrewer, brewer->getDefinition()->getMeshName(),
                social::SocialProfileCache::getCreatureGender(cauldron.mBrewer, brewer->getDefinition()->getClassName())));
        Player* player = mGameMap->getLocalPlayer();
        const double duration = recipe == nullptr || player == nullptr ? 0.0 :
            SkillManager::getResearchValue(player->getSeat(), SkillType::roomAlchemyLab, recipe->getBrewSeconds(), "BrewTime");
        const float progress = duration > 0.0 ? static_cast<float>(1.0 - cauldron.mRemaining / duration) : 0.0f;
        RoomManagerListItem* item = new RoomManagerListItem(Helper::toString(static_cast<uint32_t>(std::ceil(cauldron.mRemaining))) + " s",
            static_cast<uint32_t>(index), pictures, progress);
        // The server names the potion by its English table name; the player reads it in the chosen language
        const std::string potionName = recipe == nullptr ? cauldron.mPotion : recipe->getDisplayText();
        item->setTooltipText(Gui::toCeguiText(potionName + " / " + cauldron.mBrewer));
        list->setItem(item, 0, row);
    }
    // Every herb has its existing stock icon and a number; names stay in tooltips.
    uint32_t index = 0;
    for(const HerbDefinition& herb : ConfigManager::getSingleton().getHerbs())
    {
        if(index >= 4) break;
        std::map<std::string, uint32_t>::const_iterator amount = data.mHerbs.find(herb.mId);
        mRootWindow->getChild("RoomManagerWindow/Pages/AlchemyPage/Herb" + Helper::toString(index))->setProperty("Image", "ItemImages/" + herb.mId);
        mRootWindow->getChild("RoomManagerWindow/Pages/AlchemyPage/HerbCount" + Helper::toString(index))->setText(
            Helper::toString(amount == data.mHerbs.end() ? 0 : amount->second));
        ++index;
    }
    setLabModeShown(data.mMode);
}
