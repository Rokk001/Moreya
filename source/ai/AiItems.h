#ifndef AIITEMS_H
#define AIITEMS_H

#include <string>

class Creature;
class KeeperAI;
struct AiEvent;

namespace ITEMS
{
//! \brief Whether a bought gift can be handed to the recipient now (owner answers 92 and 94): the recipient stands alive on
//! the map, alone among the keeper's creatures, on ground claimed for the keeper and outside a running arena fight.
bool canHandOver(KeeperAI& ai, Creature* recipient);
//! \brief Keeps a bought gift in the hand for a later hand-over to its recipient (row H04).
void holdGift(KeeperAI& ai, const std::string& recipient, const std::string& bag);
//! \brief Hands a held gift over once its recipient can take it; forgets it when the bag or the recipient is gone.
void retryGift(KeeperAI& ai);
//! \brief Records catalogue rows without a keeper command.
void classNRows(KeeperAI& ai);
//! \brief Uses held specials when their capacity, mood or combat condition applies; flags describe the current trigger.
void useStoredSpecial(KeeperAI& ai, const AiEvent& event, bool fightSession, bool periodicLook, bool afterSpell);
//! \brief Buys the highest-priced affordable gift for the strongest fighter on claimed ground.
void buyForStrongest(KeeperAI& ai);
}

#endif // AIITEMS_H
