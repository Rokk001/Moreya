#include "modes/ConsoleCommands.h"

#include "entities/Creature.h"
#include "entities/Tile.h"
#include "game/Player.h"
#include "game/Seat.h"
#include "gamemap/GameMap.h"
#include "goals/Goal.h"
#include "modes/ConsoleInterface.h"
#include "modes/GameEditorModeConsole.h"
#include "modes/InputManager.h"
#include "modes/ModeManager.h"
#include "modes/AbstractModeManager.h"
#include "modes/GameMode.h"
#include "network/ClientNotification.h"
#include "network/ODClient.h"
#include "network/ODServer.h"
#include "render/CreatureReactions.h"
#include "render/ODFrameListener.h"
#include "render/RenderManager.h"
#include "render/RoomAmbience.h"
#include "rooms/Room.h"
#include "utils/ConfigManager.h"
#include "utils/Helper.h"
#include "utils/LogManager.h"
#include "utils/Translation.h"


#include <CEGUI/widgets/Editbox.h>
#include <OgreCamera.h>
#include <OgreSceneManager.h>
#include <OgreSceneNode.h>
#include <OgreViewport.h>
#include <OgreShadowCameraSetupLiSPSM.h>
#include <boost/algorithm/string/join.hpp>

#include <pybind11/embed.h>
#include <pybind11/stl.h>
#include <functional>
#include <set>

 

template<typename M, typename Ret, typename... Args>
void addCommand(M &&m, const char *name, Ret (*cmdStrFunc)(Args...)) {
	m.def(
		name, 
		[cmdStrFunc, name](Args... args) {
			GameEditorModeConsole::getSingleton().mConsoleInterface.tryExecuteClientCommand(
				std::string(name) + ' ' + cmdStrFunc(args...),
				GameEditorModeConsole::getSingletonPtr()->mModeManager->getCurrentModeType(),
				*(GameEditorModeConsole::getSingletonPtr()->mModeManager)); 
		}, 
		getDocString(name).c_str()
	);
}

template<typename M>
void addCommand(M &&m, const char *name)
{
	addCommand(m, name, +[]() { return ""; });
        
}
 
 
 
 
PYBIND11_EMBEDDED_MODULE(cheats, m)
{
    addCommand(m, "addcreature",  +[](int seat, std::string creatureName,  std::string meshName, float x, float y, float z, std::string creatureDefinitionString, int level, int exp, std::string hpString, int wakeFullness, int hunger, int goldCarried, std::string weaponLeft, std::string weaponRight, std::string skillsList, int weaponDropDeath  ){ return Helper::toString(seat) + " " + creatureName + " " + meshName + " " +  Helper::toString(x) + " " +  Helper::toString(y) + " " +  Helper::toString(z) + " "  + creatureDefinitionString + " " + Helper::toString(level) + " " +  Helper::toString(exp) + " " + hpString + " " +  Helper::toString(wakeFullness) + " " +  Helper::toString(hunger) + " " +  Helper::toString(goldCarried) + " " + weaponLeft + " " + weaponRight + " " + skillsList + " " +  Helper::toString(weaponDropDeath) ;});    
    addCommand(m, "addgold", +[](int seat, int gold){ return Helper::toString(seat)+ " " +Helper::toString(gold); });
    addCommand(m, "addmana", +[](int seat, int mana){ return Helper::toString(seat)+ " " +Helper::toString(mana); });
    addCommand(m, "catmullspline", +[](std::vector<double> points){ return Helper::toString(points);  });    
    addCommand(m, "circlearound",  +[](double x, double y, double radious){ return Helper::toString(x) + " " +  Helper::toString(y) + " " + Helper::toString(radious);      });
    addCommand(m, "creaturevisdebug", +[](std::string subject){ return subject; });
    addCommand(m, "enableZPrePass");
    addCommand(m, "farclip",+[](float distance){ return Helper::toString(distance); });
    addCommand(m, "fps", +[](int frames){ return Helper::toString(frames); });
    addCommand(m, "getposition");
    addCommand(m, "getshadowtexturecount"); 
    addCommand(m, "helpmessage");
    addCommand(m, "keys"); 
    addCommand(m, "light", +[](float r, float g, float b){ return Helper::toString(r) + " " + Helper::toString(g) + " " + Helper::toString(b) ;});    
    addCommand(m, "list", +[](std::string subject){ return subject; });
    addCommand(m, "listmeshanims", +[](std::string name){ return name;});
    addCommand(m, "logfloodfill");
    addCommand(m, "maxtime",  +[](int time){ return Helper::toString(time);});
    addCommand(m, "nearclip",+[](float distance){ return Helper::toString(distance); });
    addCommand(m, "printentities");
    addCommand(m, "printnodes");    
    addCommand(m, "seatvisdebug",  +[](int seat){ return Helper::toString(seat); });
    addCommand(m, "setShadowFarClipDistance",   +[](float distance){ return Helper::toString(distance); });
    addCommand(m, "setShadowNearClipDistance",   +[](float distance){ return Helper::toString(distance); });    
    addCommand(m, "setcamerafovy",  +[](double fovy){ return Helper::toString(fovy);});
    addCommand(m, "setcameralightdirectionthreshold",  +[](double threshold){ return Helper::toString(threshold);});    
    addCommand(m, "setcreaturedest",  +[](std::string name, int x, int y){  return name + " " +  Helper::toString(x)+ " " +Helper::toString(y);     });
    addCommand(m, "setcreaturelevel",  +[](std::string name, int level){ return name + " " + Helper::toString(level);});
    addCommand(m, "setloglevel",  +[](int level){ return Helper::toString(level);});
    addCommand(m, "setoptimaladjustfactor",  +[](float factor){ return Helper::toString(factor);});
    addCommand(m, "setshadowcamerafovy",  +[](double fovy){ return Helper::toString(fovy);});
    addCommand(m, "termwidth", +[](int width){ return Helper::toString(width); });
    addCommand(m, "togglefow");        
    addCommand(m, "triggercompositor", +[](std::string name){ return name;});
    addCommand(m, "unlockskills");
    
}



namespace
{

//! \brief The help message of the console in the chosen language: the introduction and the commands by group.
std::string getHelpMessage()
{
    std::string message = Translation::tr("console.help.intro");
    message += "\n\n" + Translation::tr("console.help.available");
    message += "\n\n" + Translation::tr("console.help.general");
    const char* const GENERAL[] = {"help", "helpkeys", "list", "maxtime", "termwidth"};
    const char* const CHEATS[] = {"addcreature", "setcreaturelevel", "addgold", "addmana", "icanseedeadpeople"};
    const char* const DEVELOPER[] = {"fps", "ambientlight", "nearclip", "farclip", "creaturevisdebug", "seatvisdebug",
        "setcreaturedest", "listmeshanims", "reaction", "roomambience", "triggercompositor", "catmullspline",
        "circlearound", "setcamerafovy", "logfloodfill"};
    for(const char* command : GENERAL)
        message += "\n\t" + Translation::tr(std::string("console.help.cmd.") + command);
    message += "\n\n" + Translation::tr("console.help.cheats");
    for(const char* command : CHEATS)
        message += "\n\t" + Translation::tr(std::string("console.help.cmd.") + command);
    message += "\n\n" + Translation::tr("console.help.developer");
    for(const char* command : DEVELOPER)
        message += "\n\t" + Translation::tr(std::string("console.help.cmd.") + command);
    return message;
}

//! \brief Template function to get/set a variable from the ODFrameListener object
template<typename ValType, typename Getter, typename Setter>
Command::Result cSetFrameListenerVar(Getter getter,
                        Setter setter,
                        ODFrameListener& fl,
                        const std::string& name,
                        const Command::ArgumentList_t& args, ConsoleInterface& c)
{
    if(args.size() < 2)
    {
        c.print(Translation::tr("console.var.is", {{"name", Translation::tr(name)}, {"value", Helper::toString(getter(fl))}}));
    }
    else
    {
        ValType v = Helper::stringToT<ValType>(args[1]);
        setter(fl, v);
        c.print(Translation::tr("console.var.set", {{"name", Translation::tr(name)}, {"value", Helper::toString(v)}}));
    }
    return Command::Result::SUCCESS;
}

Command::Result cSendCmdToServer(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    // If we should send a console command, we do it
    if(!ODClient::getSingleton().isConnected())
    {
        c.print(Translation::tr("console.send.notconnected"));
        return Command::Result::FAILED;
    }

    if(args.empty())
    {
        c.print(Translation::tr("console.send.empty"));
        return Command::Result::INVALID_ARGUMENT;
    }

    ClientNotification *clientNotification = new ClientNotification(
        ClientNotificationType::askExecuteConsoleCommand);
    uint32_t nbArgs = args.size();
    clientNotification->mPacket << nbArgs;
    for(const std::string& str : args)
        clientNotification->mPacket << str;

    ODClient::getSingleton().queueClientNotification(clientNotification);
    return Command::Result::SUCCESS;
}

Command::Result cAmbientLight(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    Ogre::SceneManager* mSceneMgr = RenderManager::getSingletonPtr()->getSceneManager();

    if (args.size() < 2)
    {
        // Display the current ambient light values.
        Ogre::ColourValue curLight = mSceneMgr->getAmbientLight();
        c.print(Translation::tr("console.ambient.current", {{"value", Helper::toString(curLight)}}));
        return Command::Result::SUCCESS;
    }
    else if(args.size() >= 4)
    {
        // Set the new color.
        Ogre::ColourValue v(Helper::toFloat(args[1]), Helper::toFloat(args[2]), Helper::toFloat(args[3]));

        mSceneMgr->setAmbientLight(v);
        c.print(Translation::tr("console.ambient.set", {{"value", Helper::toString(v)}}));
    }
    else
    {
        c.print(Translation::tr("console.ambient.needvalues"));
        return Command::Result::INVALID_ARGUMENT;
    }
    return Command::Result::SUCCESS;
}

Command::Result cShadowFarClipDistance(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if (args.size() < 2)
    {
        // Display the current shadow far clip distance
        c.print(Translation::tr("console.shadow.farcurrent", {{"value", Helper::toString(RenderManager::getSingletonPtr()->mHandLight->getShadowFarClipDistance())}}));
    }
    else if(args.size() >= 2)
    {
        RenderManager::getSingletonPtr()->mHandLight->setShadowFarClipDistance(Helper::toFloat(args[1]));
        c.print(Translation::tr("console.shadow.farset", {{"value", Helper::toString(RenderManager::getSingletonPtr()->mHandLight->getShadowFarClipDistance())}}));
  
    }
        return Command::Result::SUCCESS;
}

Command::Result cShadowNearClipDistance(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if (args.size() < 2)
    {
        // Display the current shadow near clip distance
        c.print(Translation::tr("console.shadow.nearcurrent", {{"value", Helper::toString(RenderManager::getSingletonPtr()->mHandLight->getShadowNearClipDistance())}}));
        return Command::Result::SUCCESS;
    }
    else if(args.size() >= 2)
    {
        RenderManager::getSingletonPtr()->mHandLight->setShadowNearClipDistance(Helper::toFloat(args[1]));
        c.print(Translation::tr("console.shadow.nearset", {{"value", Helper::toString(RenderManager::getSingletonPtr()->mHandLight->getShadowNearClipDistance())}}));

    }
        return Command::Result::SUCCESS;  
}


Command::Result cSetOptimalAdjustFactor(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if (args.size() < 2)
    {
        // Display the current shadow near clip distance
        c.print(Translation::tr("console.shadow.adjustfactor", {{"value", Helper::toString(dynamic_cast<Ogre::LiSPSMShadowCameraSetup*>(RenderManager::getSingletonPtr()->getSceneManager()->getShadowCameraSetup().get())->getOptimalAdjustFactor() )}}));
        return Command::Result::SUCCESS;
    }
    else if(args.size() >= 2)
    {
        dynamic_cast<Ogre::LiSPSMShadowCameraSetup*>(RenderManager::getSingletonPtr()->getSceneManager()->getShadowCameraSetup().get())->setOptimalAdjustFactor(Helper::toFloat(args[1]));

        
 
    }
        return Command::Result::SUCCESS; 
}

Command::Result cSetUseSimpleOptimalAdjust(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if (args.size() < 2)
    {
        c.print(Translation::tr("console.shadow.simpleadjust", {{"value", Helper::toString(dynamic_cast<Ogre::LiSPSMShadowCameraSetup*>(RenderManager::getSingletonPtr()->getSceneManager()->getShadowCameraSetup().get())->getUseSimpleOptimalAdjust() )}})) ;
        return Command::Result::SUCCESS;        
    }
    else
    {
        dynamic_cast<Ogre::LiSPSMShadowCameraSetup*>(RenderManager::getSingletonPtr()->getSceneManager()->getShadowCameraSetup().get())->setUseSimpleOptimalAdjust(Helper::toBool(args[1]));
        return Command::Result::SUCCESS; 
    }

}

Command::Result cSetCameraLightDirectionThreshold(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{

    if (args.size() < 2)
    {
        c.print(Translation::tr("console.shadow.lightthreshold", {{"value", Helper::toString(dynamic_cast<Ogre::LiSPSMShadowCameraSetup*>(RenderManager::getSingletonPtr()->getSceneManager()->getShadowCameraSetup().get())->getCameraLightDirectionThreshold().valueDegrees())}})) ;
        return Command::Result::SUCCESS;        
    }
    else
    {
        dynamic_cast<Ogre::LiSPSMShadowCameraSetup*>(RenderManager::getSingletonPtr()->getSceneManager()->getShadowCameraSetup().get())->setCameraLightDirectionThreshold(Ogre::Degree(Helper::toInt(args[1])));
        return Command::Result::SUCCESS; 
    }

}


Command::Result cGetShadowTextureCount(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{

        c.print(Translation::tr("console.shadow.texturecount", {{"value", Helper::toString(RenderManager::getSingletonPtr()->getSceneManager()->getShadowTextureCount())}})) ;
        return Command::Result::SUCCESS;        
}

Command::Result cSetShadowCameraFovY(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
        Ogre::Camera* mShadowCam = RenderManager::getSingletonPtr()->getSceneManager()->createCamera("mShadowCam");
        RenderManager::getSingletonPtr()->mHandLight->setSpotlightRange( Ogre::Degree(145),Ogre::Degree(145));       
        RenderManager::getSingletonPtr()->getSceneManager()->getShadowCameraSetup()->getShadowCamera(RenderManager::getSingletonPtr()->getSceneManager(), RenderManager::getSingletonPtr()->getViewport()->getCamera(), RenderManager::getSingletonPtr()->getViewport(), RenderManager::getSingletonPtr()->mHandLight, mShadowCam, 0);
        
        // mShadowCam->setFOVy(Ogre::Degree(90)); 


        
    if (args.size() < 2)
    {

        c.print(Translation::tr("console.shadow.fovy", {{"value", Helper::toString(mShadowCam->getFOVy().valueDegrees())}})) ;
        return Command::Result::SUCCESS;        
    }
    else
    {
        Ogre::Radian rr;
        rr = Ogre::Degree(Helper::toFloat(args[1]));
        return Command::Result::SUCCESS; 
    }

}

Command::Result cFPS(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if(args.size() < 2)
    {
        c.print(Translation::tr("console.fps.current",
                {{"value", Helper::toString(ODFrameListener::getSingleton().getMaxFPS())}}));
    }
    else if(args.size() >= 2)
    {
        int fps = Helper::toInt(args[1]);
        ODFrameListener::getSingleton().setMaxFPS(fps);
        c.print(Translation::tr("console.fps.set", {{"value", Helper::toString(fps)}}));
    }
    return Command::Result::SUCCESS;
}


Command::Result cGetPosition(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager& am)
{
    InputManager& inputManager = InputManager::getSingleton();
    c.print(Translation::tr("console.position",
        {{"x", Helper::toString(inputManager.mXPos)}, {"y", Helper::toString(inputManager.mYPos)}}));
    return Command::Result::SUCCESS;
}


Command::Result cPrintNodes(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    std::function<void(Ogre::SceneNode*)> printNodesAux = [&](Ogre::SceneNode* sn){
        c.print(sn->getName());
        Ogre::Node::ChildNodeMap   chnm = sn->getChildren();
        for(Ogre::Node* it : chnm   ){
            printNodesAux( static_cast<Ogre::SceneNode*>(it));
        } 
    };
    Ogre::SceneManager* mSceneMgr = RenderManager::getSingletonPtr()->getSceneManager();   
    printNodesAux(mSceneMgr->getRootSceneNode());
    return Command::Result::SUCCESS;
}


Command::Result cPrintEntities(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    std::function<void(Ogre::SceneNode*)> printNodesAux = [&](Ogre::SceneNode* sn){
  	for(Ogre::MovableObject* mv: sn->getAttachedObjectIterator())
            c.print(mv->getName());
        
        Ogre::Node::ChildNodeMap   chnm = sn->getChildren();
        for(Ogre::Node* it : chnm   ){
            printNodesAux( static_cast<Ogre::SceneNode*>(it));
        } 
    };
    Ogre::SceneManager* mSceneMgr = RenderManager::getSingletonPtr()->getSceneManager();   
    printNodesAux(mSceneMgr->getRootSceneNode());
    return Command::Result::SUCCESS;
}


Command::Result cSrvAddCreature(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    if (args.size() < 6)
    {
        c.print(Translation::tr("console.addcreature.invalidargs"));
        return Command::Result::INVALID_ARGUMENT;
    }

    // We remove the first argument (the console command)
    Command::ArgumentList_t tmp = args;
    tmp.erase(tmp.begin());
    std::string str = boost::algorithm::join(tmp, "\t");
    std::stringstream ss(str);
    Creature* creature = Creature::getCreatureFromStream(&gameMap, ss);
    if(creature == nullptr)
    {
        OD_LOG_INF("Cannot creature proper creature from string=" + str);
        return Command::Result::FAILED;
    }

    creature->addToGameMap();
    //Set up definition for creature. This was previously done in createMesh for some reason.
    creature->setupDefinition(gameMap, *ConfigManager::getSingleton().getCreatureDefinitionDefaultWorker());
    //Set position to update info on what tile the creature is in.
    creature->setPosition(creature->getPosition());

    return Command::Result::SUCCESS;
}

Command::Result cList(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager& mm)
{
    ODFrameListener* frameListener = ODFrameListener::getSingletonPtr();
    GameMap* gameMap = frameListener->getClientGameMap();

    if (args.size() < 2)
    {
        c.print(Translation::tr("console.list.available"));
        return Command::Result::SUCCESS;
    }

    std::stringstream stringStr;

    if (args[1].compare("creatures") == 0)
    {
        stringStr << Translation::tr("console.list.creatures");
        for (Creature* creature : gameMap->getCreatures())
        {
            GameEntity::exportToStream(creature, stringStr);
            stringStr << std::endl;
        }
    }
    else if (args[1].compare("classes") == 0)
    {
        stringStr << Translation::tr("console.list.classes");
        for (unsigned int i = 0; i < gameMap->numClassDescriptions(); ++i)
        {
            const CreatureDefinition* currentClassDesc = gameMap->getClassDescription(i);
            stringStr << currentClassDesc << "\n";
        }
    }
    else if (args[1].compare("players") == 0)
    {
        stringStr << Translation::tr("console.list.localplayer")
                  << Translation::tr("console.list.me") << "\t\t" << gameMap->getLocalPlayer()->getNick() << "\t"
                  << gameMap->getLocalPlayer()->getSeat()->getId() << "\t"
                  << gameMap->getLocalPlayer()->getSeat()->getTeamId() << "\n\n";

        stringStr << Translation::tr("console.list.player");

        for (Player* player : gameMap->getPlayers())
        {
            stringStr << player->getId() << "\t\t" << player->getNick() << "\t"
                    << player->getSeat()->getId() << "\t"
                    << player->getSeat()->getTeamId() << "\n\n";
        }
    }
    else if (args[1].compare("network") == 0)
    {
        if (mm.getCurrentModeType() == AbstractModeManager::EDITOR)
        {
            stringStr << Translation::tr("console.list.network.editor");
        }
        else if (ODServer::getSingleton().isConnected())
        {
            stringStr << Translation::tr("console.list.network.server");
        }
        else
        {
            stringStr << Translation::tr("console.list.network.client");
        }
    }
    else if (args[1].compare("rooms") == 0)
    {
        stringStr << Translation::tr("console.list.rooms");
        for (Room* room : gameMap->getRooms())
        {
            stringStr << room->getName() << "\t" << room->getSeat()->getId()
                    << "\t" << room->numCoveredTiles() << "\n";
        }
    }
    else if (args[1].compare("colors") == 0 || args[1].compare("colours") == 0)
    {
        stringStr << Translation::tr("console.list.colors");
        const std::vector<Seat*> seats = gameMap->getSeats();
        for (Seat* seat : seats)
        {
            Ogre::ColourValue color = seat->getColorValue();

            stringStr << "\n" << seat->getId() << "\t\t" << color.r
                    << "\t\t" << color.g << "\t\t" << color.b;
        }
    }
    else if (args[1].compare("goals") == 0)
    {
        // Loop over the list of unmet goals for the seat we are sitting in an print them.
        stringStr << Translation::tr("console.list.goals.unfinished");
        for (unsigned int i = 0; i < gameMap->getLocalPlayer()->getSeat()->numUncompleteGoals(); ++i)
        {
            Seat* s = gameMap->getLocalPlayer()->getSeat();
            Goal* tempGoal = s->getUncompleteGoal(i);
            stringStr << tempGoal->getName() << ":\t"
                    << Translation::resolve(tempGoal->getDescription(*s)) << "\n";
        }

        // Loop over the list of completed goals for the seat we are sitting in an print them.
        stringStr << Translation::tr("console.list.goals.completed");
        for (unsigned int i = 0; i < gameMap->getLocalPlayer()->getSeat()->numCompletedGoals(); ++i)
        {
            Seat* seat = gameMap->getLocalPlayer()->getSeat();
            Goal* tempGoal = seat->getCompletedGoal(i);
            stringStr << tempGoal->getName() << ":\t"
                    << Translation::resolve(tempGoal->getSuccessMessage(*seat)) << "\n";
        }
    }
    // else if (args[1].compare("lights") == 0)
    // {
    //     // // Loop over the list of ligths and print them.
    //     // stringStr << "Existing lights \n";
    //     // const Ogre::LightList &ll = ODFrameListener::getSingletonPtr()->getCameraManager()->getCamera("RTS")->getLights();
    //     // OD_LOG_INF("The size of LigthList is " + Helper::toString(ll.size()));
    //     // int ii =0 ;
    //     // for (auto light : ll )
    //     // {
    //     //     stringStr << ii << ": " << light->getName() << " \n" ;
    //     //     ++ii;
    //     // }


    // }



    
    else
    {
        stringStr << Translation::tr("console.list.unknown");
    }

    c.print("+\n" + stringStr.str() + "\n");
    return Command::Result::SUCCESS;
}

Command::Result cSrvCreatureVisDebug(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    if(args.size() < 2)
        return Command::Result::INVALID_ARGUMENT;

    const std::string& name = args[1];
    gameMap.consoleToggleCreatureVisualDebug(name);

    return Command::Result::SUCCESS;
}

Command::Result cSrvSeatVisDebug(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    if(args.size() < 2)
        return Command::Result::INVALID_ARGUMENT;

    int seatId = Helper::toInt(args[1]);
    gameMap.consoleToggleSeatVisualDebug(seatId);
    return Command::Result::SUCCESS;
}

Command::Result cSrvToggleFOW(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    gameMap.consoleAskToggleFOW();
    return Command::Result::SUCCESS;
}

Command::Result cSrvSetCreatureLevel(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    if(args.size() < 3)
        return Command::Result::INVALID_ARGUMENT;

    const std::string& name = args[1];
    uint32_t level = Helper::toUInt32(args[2]);
    gameMap.consoleSetLevelCreature(name, level);
    return Command::Result::SUCCESS;
}

Command::Result cCircleAround(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if(args.size() < 4)
    {
        c.print(Translation::tr("console.circlearound.args"));
        return Command::Result::INVALID_ARGUMENT;
    }

    ODFrameListener& frameListener = ODFrameListener::getSingleton();
    CameraManager* cm = frameListener.getCameraManager();
    int centerX = Helper::toDouble(args[1]);
    int centerY = Helper::toDouble(args[2]);
    unsigned int radius = Helper::toDouble(args[3]);


    cm->circleAround(centerX, centerY, radius);
    return Command::Result::SUCCESS;
}

Command::Result cHermiteCatmullSpline(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    //TODO: only works on larger maps with coordinates > 10
    if(args.size() < 5)
    {
        c.print(Translation::tr("console.catmullspline.args"));
        return Command::Result::INVALID_ARGUMENT;
    }


    CameraManager* cm = ODFrameListener::getSingleton().getCameraManager();
    std::size_t numPairs = (args.size() - 1) / 2;

    cm->resetHCSNodes(numPairs);
    for(std::size_t i = 1; i < args.size() - 1; i +=2)
    {
        int a = Helper::toInt(args[i]);
        int b = Helper::toInt(args[i + 1]);
        //TODO: Why are the points specified as integers?
        cm->addHCSNodes(a, b);
        c.print(Translation::tr("console.catmullspline.node", {{"a", args[i]}, {"b", args[i + 1]}}));
    }

    cm->setCatmullSplineMode(true);
    return Command::Result::SUCCESS;
}

Command::Result cSrvAddGold(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    if(args.size() < 3)
        return Command::Result::INVALID_ARGUMENT;

    int seatId = Helper::toInt(args[1]);
    int gold = Helper::toInt(args[2]);
    gameMap.addGoldToSeat(gold, seatId);
    return Command::Result::SUCCESS;
}

Command::Result cSrvAddMana(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    if(args.size() < 3)
        return Command::Result::INVALID_ARGUMENT;

    int seatId = Helper::toInt(args[1]);
    int mana = Helper::toInt(args[2]);
    gameMap.addManaToSeat(mana, seatId);
    return Command::Result::SUCCESS;
}

Command::Result cSrvSetCreatureDest(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    if(args.size() < 4)
        return Command::Result::INVALID_ARGUMENT;

    const std::string& name = args[1];
    int x = Helper::toInt(args[2]);
    int y = Helper::toInt(args[3]);
    gameMap.consoleSetCreatureDestination(name, x, y);
    return Command::Result::SUCCESS;
}

Command::Result cSrvLogFloodFill(const Command::ArgumentList_t&, ConsoleInterface& c, GameMap& gameMap)
{
    gameMap.logFloodFileTiles();
    return Command::Result::SUCCESS;
}

Command::Result cSetCameraFOVy(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    Ogre::Camera* cam = ODFrameListener::getSingleton().getCameraManager()->getActiveCamera();
    if(args.size() < 2)
    {
        c.print(Translation::tr("console.camera.fovy", {{"value", Helper::toString(cam->getFOVy().valueDegrees())}}));
    }
    else
    {
        cam->setFOVy(Ogre::Degree(static_cast<Ogre::Real>(Helper::toFloat(args[1]))));
    }
    return Command::Result::SUCCESS;
}

Command::Result cEnableZPrePass(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    ODFrameListener::getSingleton().mRenderManager->setup();
    ODFrameListener::getSingleton().mRenderManager->m_ZPrePassEnabled = true;    
    c.print(Translation::tr("console.zprepass"));
    return Command::Result::SUCCESS;
}

Command::Result cListMeshAnims(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if(args.size() < 2)
    {
        c.print(Translation::tr("console.meshanims.needname"));
        return Command::Result::INVALID_ARGUMENT;
    }
    std::string anims = RenderManager::consoleListAnimationsForMesh(args[1]);
    c.print(Translation::tr("console.meshanims.result", {{"mesh", args[1]}, {"anims", anims}}));
    return Command::Result::SUCCESS;
}

//! \brief Console command "reaction": lists the reaction events, reloads the file or shows an event on a
//! creature (the one under the pointer, a named one, all visible ones or as a staggered group).
Command::Result cCreatureReaction(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    CreatureReactions* reactions = CreatureReactions::getSingletonPtr();
    if(reactions == nullptr)
    {
        c.print(Translation::tr("console.reaction.unavailable"));
        return Command::Result::FAILED;
    }

    if((args.size() < 2) || (args[1] == "list"))
    {
        c.print(Translation::tr("console.reaction.mode", {{"mode", CreatureReactions::modeToString(reactions->getMode())},
            {"running", Helper::toString(reactions->getNbRunning())}}));
        const std::map<std::string, ReactionEvent>& events = reactions->getConfig().getEvents();
        for(std::map<std::string, ReactionEvent>::const_iterator it = events.begin(); it != events.end(); ++it)
        {
            std::string variantNames;
            for(const ReactionVariant& variant : it->second.mVariants)
                variantNames += " " + variant.mName;

            c.print(Translation::tr("console.reaction.event", {{"event", it->first},
                {"priority", CreatureReactionConfig::priorityToString(it->second.mPriority)},
                {"count", Helper::toString(it->second.mVariants.size())}, {"variants", variantNames}}));
        }
        c.print(Translation::tr("console.reaction.usage"));
        return Command::Result::SUCCESS;
    }

    if(args[1] == "reload")
    {
        bool loaded = reactions->reloadConfig();
        c.print(Translation::tr(loaded ? "console.reaction.reloaded" : "console.reaction.reloadfailed"));
        return loaded ? Command::Result::SUCCESS : Command::Result::FAILED;
    }

    const std::string& eventName = args[1];
    if(reactions->getConfig().getEvent(eventName) == nullptr)
    {
        c.print(Translation::tr("console.reaction.unknownevent", {{"event", eventName}}));
        return Command::Result::INVALID_ARGUMENT;
    }

    GameMap* gameMap = ODFrameListener::getSingleton().getClientGameMap();
    bool asGroup = (args.size() >= 3) && (args[2] == "group");
    std::vector<Creature*> creatures;
    if((args.size() >= 3) && ((args[2] == "all") || asGroup))
    {
        for(Creature* creature : gameMap->getCreatures())
        {
            if(reactions->isCreatureNearCamera(creature))
                creatures.push_back(creature);
        }
    }
    else if(args.size() >= 3)
    {
        Creature* creature = gameMap->getCreature(args[2]);
        if(creature == nullptr)
        {
            c.print(Translation::tr("console.reaction.unknowncreature", {{"name", args[2]}}));
            return Command::Result::INVALID_ARGUMENT;
        }
        creatures.push_back(creature);
    }
    else if(InputManager::getSingleton().mHighlightedCreature != nullptr)
    {
        creatures.push_back(InputManager::getSingleton().mHighlightedCreature);
    }
    else
    {
        c.print(Translation::tr("console.reaction.nocreature"));
        return Command::Result::INVALID_ARGUMENT;
    }

    // A fixed variant can only be asked for single creatures, a group chooses for itself
    std::string variantName;
    if(args.size() >= 4)
        variantName = args[3];

    if(asGroup)
    {
        reactions->triggerGroup(eventName, creatures, true);
        c.print(Translation::tr("console.reaction.group", {{"event", eventName}, {"count", Helper::toString(creatures.size())}}));
        return Command::Result::SUCCESS;
    }

    uint32_t nbStarted = 0;
    for(Creature* creature : creatures)
    {
        if(reactions->trigger(creature, eventName, true, variantName))
            ++nbStarted;
    }
    c.print(Translation::tr("console.reaction.started", {{"event", eventName}, {"started", Helper::toString(nbStarted)},
        {"count", Helper::toString(creatures.size())}}));
    return Command::Result::SUCCESS;
}

//! \brief Console command roomambience: lists the effects, reloads the configuration, sets the mode or starts an event at a tile
Command::Result cRoomAmbience(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    RoomAmbience* ambience = RoomAmbience::getSingletonPtr();
    if(ambience == nullptr)
    {
        c.print(Translation::tr("console.ambience.unavailable"));
        return Command::Result::FAILED;
    }

    if((args.size() < 2) || (args[1] == "list"))
    {
        c.print(Translation::tr("console.ambience.mode", {{"mode", RoomAmbience::modeToString(ambience->getMode())},
            {"particles", Helper::toString(ambience->getNbParticleSystems())},
            {"objects", Helper::toString(ambience->getNbMovedObjects())}}));
        std::set<std::string> events;
        const std::vector<AmbienceEffect>& effects = ambience->getConfig().getEffects();
        for(const AmbienceEffect& effect : effects)
        {
            if(effect.mTarget == AmbienceTarget::event)
                events.insert(effect.mEvent);
        }
        c.print(Translation::tr("console.ambience.effects", {{"count", Helper::toString(effects.size())}}));
        for(const std::string& eventName : events)
            c.print(Translation::tr("console.ambience.event", {{"event", eventName}}));
        c.print(Translation::tr("console.ambience.usage"));
        return Command::Result::SUCCESS;
    }

    if(args[1] == "reload")
    {
        bool loaded = ambience->reloadConfig();
        c.print(Translation::tr(loaded ? "console.ambience.reloaded" : "console.ambience.reloadfailed"));
        return loaded ? Command::Result::SUCCESS : Command::Result::FAILED;
    }

    if(args[1] == "mode")
    {
        if(args.size() < 3)
        {
            c.print(Translation::tr("console.ambience.needmode"));
            return Command::Result::INVALID_ARGUMENT;
        }

        ambience->setMode(RoomAmbience::modeFromString(args[2]));
        c.print(Translation::tr("console.ambience.modeset", {{"mode", RoomAmbience::modeToString(ambience->getMode())}}));
        return Command::Result::SUCCESS;
    }

    GameMap* gameMap = ODFrameListener::getSingleton().getClientGameMap();
    int x = InputManager::getSingleton().mXPos;
    int y = InputManager::getSingleton().mYPos;
    if(args.size() >= 4)
    {
        x = Helper::toInt(args[2]);
        y = Helper::toInt(args[3]);
    }

    Tile* tile = gameMap->getTile(x, y);
    if(tile == nullptr)
    {
        c.print(Translation::tr("console.ambience.notile", {{"x", Helper::toString(x)}, {"y", Helper::toString(y)}}));
        return Command::Result::INVALID_ARGUMENT;
    }

    uint32_t nbStarted = ambience->triggerEvent(args[1], tile->getPosition(), true);
    c.print(Translation::tr("console.ambience.started", {{"event", args[1]}, {"count", Helper::toString(nbStarted)},
        {"x", Helper::toString(x)}, {"y", Helper::toString(y)}}));
    return Command::Result::SUCCESS;
}

Command::Result cSetLogLevel(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if(args.size() < 2)
    {
        c.print(Translation::tr("console.loglevel.need"));
        return Command::Result::INVALID_ARGUMENT;
    }

    if(args.size() == 2)
    {
        uint32_t val = Helper::toUInt32(args[1]);
        LogMessageLevel lml = static_cast<LogMessageLevel>(val);
        c.print(Translation::tr("console.loglevel.global", {{"level", std::string(LogMessageLevelToString(lml))}}));
        LogManager::getSingleton().setLevel(lml);
        return Command::Result::SUCCESS;
    }

    const std::string& module = args[1];
    uint32_t val = Helper::toUInt32(args[2]);
    LogMessageLevel lml = static_cast<LogMessageLevel>(val);
    c.print(Translation::tr("console.loglevel.module", {{"module", module}, {"level", LogMessageLevelToString(lml)}}));
    LogManager::getSingleton().setModuleLevel(module.c_str(), lml);
    return Command::Result::SUCCESS;
}

Command::Result cSrvUnlockSkills(const Command::ArgumentList_t& args, ConsoleInterface& c, GameMap& gameMap)
{
    gameMap.consoleAskUnlockSkills();
    return Command::Result::SUCCESS;
}

Command::Result cKeys(const Command::ArgumentList_t&, ConsoleInterface& c, AbstractModeManager&)
{
    c.print(Translation::tr("console.keys"));
    return Command::Result::SUCCESS;
}

Command::Result cTriggerCompositor(const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&)
{
    if(args.size() < 2)
    {
        c.print(Translation::tr("console.compositor.need"));
        return Command::Result::INVALID_ARGUMENT;
    }
    RenderManager::getSingleton().triggerCompositor(args[1]);
    return Command::Result::SUCCESS;
}

} // namespace <none>


namespace ConsoleCommands
{
    void addConsoleCommands(ConsoleInterface& cl)
    {
        cl.addCommand("addcreature",
                         cSendCmdToServer,
                         cSrvAddCreature,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("addgold",
                         cSendCmdToServer,
                         cSrvAddGold,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("addmana",
                         cSendCmdToServer,
                         cSrvAddMana,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR }); 
        cl.addCommand("catmullspline",
                         cHermiteCatmullSpline,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         {"hermitecatmullspline" });
 
        cl.addCommand("circlearound",
                         cCircleAround,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("creaturevisdebug",
                         cSendCmdToServer,
                         cSrvCreatureVisDebug,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         {"creaturevisdebug" });
 
        cl.addCommand("enableZPrePass",
                         cEnableZPrePass,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
    
        cl.addCommand("farclip",
                         [](const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&) {
                             return cSetFrameListenerVar<float>(std::mem_fn(&ODFrameListener::getActiveCameraFarClipDistance),
                                                                std::mem_fn(&ODFrameListener::setActiveCameraFarClipDistance),
                                                                ODFrameListener::getSingleton(),
                                                                "console.var.farclip", args, c);
                         },
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("fps",
                         cFPS,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("getposition",
                         cGetPosition,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR});    
        cl.addCommand("getshadowtexturecount",
                         cGetShadowTextureCount,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR});    
        cl.addCommand("helpmessage",
                         [](const Command::ArgumentList_t&, ConsoleInterface& c, AbstractModeManager&) {
                             c.print(getHelpMessage());
                             return Command::Result::SUCCESS;
                         },
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("keys",
                         cKeys,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         { });
        cl.addCommand("light",
                         cAmbientLight,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
        
        cl.addCommand("list",
                         cList,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         {"ls" });
 
        cl.addCommand("listmeshanims",
                         cListMeshAnims,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         {"listmeshanimations" });
 
        cl.addCommand("logfloodfill",
                         cSendCmdToServer,
                         cSrvLogFloodFill,
                         {AbstractModeManager::ModeType::GAME},
                         { });
 
        cl.addCommand("maxtime",
                         [](const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&) {
                             return cSetFrameListenerVar<float>(std::mem_fn(&ODFrameListener::getEventMaxTimeDisplay),
                                                                std::mem_fn(&ODFrameListener::setEventMaxTimeDisplay),
                                                                ODFrameListener::getSingleton(),
                                                                "console.var.maxtime", args, c);
                         },
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("nearclip",
                         [](const Command::ArgumentList_t& args, ConsoleInterface& c, AbstractModeManager&) {
                             return cSetFrameListenerVar<float>(std::mem_fn(&ODFrameListener::getActiveCameraNearClipDistance),
                                                                std::mem_fn(&ODFrameListener::setActiveCameraNearClipDistance),
                                                                ODFrameListener::getSingleton(),
                                                                "console.var.nearclip", args, c);
                         },
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("reaction",
                         cCreatureReaction,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME});
        cl.addCommand("roomambience",
                         cRoomAmbience,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME});
        cl.addCommand("printentities",
                         cPrintEntities,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR});    
        cl.addCommand("printnodes",
                         cPrintNodes,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("seatvisualdebug",
                         cSendCmdToServer,
                         cSrvSeatVisDebug,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         {"seatvisdebug" });
 
        cl.addCommand("setShadowFarClipDistance",
                         cShadowFarClipDistance,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("setShadowNearClipDistance",
                         cShadowNearClipDistance,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("setcamerafovy",
                         cSetCameraFOVy,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("setcameralightdirectionthreshold",
                         cSetCameraLightDirectionThreshold,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("setcreaturedest",
                         cSendCmdToServer,
                         cSrvSetCreatureDest,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         {"setcreaturedestination" });
 
        cl.addCommand("setcreaturelevel",
                         cSendCmdToServer,
                         cSrvSetCreatureLevel,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("setloglevel",
                         cSetLogLevel,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR},
                         { });
 
        cl.addCommand("setoptimaladjustfactor",
                         cSetOptimalAdjustFactor,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });

        cl.addCommand("setuseoptimaladjust",
                         cSetUseSimpleOptimalAdjust,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });        
        cl.addCommand("setshadowcamerafovy",
                         cSetShadowCameraFovY,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR});    
 
        cl.addCommand("tilevisualdebug",
                         [](const Command::ArgumentList_t&, ConsoleInterface& c, AbstractModeManager&) {
                             GameMode* gm = static_cast<GameMode*>(ODFrameListener::getSingletonPtr()->getModeManager()->getCurrentMode());
                             gm->toggleAllowTileDebugWindow();
                             return Command::Result::SUCCESS;
                         },
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME });
 
    
        cl.addCommand("togglefow",
                         cSendCmdToServer,
                         cSrvToggleFOW,
                         {AbstractModeManager::ModeType::GAME},
                         {"icanseedeadpeople" });
 
        cl.addCommand("triggercompositor",
                         cTriggerCompositor,
                         Command::cStubServer,
                         {AbstractModeManager::ModeType::GAME, AbstractModeManager::ModeType::EDITOR });
 
        cl.addCommand("unlockskills",
                         cSendCmdToServer,
                         cSrvUnlockSkills,
                         {AbstractModeManager::ModeType::GAME });
    }

} // namespace ConsoleCommands
