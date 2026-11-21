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

// The helper relay backend is built only with the CMake option OD_NET_HELPER_RELAY, which is off by default
// (see docs/development/NETWORK-TRANSPORT.md).
#ifdef OD_NET_HELPER_RELAY
#include "network/HelperRelayProcess.h"
#include "network/HelperRelayTransport.h"
#endif

#include "utils/LogManager.h"

//! \brief The backend used by the game; TCP unless the helper relay is built and a helper process is set up.
NetTransportKind NetTransport::getDefaultKind()
{
#ifdef OD_NET_HELPER_RELAY
    // The relay backend carries direct TCP as well (host names, addresses, the host's own client on localhost),
    // so with a helper process set up (--net-helper) it serves every session
    if(HelperRelayProcess::getActive() != nullptr)
        return NetTransportKind::helperRelay;
#endif
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
            return std::unique_ptr<NetConnection>(new HelperRelayConnection(HelperRelayProcess::getActive()));
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
            return std::unique_ptr<NetListener>(new HelperRelayListener(HelperRelayProcess::getActive()));
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
