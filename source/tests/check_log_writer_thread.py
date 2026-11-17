"""Check that logging never waits for a slow log sink (frame stall cause: synchronous log file writes).

Measured cause (INGAME-QS-10 P1): every log line was written and flushed to the log file by the thread that logged it,
so the render thread waited for the file system. Frame stall lines of the deployed build named it
"log-write-mutex-and-sinks" with 428 ms and 500 ms (owner session 2026-11-17 17:41:47 and 17:44:05) and 82 ms in a
measuring run without input.

The production LogManager.cpp and LogManager.h are compiled unchanged into a small probe with stand-ins for the Ogre
singleton, Helper, the frame stall trace and boost::filesystem. The probe adds a sink that needs 150 ms per line and:
- logs five normal lines and requires the five calls together to return in less than 100 ms (they took at least
  750 ms when the sink was written by the logging thread);
- logs a critical line and requires it to be in the sink, after the five earlier lines, when logMessage returns;
- logs a line below the log level and requires it never to reach the sink;
- destroys the manager and requires every accepted line in the sink exactly once and in logging order, with the
  module name taken from the file path.

Fixed values: 5 normal lines, 150 ms per sink write, 100 ms limit, 7 written lines. The probe compiles with cl, so this
check runs in the compile phase of the integration only.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

OGRE_SINGLETON = r'''
#pragma once
namespace Ogre
{
template<typename T> class Singleton
{
protected:
    static T* msSingleton;
public:
    Singleton() { msSingleton = static_cast<T*>(this); }
    ~Singleton() { msSingleton = nullptr; }
    static T& getSingleton() { return *msSingleton; }
    static T* getSingletonPtr() { return msSingleton; }
};
}
'''

HELPER = r'''
#pragma once
#include <string>
namespace Helper
{
template<typename T> std::string toString(T value) { return std::to_string(value); }
}
'''

FRAME_STALL_TRACE = r'''
#pragma once
class FrameStallTrace
{
public:
    enum Phase { LogWrite };
    class Scope
    {
    public:
        Scope(Phase, const char* = "") {}
    };
};
'''

BOOST_FILESYSTEM = r'''
#pragma once
#include <filesystem>
namespace boost { namespace filesystem { typedef std::filesystem::path path; } }
'''

PROBE = r'''
#include "utils/LogManager.h"

#include <cassert>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

struct Record
{
    std::mutex mLock;
    std::vector<std::string> mLines;
};

class SlowSink : public LogSink
{
public:
    explicit SlowSink(Record& record) : mRecord(record) {}
    void write(LogMessageLevel level, const std::string& module, const std::string& timestamp,
        const std::string& filename, int line, const std::string& message) override
    {
        std::this_thread::sleep_for(std::chrono::milliseconds(150));
        assert(module == "SlowModule");
        assert(filename == "SlowModule.cpp");
        assert(timestamp.size() == 8 && timestamp[2] == ':' && timestamp[5] == ':');
        (void)level;
        (void)line;
        std::lock_guard<std::mutex> locked(mRecord.mLock);
        mRecord.mLines.push_back(message);
    }
private:
    Record& mRecord;
};

int main()
{
    const char* file = "C:/game/source/SlowModule.cpp";
    Record record;
    {
        LogManager manager;
        manager.addSink(std::unique_ptr<LogSink>(new SlowSink(record)));
        const std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
        for(int i = 0; i < 5; ++i)
            manager.logMessage(LogMessageLevel::NORMAL, file, 10 + i, "line" + std::to_string(i));
        const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
        std::printf("five normal lines logged in %.2f ms\n", ms);
        assert(ms < 100.0);

        manager.logMessage(LogMessageLevel::CRITICAL, file, 20, "critical");
        {
            std::lock_guard<std::mutex> locked(record.mLock);
            assert(record.mLines.size() == 6);
            assert(record.mLines.back() == "critical");
        }
        assert(manager.getCriticalCount() == 1);
        manager.logMessage(LogMessageLevel::TRIVIAL, file, 30, "filtered");
        manager.logMessage(LogMessageLevel::NORMAL, file, 40, "after");
    }
    const std::vector<std::string> expected = {"line0", "line1", "line2", "line3", "line4", "critical", "after"};
    assert(record.mLines == expected);
    std::printf("log writer probe passed (%u lines)\n", static_cast<unsigned int>(record.mLines.size()));
    return 0;
}
'''


def main():
    """Compiles the production log manager with the stand-ins and runs the probe."""
    vcvars = Path('C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        include = directory / 'include'
        for relative, text in (('OgreSingleton.h', OGRE_SINGLETON), ('utils/Helper.h', HELPER),
                               ('render/FrameStallTrace.h', FRAME_STALL_TRACE),
                               ('boost/filesystem.hpp', BOOST_FILESYSTEM)):
            target = include / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
        for relative in ('utils/LogManager.h', 'utils/LogSink.h', 'utils/LogMessageLevel.h'):
            target = include / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ROOT / 'source' / relative).read_text(encoding='utf-8'), encoding='utf-8')
        # LogSink.h includes "LogMessageLevel.h" relative to itself; it is copied next to it above.
        production = directory / 'LogManager.cpp'
        production.write_text((ROOT / 'source/utils/LogManager.cpp').read_text(encoding='utf-8'), encoding='utf-8')
        probe = directory / 'probe.cpp'
        probe.write_text(PROBE, encoding='utf-8')
        batch = directory / 'run.cmd'
        batch.write_text(
            f'@echo off\ncall "{vcvars}" >nul\n'
            f'cl /nologo /EHsc /std:c++17 /I"{include}" "{production}" "{probe}" /Fe:"{directory / "probe.exe"}" '
            f'/Fo:"{directory}\\\\"\n'
            'if errorlevel 1 exit /b 1\n'
            f'"{directory / "probe.exe"}"\nexit /b %errorlevel%\n',
            encoding='utf-8',
        )
        subprocess.run(['cmd', '/d', '/c', str(batch)], cwd=directory, check=True)
    print('log writer thread passes the checks')


if __name__ == '__main__':
    main()
