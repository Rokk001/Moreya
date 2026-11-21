#include "entities/NodeType.h"

#include "network/ODPacket.h"
#include "utils/Helper.h"

#include <istream>
#include <ostream>

std::istream& operator>>(std::istream& is, NodeType& rt)
{
  uint32_t tmp;
  is >> tmp;
  rt = static_cast<NodeType>(tmp);
  return is;
}

std::ostream& operator<<(std::ostream& os, const NodeType& rt)
{
  uint32_t tmp = static_cast<uint32_t>(rt);
  os << tmp;
  return os;
}

//! \brief Reads a NodeType. A value outside of the enum marks the packet as failed and leaves rt unchanged.
ODPacket& operator>>(ODPacket& is, NodeType& rt)
{
  return ODPacket::readEnum<uint32_t>(is, rt, NodeType::MTILES_NODE);
}

ODPacket& operator<<(ODPacket& os, const NodeType& rt)
{
  uint32_t tmp = static_cast<uint32_t>(rt);
  os << tmp;
  return os;
}
