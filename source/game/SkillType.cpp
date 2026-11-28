/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "game/SkillType.h"

#include "network/ODPacket.h"
#include "utils/Helper.h"
#include "utils/NameAliases.h"
#include "utils/Translation.h"

namespace Skills
{

SkillType fromString(const std::string& typeName)
{
    const std::string type = NameAliases::resolve(typeName);
    for(uint32_t i = 0; i < static_cast<uint32_t>(SkillType::countSkill); ++i)
    {
        SkillType skillType = static_cast<SkillType>(i);
        if(type != toString(skillType))
            continue;

        return skillType;
    }

    return SkillType::nullSkillType;
}

//! \brief Returns the stored name of a research type.
//! \brief Returns the stable saved name of every research entry.
std::string toString(SkillType type)
{
    switch(type)
    {
        case SkillType::nullSkillType:
            return "nullSkillType";
        case SkillType::roomArena:
            return "roomArena";
        case SkillType::roomBridgeStone:
            return "roomBridgeStone";
        case SkillType::roomBridgeWooden:
            return "roomBridgeWooden";
        case SkillType::roomCasino:
            return "roomCasino";
        case SkillType::roomCrypt:
            return "roomCrypt";
        case SkillType::roomDormitory:
            return "roomDormitory";
        case SkillType::roomWorkshop:
            return "roomWorkshop";
        case SkillType::roomHatchery:
            return "roomHatchery";
        case SkillType::roomLibrary:
            return "roomLibrary";
        case SkillType::roomPrison:
            return "roomPrison";
        case SkillType::roomInfirmary:
            return "roomInfirmary";
        case SkillType::roomGhostRoom:
            return "roomGhostRoom";
        case SkillType::roomGuardRoom:
            return "roomGuardRoom";
        case SkillType::roomToilet:
            return "roomToilet";
        case SkillType::roomTavern:
            return "roomTavern";
        case SkillType::tavernBeer:
            return "tavernBeer";
        case SkillType::roomSpa:
            return "roomSpa";
        case SkillType::roomTemple:
            return "roomTemple";
        case SkillType::roomTorture:
            return "roomTorture";
        case SkillType::roomTrainingHall:
            return "roomTrainingHall";
        case SkillType::roomTreasury:
            return "roomTreasury";
        case SkillType::spellCallToWar:
            return "spellCallToWar";
        case SkillType::spellSummonWorker:
            return "spellSummonWorker";
        case SkillType::spellCreatureDefense:
            return "spellCreatureDefense";
        case SkillType::spellCreatureExplosion:
            return "spellCreatureExplosion";
        case SkillType::spellCreatureHaste:
            return "spellCreatureHaste";
        case SkillType::spellCreatureHeal:
            return "spellCreatureHeal";
        case SkillType::spellCreatureSlow:
            return "spellCreatureSlow";
        case SkillType::spellCreatureStrength:
            return "spellCreatureStrength";
        case SkillType::spellCreatureWeak:
            return "spellCreatureWeak";
        case SkillType::trapBoulder:
            return "trapBoulder";
        case SkillType::trapCannon:
            return "trapCannon";
        case SkillType::trapSpike:
            return "trapSpike";
        case SkillType::trapAlarm:
            return "trapAlarm";
        case SkillType::trapDoorWooden:
            return "trapDoorWooden";
        case SkillType::trapDoorIronbound:
            return "trapDoorIronbound";
        case SkillType::trapDoorSteel:
            return "trapDoorSteel";
        case SkillType::trapDoorBarricade:
            return "trapDoorBarricade";
        case SkillType::trapFear:
            return "trapFear";
        case SkillType::trapGas:
            return "trapGas";
        case SkillType::trapLightning:
            return "trapLightning";
        case SkillType::trapFireburst:
            return "trapFireburst";
        case SkillType::trapWatchBanner:
            return "trapWatchBanner";
        case SkillType::trapDoorSecret:
            return "trapDoorSecret";
        case SkillType::trapDoorRuned:
            return "trapDoorRuned";
        case SkillType::spellEyeEvil:
            return "spellEyeEvil";
        case SkillType::spellCreateGold:
            return "spellCreateGold";
        case SkillType::spellLightning:
            return "spellLightning";
        case SkillType::spellTremor:
            return "spellTremor";
        case SkillType::spellDefector:
            return "spellDefector";
        case SkillType::spellHexenHen:
            return "spellHexenHen";
        case SkillType::spellInferno:
            return "spellInferno";
        case SkillType::spellSummonChampion:
            return "spellSummonChampion";
        case SkillType::spellPossess:
            return "spellPossess";
        case SkillType::trapTrigger:
            return "trapTrigger";
        case SkillType::trapFreeze:
            return "trapFreeze";
        case SkillType::keeperDominion:
            return "keeperDominion";
        case SkillType::keeperHeartFortitude:
            return "keeperHeartFortitude";
        case SkillType::keeperHeartMending:
            return "keeperHeartMending";
        case SkillType::keeperManaFlow:
            return "keeperManaFlow";
        case SkillType::roomMerchant:
            return "roomMerchant";
        case SkillType::roomHerbGarden:
            return "roomHerbGarden";
        case SkillType::roomAlchemyLab:
            return "roomAlchemyLab";
        case SkillType::trapFineTools:
            return "trapFineTools";
        case SkillType::trapMasterTools:
            return "trapMasterTools";
        case SkillType::spellSunthornCultivation:
            return "spellSunthornCultivation";
        case SkillType::spellCurse:
            return "spellCurse";
        case SkillType::spellBlessing:
            return "spellBlessing";
        case SkillType::spellInvisibility:
            return "spellInvisibility";
        case SkillType::spellPlague:
            return "spellPlague";
        case SkillType::spellBreakWall:
            return "spellBreakWall";
        case SkillType::spellRevealEnemy:
            return "spellRevealEnemy";
        default:
            return "Unknown enum value:" + Helper::toString(static_cast<int>(type));
    }
}

//! \brief Returns the player-visible name of a research type.
//! \brief Returns the approved player-facing research entry name, in the chosen language.
std::string skillTypeToPlayerVisibleString(SkillType type)
{
    switch(type)
    {
        case SkillType::nullSkillType:
            return Translation::tr("research.nullskilltype.name");
        case SkillType::roomArena:
            return Translation::tr("research.roomarena.name");
        case SkillType::roomBridgeStone:
            return Translation::tr("research.roombridgestone.name");
        case SkillType::roomBridgeWooden:
            return Translation::tr("research.roombridgewooden.name");
        case SkillType::roomCasino:
            return Translation::tr("research.roomcasino.name");
        case SkillType::roomCrypt:
            return Translation::tr("research.roomcrypt.name");
        case SkillType::roomDormitory:
            return Translation::tr("research.roomdormitory.name");
        case SkillType::roomWorkshop:
            return Translation::tr("research.roomworkshop.name");
        case SkillType::roomHatchery:
            return Translation::tr("research.roomhatchery.name");
        case SkillType::roomLibrary:
            return Translation::tr("research.roomlibrary.name");
        case SkillType::roomTrainingHall:
            return Translation::tr("research.roomtraininghall.name");
        case SkillType::roomTreasury:
            return Translation::tr("research.roomtreasury.name");
        case SkillType::roomPrison:
            return Translation::tr("research.roomprison.name");
        case SkillType::roomInfirmary:
            return Translation::tr("research.roominfirmary.name");
        case SkillType::roomGhostRoom:
            return Translation::tr("research.roomghostroom.name");
        case SkillType::roomGuardRoom:
            return Translation::tr("research.roomguardroom.name");
        case SkillType::roomToilet:
            return Translation::tr("research.roomtoilet.name");
        case SkillType::roomTavern:
            return Translation::tr("research.roomtavern.name");
        case SkillType::tavernBeer:
            return Translation::tr("research.tavernbeer.name");
        case SkillType::roomSpa:
            return Translation::tr("research.roomspa.name");
        case SkillType::roomTemple:
            return Translation::tr("research.roomtemple.name");
        case SkillType::roomTorture:
            return Translation::tr("research.roomtorture.name");
        case SkillType::spellCallToWar:
            return Translation::tr("research.spellcalltowar.name");
        case SkillType::spellSummonWorker:
            return Translation::tr("research.spellsummonworker.name");
        case SkillType::spellCreatureHeal:
            return Translation::tr("research.spellcreatureheal.name");
        case SkillType::spellCreatureDefense:
            return Translation::tr("research.spellcreaturedefense.name");
        case SkillType::spellCreatureExplosion:
            return Translation::tr("research.spellcreatureexplosion.name");
        case SkillType::spellCreatureHaste:
            return Translation::tr("research.spellcreaturehaste.name");
        case SkillType::spellCreatureSlow:
            return Translation::tr("research.spellcreatureslow.name");
        case SkillType::spellCreatureStrength:
            return Translation::tr("research.spellcreaturestrength.name");
        case SkillType::spellCreatureWeak:
            return Translation::tr("research.spellcreatureweak.name");
        case SkillType::trapBoulder:
            return Translation::tr("research.trapboulder.name");
        case SkillType::trapCannon:
            return Translation::tr("research.trapcannon.name");
        case SkillType::trapSpike:
            return Translation::tr("research.trapspike.name");
        case SkillType::trapAlarm:
            return Translation::tr("research.trapalarm.name");
        case SkillType::trapDoorWooden:
            return Translation::tr("research.trapdoorwooden.name");
        case SkillType::trapDoorIronbound:
            return Translation::tr("research.trapdoorironbound.name");
        case SkillType::trapDoorSteel:
            return Translation::tr("research.trapdoorsteel.name");
        case SkillType::trapDoorBarricade:
            return Translation::tr("research.trapdoorbarricade.name");
        case SkillType::trapFear:
            return Translation::tr("research.trapfear.name");
        case SkillType::trapGas:
            return Translation::tr("research.trapgas.name");
        case SkillType::trapLightning:
            return Translation::tr("research.traplightning.name");
        case SkillType::trapFireburst:
            return Translation::tr("research.trapfireburst.name");
        case SkillType::trapWatchBanner:
            return Translation::tr("research.trapwatchbanner.name");
        case SkillType::trapDoorSecret:
            return Translation::tr("research.trapdoorsecret.name");
        case SkillType::trapDoorRuned:
            return Translation::tr("research.trapdoorruned.name");
        case SkillType::spellEyeEvil:
            return Translation::tr("research.spelleyeevil.name");
        case SkillType::spellCreateGold:
            return Translation::tr("research.spellcreategold.name");
        case SkillType::spellLightning:
            return Translation::tr("research.spelllightning.name");
        case SkillType::spellTremor:
            return Translation::tr("research.spelltremor.name");
        case SkillType::spellDefector:
            return Translation::tr("research.spelldefector.name");
        case SkillType::spellHexenHen:
            return Translation::tr("research.spellhexenhen.name");
        case SkillType::spellInferno:
            return Translation::tr("research.spellinferno.name");
        case SkillType::spellPossess:
            return Translation::tr("research.spellpossess.name");
        case SkillType::spellSummonChampion:
            return Translation::tr("research.spellsummonchampion.name");
        case SkillType::trapTrigger:
            return Translation::tr("research.traptrigger.name");
        case SkillType::trapFreeze:
            return Translation::tr("research.trapfreeze.name");
        case SkillType::keeperDominion:
            return Translation::tr("research.keeperdominion.name");
        case SkillType::keeperHeartFortitude:
            return Translation::tr("research.keeperheartfortitude.name");
        case SkillType::keeperHeartMending:
            return Translation::tr("research.keeperheartmending.name");
        case SkillType::keeperManaFlow:
            return Translation::tr("research.keepermanaflow.name");
        case SkillType::roomMerchant:
            return Translation::tr("research.roommerchant.name");
        case SkillType::roomHerbGarden:
            return Translation::tr("research.roomherbgarden.name");
        case SkillType::roomAlchemyLab:
            return Translation::tr("research.roomalchemylab.name");
        case SkillType::trapFineTools:
            return Translation::tr("research.trapfinetools.name");
        case SkillType::trapMasterTools:
            return Translation::tr("research.trapmastertools.name");
        case SkillType::spellSunthornCultivation:
            return Translation::tr("research.spellsunthorncultivation.name");
        case SkillType::spellCurse:
            return Translation::tr("research.spellcurse.name");
        case SkillType::spellBlessing:
            return Translation::tr("research.spellblessing.name");
        case SkillType::spellInvisibility:
            return Translation::tr("research.spellinvisibility.name");
        case SkillType::spellPlague:
            return Translation::tr("research.spellplague.name");
        case SkillType::spellBreakWall:
            return Translation::tr("research.spellbreakwall.name");
        case SkillType::spellRevealEnemy:
            return Translation::tr("research.spellrevealenemy.name");
        default:
            return "Unknown enum value:" + Helper::toString(static_cast<int>(type));
    }
}

bool isRewardSkill(SkillType type)
{
    return (type == SkillType::spellSummonChampion);
}
}

ODPacket& operator<<(ODPacket& os, const SkillType& type)
{
    os << static_cast<int32_t>(type);
    return os;
}

//! \brief Reads a SkillType. A value above countSkill marks the packet as failed and leaves type unchanged.
ODPacket& operator>>(ODPacket& is, SkillType& type)
{
    return ODPacket::readEnum<int32_t>(is, type, SkillType::countSkill);
}

std::ostream& operator<<(std::ostream& os, const SkillType& type)
{
    os << static_cast<int32_t>(type);
    return os;
}

std::istream& operator>>(std::istream& is, SkillType& type)
{
    int32_t tmp;
    is >> tmp;
    type = static_cast<SkillType>(tmp);
    return is;
}
