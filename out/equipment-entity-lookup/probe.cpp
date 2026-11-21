enum class GameEntityType
{
    unknown,
    creature,
    room,
    trap,
    tile,
    mapLight,
    spell,
    buildingObject,
    treasuryObject,
    chickenEntity,
    smallSpiderEntity,
    craftedTrap,
    missileObject,
    persistentObject,
    trapEntity,
    skillEntity,
    giftBoxEntity,
    lavaRock,
    dirtPileEntity,
    itemBagEntity,
    merchantEntity,
    herbBundleEntity,
    innkeeperEntity,
    infirmaryShamanEntity,
    ghostEntity,
    ghostBoxEntity,
    poolAttendantEntity
};
#include <string>
#include <vector>
#include <stdexcept>
//! \brief Supplies named registered entities to the actual typed lookup dispatcher.
struct GameEntity { std::string name;GameEntityType type=GameEntityType::unknown;
    //! \brief Constructs a named identity with its independently selected registered type.
    GameEntity(const std::string& value,GameEntityType kind=GameEntityType::unknown):name(value),type(kind){}
    //! \brief Supplies the type checked by the production ghost and box dispatcher.
    GameEntityType getObjectType()const{return type;}
};
//! \brief Uses the rendered registry interface expected by the production ghost dispatcher.
using RenderedMovableEntity=GameEntity;
//! \brief Isolates the real dispatch from unrelated map systems without replacing its switch.
struct GameMap {
    std::vector<GameEntity*> rendered;
    //! \brief Finds the exact registered rendered identity, or preserves a missing-name result.
    GameEntity* getRenderedMovableEntity(const std::string& name) {
        for(GameEntity* entity:rendered) if(entity->name==name) return entity;
        return nullptr;
    }
    //! \brief Keeps creatures outside this rendered-equipment fixture.
    GameEntity* getCreature(const std::string&) { return nullptr; }
    //! \brief Keeps spells outside this rendered-equipment fixture.
    GameEntity* getSpell(const std::string&) { return nullptr; }
    //! \brief Keeps lights outside this rendered-equipment fixture.
    GameEntity* getMapLight(const std::string&) { return nullptr; }
    //! \brief Keeps rooms outside this rendered-equipment fixture.
    GameEntity* getRoomByName(const std::string&) { return nullptr; }
    //! \brief Keeps traps outside this rendered-equipment fixture.
    GameEntity* getTrapByName(const std::string&) { return nullptr; }
    //! \brief Runs the unchanged production type-to-registry dispatcher.
    GameEntity* getEntityFromTypeAndName(GameEntityType type,const std::string& name);
};

//! \brief Runs the production entity lookup without changing its dispatch.
GameEntity* GameMap::getEntityFromTypeAndName(GameEntityType entityType,
    const std::string& entityName)
{
    switch(entityType)
    {
        case GameEntityType::creature:
            return getCreature(entityName);

        case GameEntityType::ghostEntity:
        case GameEntityType::ghostBoxEntity:
        {
            RenderedMovableEntity* entity=getRenderedMovableEntity(entityName);
            return entity!=nullptr && entity->getObjectType()==entityType?entity:nullptr;
        }

        case GameEntityType::buildingObject:
        case GameEntityType::chickenEntity:
        case GameEntityType::craftedTrap:
        case GameEntityType::missileObject:
        case GameEntityType::persistentObject:
        case GameEntityType::smallSpiderEntity:
        case GameEntityType::trapEntity:
        case GameEntityType::treasuryObject:
        case GameEntityType::skillEntity:
        case GameEntityType::giftBoxEntity:
        case GameEntityType::lavaRock:
        case GameEntityType::infirmaryShamanEntity:
        case GameEntityType::itemBagEntity:
        case GameEntityType::merchantEntity:
        case GameEntityType::herbBundleEntity:
        case GameEntityType::dirtPileEntity:
        case GameEntityType::innkeeperEntity:
        case GameEntityType::poolAttendantEntity:
            return getRenderedMovableEntity(entityName);

        case GameEntityType::spell:
            return getSpell(entityName);

        case GameEntityType::mapLight:
            return getMapLight(entityName);

        case GameEntityType::room:
            return getRoomByName(entityName);

        case GameEntityType::trap:
            return getTrapByName(entityName);

        default:
            break;
    }

    return nullptr;
}
//! \brief Verifies equipment and infirmary figures resolve their registered identities and missing names stay missing.
int main() {
    GameMap map; GameEntity bag={"ItemBag__171"},merchant={"Merchant_1"},bundle={"HerbBundle_1"},shaman={"InfirmaryShaman_1"};
    map.rendered={&bag,&merchant,&bundle,&shaman};
    const GameEntityType types[]={GameEntityType::itemBagEntity,GameEntityType::merchantEntity,GameEntityType::herbBundleEntity,GameEntityType::infirmaryShamanEntity};
    for(size_t index=0;index<map.rendered.size();++index) {
        if(map.getEntityFromTypeAndName(types[index],map.rendered[index]->name)!=map.rendered[index])
            throw std::runtime_error("registered equipment entity lookup failed");
        if(map.getEntityFromTypeAndName(types[index],"missing")!=nullptr)
            throw std::runtime_error("missing equipment identity resolved");
    }
    GameEntity ghost("Ghost_1",GameEntityType::ghostEntity),box("GhostBox_1",GameEntityType::ghostBoxEntity);
    map.rendered.push_back(&ghost);map.rendered.push_back(&box);
    if(map.getEntityFromTypeAndName(GameEntityType::ghostEntity,ghost.name)!=&ghost ||
       map.getEntityFromTypeAndName(GameEntityType::ghostBoxEntity,box.name)!=&box)
        throw std::runtime_error("registered ghost and box identities must resolve");
    if(map.getEntityFromTypeAndName(GameEntityType::ghostEntity,box.name)!=nullptr ||
       map.getEntityFromTypeAndName(GameEntityType::ghostBoxEntity,ghost.name)!=nullptr ||
       map.getEntityFromTypeAndName(GameEntityType::ghostEntity,bag.name)!=nullptr ||
       map.getEntityFromTypeAndName(GameEntityType::ghostBoxEntity,"missing")!=nullptr)
        throw std::runtime_error("ghost lookup must reject wrong concrete types and missing identities");
    if(map.getEntityFromTypeAndName(GameEntityType::unknown,bag.name)!=nullptr)
        throw std::runtime_error("unknown entity type resolved");
}
