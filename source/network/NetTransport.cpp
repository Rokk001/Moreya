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

#include "network/NetTransport.h"
#include "network/TcpNetTransport.h"

// The helper relay backend is not built yet. OD_NET_HELPER_RELAY is defined nowhere; the stub exists
// to show where the backend plugs in (see docs/development/NETWORK-TRANSPORT.md).
#ifdef OD_NET_HELPER_RELAY
#include "network/HelperRelayTransport.h"
#endif

#include "utils/LogManager.h"

//! \brief The backend used by the game; TCP until the helper relay is built and offered in the menus.
NetTransportKind NetTransport::getDefaultKind()
{
    return NetTransportKind::tcp;
}

//! \brief Creates an unconnected connection; an unbuilt kind falls back to TCP with an error log.
std::unique_ptr<NetConnection> NetTransport::createConnection(NetTransportKind kind)
{
    switch(kind)
    {
        case NetTransportKind::tcp:
            return std::unique_ptr<NetConnection>(new TcpNetConnection);
        case NetTransportKind::helperRelay:
        {
#ifdef OD_NET_HELPER_RELAY
            return std::unique_ptr<NetConnection>(new HelperRelayConnection);
#else
            OD_LOG_ERR("The helper relay transport is not built, using TCP");
            break;
#endif
        }
        default:
            OD_LOG_ERR("Unknown transport kind, using TCP");
            break;
    }
    return std::unique_ptr<NetConnection>(new TcpNetConnection);
}

//! \brief Creates a listener; an unbuilt kind falls back to TCP with an error log.
std::unique_ptr<NetListener> NetTransport::createListener(NetTransportKind kind)
{
    switch(kind)
    {
        case NetTransportKind::tcp:
            return std::unique_ptr<NetListener>(new TcpNetListener);
        case NetTransportKind::helperRelay:
        {
#ifdef OD_NET_HELPER_RELAY
            return std::unique_ptr<NetListener>(new HelperRelayListener);
#else
            OD_LOG_ERR("The helper relay transport is not built, using TCP");
            break;
#endif
        }
        default:
            OD_LOG_ERR("Unknown transport kind, using TCP");
            break;
    }
    return std::unique_ptr<NetListener>(new TcpNetListener);
}
