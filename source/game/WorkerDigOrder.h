#ifndef WORKERDIGORDER_H
#define WORKERDIGORDER_H

//! \brief The order in which a digger chooses its next marked wall and whether it keeps a gold or gem wall while it
//! carries a full load to the treasury.
//! With "gold first" off a digger leaves its gold or gem wall when its load is full and chooses again after the
//! delivery. The wall it carried a load away from is marked; in the choice right after a delivery a marked wall
//! ranks with the occupied walls, so the digger first takes a wall nobody digs and nobody has carried a load away
//! from (an earth wall or a gold wall nobody has started). A gold wall holds many loads; without this a digger that
//! took one would stay there until it is empty and no earth wall would be dug meanwhile.
//! With "gold first" on gold and gem walls come first and a digger keeps its gold wall until it is empty, as before.
namespace WorkerDigOrder
{
//! \brief Returns the rank group of a marked wall for a digger, lower groups are chosen first.
//! \param goldFirst The keeper's "gold first" setting.
//! \param goldOrGem The wall is a gold or a gem wall.
//! \param occupied Another worker has reserved a dig place at the wall.
//! \param loadTaken A digger has carried a full load away from the wall.
//! \param afterDelivery The digger chooses right after it delivered a load it carried away from a wall.
inline int group(bool goldFirst, bool goldOrGem, bool occupied, bool loadTaken, bool afterDelivery)
{
    const bool taken = occupied || (!goldFirst && afterDelivery && loadTaken);
    return (goldFirst && !goldOrGem ? 2 : 0) + (taken ? 1 : 0);
}

//! \brief Returns whether a dig place ranks before the best dig place found so far: the lower group first, within a
//! group the place the digger already stands on, then the nearer place.
//! \param haveBest A best dig place was found before.
//! \param candidateGroup The group of the tested wall.
//! \param candidateHere The digger stands on the tested dig place.
//! \param candidateDistance The squared distance of the tested dig place.
//! \param bestGroup The group of the best wall so far.
//! \param bestHere The digger stands on the best dig place so far.
//! \param bestDistance The squared distance of the best dig place so far.
inline bool ranksBefore(bool haveBest, int candidateGroup, bool candidateHere, float candidateDistance,
                        int bestGroup, bool bestHere, float bestDistance)
{
    if(!haveBest)
        return true;
    if(candidateGroup != bestGroup)
        return candidateGroup < bestGroup;
    if(candidateHere != bestHere)
        return candidateHere;
    return candidateDistance < bestDistance;
}

//! \brief Returns whether a digger keeps its gold or gem wall reserved while it carries a full load to the treasury
//! and comes back to it. Only with "gold first" on; otherwise it leaves the wall and chooses again after the delivery.
//! \param goldFirst The keeper's "gold first" setting.
inline bool keepsWallForDelivery(bool goldFirst)
{
    return goldFirst;
}
}

#endif // WORKERDIGORDER_H
