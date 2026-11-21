#include "SpellType.h"

#include "network/ODPacket.h"

#include <istream>
#include <ostream>

std::istream& operator>>(std::istream& is, SpellType& tt)
{
    uint32_t tmp;
    is >> tmp;
    tt = static_cast<SpellType>(tmp);
    return is;
}

std::ostream& operator<<(std::ostream& os, const SpellType& tt)
{
    uint32_t tmp = static_cast<uint32_t>(tt);
    os << tmp;
    return os;
}

//! \brief Reads a SpellType. A value above nbSpells marks the packet as failed and leaves tt unchanged.
ODPacket& operator>>(ODPacket& is, SpellType& tt)
{
    return ODPacket::readEnum<uint32_t>(is, tt, SpellType::nbSpells);
}

ODPacket& operator<<(ODPacket& os, const SpellType& tt)
{
    uint32_t tmp = static_cast<uint32_t>(tt);
    os << tmp;
    return os;
}
